"""One upper-block fine-tuning experiment; smoke/train/verify, no test images."""
import argparse
import csv
import hashlib
import json
import math
import sys
import time

try:
    from ai.train_baseline import (FrozenImages, build_model, evaluate, one_per_class,
                                   seed_everything, torch, nn, torchvision, np, Image)
    from ai.baseline_data import ROOT, load_baseline_data, training_class_weights
except ModuleNotFoundError:
    from train_baseline import (FrozenImages, build_model, evaluate, one_per_class,
                               seed_everything, torch, nn, torchvision, np, Image)
    from baseline_data import ROOT, load_baseline_data, training_class_weights
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.models import EfficientNet_B0_Weights


def configure_trainable(model, blocks):
    if blocks != [6, 7, 8] or len(model.features) != 9:
        raise ValueError('This experiment requires EfficientNet-B0 blocks 6, 7, 8')
    model.requires_grad_(False)
    for index in blocks: model.features[index].requires_grad_(True)
    model.classifier.requires_grad_(True)
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm): module.requires_grad_(False)


def training_mode(model, blocks):
    model.train()
    model.features.eval()
    for index in blocks: model.features[index].train()
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm): module.eval()


def state_checks(model, source, blocks):
    current = model.state_dict()
    trainable = {name for name, parameter in model.named_parameters() if parameter.requires_grad}
    frozen = [name for name in current if name not in trainable]
    changed_blocks = {str(index): any(
        not torch.equal(current[name].detach().cpu(), source[name])
        for name in trainable if name.startswith(f'features.{index}.')) for index in blocks}
    checks = {'frozen_parameters_and_buffers_unchanged': all(
        torch.equal(current[name].detach().cpu(), source[name]) for name in frozen),
        'changed_feature_blocks': changed_blocks,
        'classifier_updated': any(not torch.equal(current[name].detach().cpu(), source[name])
                                  for name in trainable if name.startswith('classifier.'))}
    if not checks['frozen_parameters_and_buffers_unchanged'] or not all(changed_blocks.values()) or not checks['classifier_updated']:
        raise ValueError(f'Fine-tuning state invariants failed: {checks}')
    return checks


def load_source(config, mapping):
    path = ROOT / config['source_checkpoint']
    if hashlib.sha256(path.read_bytes()).hexdigest() != config['source_sha256']:
        raise ValueError('Baseline checkpoint hash changed')
    source = torch.load(path, map_location='cpu', weights_only=True)
    metadata = source['metadata']
    if metadata['class_to_index'] != mapping or metadata['config']['dataset_lock_sha256_lf'] != config['dataset_lock_sha256_lf']:
        raise ValueError('Source baseline uses a different dataset/class mapping')
    if metadata['mode'] != 'train' or metadata['test_images_evaluated'] != 0:
        raise ValueError('Source must be the validation-only trained baseline')
    return source


def assert_metrics(actual, expected):
    for key in ('accuracy', 'macro_f1', 'confusion_matrix', 'per_class'):
        if actual[key] != expected[key]: raise ValueError(f'Validation replay differs: {key}')
    if not math.isclose(actual['loss'], expected['loss'], rel_tol=1e-6, abs_tol=1e-6):
        raise ValueError('Validation replay loss differs')


def macro_precision(metrics):
    return sum(row['precision'] for row in metrics['per_class']) / len(metrics['per_class'])


