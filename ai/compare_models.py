"""Three pretrained architectures under one predeclared validation-only protocol."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

try:
    from ai.train_baseline import FrozenImages, evaluate, seed_everything, torch, nn, torchvision, np, Image, one_per_class
    from ai.baseline_data import ROOT, load_baseline_data, training_class_weights
    from ai.train_finetune import assert_metrics, macro_precision
except ModuleNotFoundError:
    from train_baseline import FrozenImages, evaluate, seed_everything, torch, nn, torchvision, np, Image, one_per_class
    from baseline_data import ROOT, load_baseline_data, training_class_weights
    from train_finetune import assert_metrics, macro_precision
from torch.utils.data import DataLoader
from torchvision import models, transforms

SPECS = {
    'efficientnet_b0': (models.efficientnet_b0, models.EfficientNet_B0_Weights.IMAGENET1K_V1),
    'resnet50': (models.resnet50, models.ResNet50_Weights.IMAGENET1K_V2),
    'densenet121': (models.densenet121, models.DenseNet121_Weights.IMAGENET1K_V1)}


def build(architecture, classes=8, pretrained=True):
    builder, weights = SPECS[architecture]
    model = builder(weights=weights if pretrained else None)
    if architecture == 'resnet50': model.fc = nn.Linear(model.fc.in_features, classes)
    elif architecture == 'densenet121': model.classifier = nn.Linear(model.classifier.in_features, classes)
    else: model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, classes)
    return model


def head(model, architecture): return model.fc if architecture == 'resnet50' else model.classifier


def configure(model, architecture, full):
    model.requires_grad_(full)
    head(model, architecture).requires_grad_(True)
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm): module.requires_grad_(False)


def training_mode(model, architecture, full):
    model.train() if full else model.eval()
    head(model, architecture).train()
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm): module.eval()


def frozen_digest(model):
    trainable = {name for name, param in model.named_parameters() if param.requires_grad}
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        if name not in trainable:
            digest.update(name.encode()); digest.update(tensor.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def transforms_for():
    normalise = transforms.Normalize((.485,.456,.406),(.229,.224,.225))
    validation = transforms.Compose([transforms.Resize(256, interpolation=transforms.InterpolationMode.BICUBIC),
        transforms.CenterCrop(224), transforms.ToTensor(), normalise])
    training = transforms.Compose([transforms.RandomResizedCrop(224, scale=(.85,1), ratio=(.9,1.1),
        interpolation=transforms.InterpolationMode.BICUBIC), transforms.RandomHorizontalFlip(.5), transforms.ToTensor(), normalise])
    return training, validation


def score(metrics): return metrics['accuracy'], metrics['macro_f1'], -metrics['loss']


def weight_path(architecture):
    torch.hub.set_dir(str(ROOT/'ai/weights'))
    return Path(torch.hub.get_dir())/'checkpoints'/Path(SPECS[architecture][1].url).name


def verify(folder, device):
    run=json.loads((folder/'run.json').read_text()); config=run['config']; arch=run['architecture']
    complete=json.loads((folder/'complete.json').read_text()); history=json.loads((folder/'history.json').read_text())
    if complete['test_evaluated'] or run['test_images_evaluated'] != 0: raise ValueError('Test use forbidden')
    if complete['epochs'] != len(history) or [r['epoch'] for r in history] != list(range(1,len(history)+1)):
        raise ValueError('Incomplete history')
    if len(history) < config['warmup_epochs']+config['minimum_finetune_epochs']: raise ValueError('Too little completed fine-tuning')
    best=max((r for r in history if r['stage']=='full_finetune'),key=lambda r:score(r['validation']))
    path=folder/'best.pt'; saved=torch.load(path,map_location='cpu',weights_only=True)
    if saved['metadata'] != run or saved['epoch'] != best['epoch'] or saved['validation'] != best['validation']:
        raise ValueError('Checkpoint differs from logged selection')
    mapping,rows,_=load_baseline_data(config)
    if mapping != run['class_to_index']: raise ValueError('Class mapping changed')
    seed_everything(config['seed'],config['cpu_threads'])
    model=build(arch,pretrained=False); model.load_state_dict(saved['model_state_dict']); configure(model,arch,True)
    if frozen_digest(model) != run['full_frozen_digest']: raise ValueError('Frozen BatchNorm state changed')
    if hashlib.sha256(weight_path(arch).read_bytes()).hexdigest() != run['pretrained_sha256']: raise ValueError('Source weights changed')
    original=build(arch,pretrained=True)
    original_head={id(param) for param in head(original,arch).parameters()}
    feature_names=[name for name,param in original.named_parameters() if id(param) not in original_head]
    if not any(not torch.equal(model.state_dict()[name], original.state_dict()[name]) for name in feature_names):
        raise ValueError('No feature updates found')
    model.to(device)
    loader=DataLoader(FrozenImages(rows['val'],transforms_for()[1]),batch_size=config['batch_size'])
    metrics=evaluate(model,loader,device,len(mapping)); assert_metrics(metrics,saved['validation'])
    output=ROOT/'docs/ai/model_comparison'/folder.name; output.mkdir(parents=True,exist_ok=True)
    result={'run_id':folder.name,'architecture':arch,'run':run,'checkpoint_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'best_epoch':saved['epoch'],'epochs_completed':len(history),'validation':metrics,'macro_precision':macro_precision(metrics),
        'validation_replay_verified':True,'frozen_batchnorm_verified':True,'features_updated':True,
        'epoch_seconds':sum(r['seconds'] for r in history),'accuracy_target_reached':metrics['accuracy']>=config['accuracy_target'],
        'test_images_evaluated':0}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    (output/'epochs.json').write_text(json.dumps(history,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('architecture','best_epoch','epochs_completed','macro_precision','accuracy_target_reached','validation_replay_verified')}),flush=True)
    print(json.dumps({'accuracy':metrics['accuracy'],'macro_f1':metrics['macro_f1'],'loss':metrics['loss']}),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('fetch','smoke','train','verify'),required=True)
    parser.add_argument('--architecture',choices=tuple(SPECS),required=True)
    parser.add_argument('--run-id')
    parser.add_argument('--device',choices=('cuda','cpu'),default='cuda')
    args=parser.parse_args()
    arch=args.architecture; path=weight_path(arch)
    if args.mode=='fetch':
        weights=SPECS[arch][1]
        torch.hub.load_state_dict_from_url(weights.url,model_dir=str(path.parent),check_hash=True,progress=False)
        print(json.dumps({'architecture':arch,'url':weights.url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})); return
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.run_id): raise ValueError('Invalid run ID')
    device=torch.device(args.device)
    if device.type=='cuda' and not torch.cuda.is_available(): raise ValueError('CUDA unavailable')
    folder=ROOT/'ai/runs'/args.run_id
    if args.mode=='verify': return verify(folder,device)
    if folder.exists(): raise ValueError('Run already exists')
    if not path.exists(): raise ValueError('Pretrained weights missing; fetch separately')
    weight_sha=hashlib.sha256(path.read_bytes()).hexdigest()
    if not weight_sha.startswith(path.stem.rsplit('-',1)[1]): raise ValueError('Pretrained hash-prefix mismatch')
    config=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    mapping,rows,dataset=load_baseline_data(config)
    seed_everything(config['seed'],config['cpu_threads'])
    model=build(arch,len(mapping)).to(device)
    train_transform,val_transform=transforms_for()
    configure(model,arch,True); full_frozen=frozen_digest(model)
    configure(model,arch,False); warm_frozen=frozen_digest(model)
    run={'architecture':arch,'config':config,'class_to_index':mapping,'dataset_lock':dataset,'mode':args.mode,
        'pretrained_url':SPECS[arch][1].url,'pretrained_sha256':weight_sha,'full_frozen_digest':full_frozen,
        'train_transform':repr(train_transform),'validation_transform':repr(val_transform),
        'parameters':sum(p.numel() for p in model.parameters()),'torch':str(torch.__version__),
        'torchvision':str(torchvision.__version__),'numpy':np.__version__,'pillow':Image.__version__,
        'python':sys.version,'device':str(device),'gpu':torch.cuda.get_device_name(0) if device.type=='cuda' else None,
        'test_images_evaluated':0}
    folder.mkdir(parents=True); (folder/'run.json').write_text(json.dumps(run,indent=2)+'\n')
    criterion=nn.CrossEntropyLoss(weight=torch.tensor(training_class_weights(rows['train'],len(mapping)),device=device))
    if args.mode=='smoke':
        images,labels=next(iter(DataLoader(FrozenImages(one_per_class(rows['train']),train_transform),batch_size=8)))
        for full in (False,True):
            configure(model,arch,full); before=frozen_digest(model); training_mode(model,arch,full)
            optimizer=torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],lr=1e-4)
            optimizer.zero_grad(); loss=criterion(model(images.to(device)),labels.to(device)); loss.backward(); optimizer.step()
            if not torch.isfinite(loss) or frozen_digest(model)!=before: raise ValueError('Smoke invariants failed')
        (folder/'smoke.json').write_text(json.dumps({'finite_loss':True,'both_stage_frozen_state_verified':True,'checkpoint_saved':False,'test_images':0},indent=2)+'\n')
        print(arch+' smoke passed',flush=True); return
    loader=DataLoader(FrozenImages(rows['train'],train_transform),batch_size=config['batch_size'],shuffle=True,
        generator=torch.Generator().manual_seed(config['seed']),num_workers=0)
    val_loader=DataLoader(FrozenImages(rows['val'],val_transform),batch_size=config['batch_size'],num_workers=0)
    optimizer=torch.optim.AdamW(head(model,arch).parameters(),lr=config['warmup_head_lr'],weight_decay=config['weight_decay'])
    best=(-1,-1,float('-inf')); history=[]; stale=0; scheduler=None
    for epoch in range(1,config['warmup_epochs']+config['finetune_epochs']+1):
        full=epoch>config['warmup_epochs']
        if epoch==config['warmup_epochs']+1:
            if frozen_digest(model)!=warm_frozen: raise ValueError('Warm-up changed frozen features')
            configure(model,arch,True)
            head_ids={id(p) for p in head(model,arch).parameters()}
            optimizer=torch.optim.AdamW([
                {'params':[p for p in model.parameters() if p.requires_grad and id(p) not in head_ids],'lr':config['feature_lr']},
                {'params':head(model,arch).parameters(),'lr':config['head_lr']}],weight_decay=config['weight_decay'])
            scheduler=torch.optim.lr_scheduler.CosineAnnealingLR(optimizer,T_max=config['finetune_epochs'],eta_min=1e-6)
        started=time.monotonic(); training_mode(model,arch,full); total=batches=0
        for images,labels in loader:
            optimizer.zero_grad(set_to_none=True)
            loss=criterion(model(images.to(device)),labels.to(device))
            if not torch.isfinite(loss): raise ValueError('Nonfinite training loss')
            loss.backward(); optimizer.step(); total+=loss.item(); batches+=1
        metrics=evaluate(model,val_loader,device,len(mapping))
        history.append({'epoch':epoch,'stage':'full_finetune' if full else 'head_warmup',
            'training_weighted_mean_batch_loss':total/batches,'validation':metrics,'seconds':time.monotonic()-started})
        if full:
            if frozen_digest(model)!=full_frozen: raise ValueError('Frozen BatchNorm state changed')
            if score(metrics)>best:
                best=score(metrics); stale=0
                torch.save({'model_state_dict':model.state_dict(),'metadata':run,'epoch':epoch,'validation':metrics},folder/'best.pt')
            else: stale+=1
            scheduler.step()
        (folder/'history.json').write_text(json.dumps(history,indent=2)+'\n')
        print(json.dumps({'architecture':arch,'epoch':epoch,'stage':history[-1]['stage'],
            'accuracy':metrics['accuracy'],'macro_f1':metrics['macro_f1'],'seconds':history[-1]['seconds']}),flush=True)
        if full and epoch-config['warmup_epochs']>=config['minimum_finetune_epochs'] and stale>=config['early_stopping_patience']: break
    (folder/'complete.json').write_text(json.dumps({'epochs':len(history),'test_evaluated':False,'best_selection_score':best},indent=2)+'\n')


if __name__=='__main__': main()