def verify(folder, device):
    run = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
    config = run['config']
    history = json.loads((folder / 'history.json').read_text(encoding='utf-8'))
    complete = json.loads((folder / 'complete.json').read_text(encoding='utf-8'))
    if run['mode'] != 'train' or complete['epochs'] != config['epochs'] or [r['epoch'] for r in history] != list(range(1, config['epochs'] + 1)):
        raise ValueError('Incomplete training run')
    if complete['test_evaluated'] is not False or run['test_images_evaluated'] != 0:
        raise ValueError('Test evaluation is not permitted here')
    best = max(history, key=lambda r: (r['validation']['macro_f1'], -r['validation']['loss']))
    path = folder / 'best.pt'
    checkpoint = torch.load(path, map_location='cpu', weights_only=True)
    if checkpoint['epoch'] != best['epoch'] or checkpoint['validation'] != best['validation'] or checkpoint['metadata'] != run:
        raise ValueError('Checkpoint does not match selection rule/metadata')
    mapping, rows, _ = load_baseline_data(config)
    source = load_source(config, mapping)
    seed_everything(config['seed'], config['cpu_threads'])
    model = build_model(len(mapping), pretrained=False)
    model.load_state_dict(checkpoint['model_state_dict'])
    configure_trainable(model, config['feature_blocks'])
    checks = state_checks(model, source['model_state_dict'], config['feature_blocks'])
    model.to(device)
    loader = DataLoader(FrozenImages(rows['val'], EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()), batch_size=config['batch_size'])
    reproduced = evaluate(model, loader, device, len(mapping))
    assert_metrics(reproduced, checkpoint['validation'])
    # Replay the source on the identical validation loader to verify the comparison too.
    model.load_state_dict(source['model_state_dict'])
    baseline = evaluate(model, loader, device, len(mapping))
    assert_metrics(baseline, source['validation'])
    output = ROOT / 'docs/ai/finetune_results'
    output.mkdir(parents=True, exist_ok=True)
    summary = {'run_id': folder.name, 'config': config, 'environment': run,
               'checkpoint_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'best_epoch': best['epoch'], 'validation_images': len(rows['val']),
               'test_images_evaluated': 0, 'validation_replay_verified': True,
               'baseline_replay_verified': True, 'state_checks': checks,
               'baseline': baseline, 'finetuned': reproduced,
               'baseline_macro_precision': macro_precision(baseline),
               'finetuned_macro_precision': macro_precision(reproduced),
               'epoch_seconds_total': sum(r['seconds'] for r in history)}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    (output / 'epochs.json').write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
    with (output / 'per_class.csv').open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['class_name', 'class_index', 'support', 'precision', 'recall', 'f1'])
        writer.writeheader()
        for name, index in sorted(mapping.items(), key=lambda pair: pair[1]):
            writer.writerow({'class_name': name, **reproduced['per_class'][index]})
    print(json.dumps({key: summary[key] for key in ('best_epoch', 'validation_replay_verified', 'baseline_replay_verified', 'state_checks', 'baseline_macro_precision', 'finetuned_macro_precision')}, indent=2))
    print(json.dumps({'baseline_accuracy': baseline['accuracy'], 'finetuned_accuracy': reproduced['accuracy'],
                      'baseline_macro_f1': baseline['macro_f1'], 'finetuned_macro_f1': reproduced['macro_f1']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('smoke', 'train', 'verify'), required=True)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    if not args.run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in args.run_id):
        raise ValueError('Invalid run ID')
    device = torch.device(args.device)
    if device.type == 'cuda' and not torch.cuda.is_available(): raise ValueError('CUDA unavailable')
    folder = ROOT / 'ai/runs' / args.run_id
    if args.mode == 'verify': return verify(folder, device)
    if folder.exists(): raise ValueError('Run exists; use a new run ID')
    config = json.loads((ROOT / 'ai/finetune_config.json').read_text(encoding='utf-8'))
    mapping, rows, dataset = load_baseline_data(config)
    source = load_source(config, mapping)
    seed_everything(config['seed'], config['cpu_threads'])
    model = build_model(len(mapping), pretrained=False)
    model.load_state_dict(source['model_state_dict'])
    configure_trainable(model, config['feature_blocks'])
    model.to(device)
    validation_transform = EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()
    training_transform = transforms.Compose([transforms.RandomHorizontalFlip(p=0.5), validation_transform])
    feature_parameters = [p for p in model.features.parameters() if p.requires_grad]
    classifier_parameters = [p for p in model.classifier.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW([
        {'params': feature_parameters, 'lr': config['feature_learning_rate']},
        {'params': classifier_parameters, 'lr': config['classifier_learning_rate']}], weight_decay=config['weight_decay'])
    criterion = nn.CrossEntropyLoss(weight=torch.tensor(training_class_weights(rows['train'], len(mapping)), device=device))
    run = {'mode': args.mode, 'config': config, 'class_to_index': mapping, 'dataset_lock': dataset,
           'source_epoch': source['epoch'], 'device': str(device),
           'gpu': torch.cuda.get_device_name(0) if device.type == 'cuda' else None,
           'python': sys.version, 'torch': str(torch.__version__), 'torchvision': str(torchvision.__version__),
           'numpy': np.__version__, 'pillow': Image.__version__, 'cuda_runtime': torch.version.cuda,
           'training_transform': repr(training_transform), 'validation_transform': repr(validation_transform),
           'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad),
           'test_images_evaluated': 0}
    folder.mkdir(parents=True)
    (folder / 'run.json').write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'mode': args.mode, 'trainable_parameters': run['trainable_parameters'], 'gpu': run['gpu']}), flush=True)
    if args.mode == 'smoke':
        loader = DataLoader(FrozenImages(one_per_class(rows['train']), training_transform), batch_size=len(mapping))
        images, labels = next(iter(loader))
        training_mode(model, config['feature_blocks']); optimizer.zero_grad(set_to_none=True)
        logits = model(images.to(device)); loss = criterion(logits, labels.to(device))
        if not torch.isfinite(loss): raise ValueError('Nonfinite loss')
        loss.backward(); optimizer.step()
        checks = state_checks(model, source['model_state_dict'], config['feature_blocks'])
        smoke = {**checks, 'training_images': len(mapping), 'test_images': 0, 'checkpoint_saved': False, 'logits_shape': list(logits.shape)}
        (folder / 'smoke.json').write_text(json.dumps(smoke, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(smoke, indent=2)); return
    train_loader = DataLoader(FrozenImages(rows['train'], training_transform), batch_size=config['batch_size'], shuffle=True,
                              generator=torch.Generator().manual_seed(config['seed']), num_workers=config['num_workers'])
    val_loader = DataLoader(FrozenImages(rows['val'], validation_transform), batch_size=config['batch_size'], num_workers=config['num_workers'])
    best, history = (-1.0, float('-inf')), []
    for epoch in range(1, config['epochs'] + 1):
        started = time.monotonic(); training_mode(model, config['feature_blocks']); loss_sum = batches = 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True); loss = criterion(model(images), labels)
            if not torch.isfinite(loss): raise ValueError('Nonfinite loss')
            loss.backward(); optimizer.step(); loss_sum += loss.item(); batches += 1
        validation = evaluate(model, val_loader, device, len(mapping))
        history.append({'epoch': epoch, 'training_weighted_mean_batch_loss': loss_sum / batches,
                        'validation': validation, 'seconds': time.monotonic() - started})
        score = (validation['macro_f1'], -validation['loss'])
        if score > best:
            best = score
            state_checks(model, source['model_state_dict'], config['feature_blocks'])
            torch.save({'model_state_dict': model.state_dict(), 'metadata': run, 'epoch': epoch, 'validation': validation}, folder / 'best.pt')
        (folder / 'history.json').write_text(json.dumps(history, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'epoch': epoch, 'accuracy': validation['accuracy'], 'macro_f1': validation['macro_f1'],
                          'macro_precision': macro_precision(validation), 'loss': validation['loss']}), flush=True)
    (folder / 'complete.json').write_text(json.dumps({'epochs': len(history), 'test_evaluated': False}, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
