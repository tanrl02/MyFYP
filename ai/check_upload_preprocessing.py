"""Validation-only upload compatibility check; no fitting, server or database writes."""
import hashlib
from collections import Counter
from io import BytesIO
import json
import sys

try:
    from ai.compare_models import ROOT,build,transforms_for,FrozenImages,torch,seed_everything
    from ai.baseline_data import load_baseline_data,classification_metrics
    from ai.train_finetune import assert_metrics,macro_precision
except ModuleNotFoundError:
    from compare_models import ROOT,build,transforms_for,FrozenImages,torch,seed_everything
    from baseline_data import load_baseline_data,classification_metrics
    from train_finetune import assert_metrics,macro_precision
from PIL import Image,ImageOps
from torch.utils.data import DataLoader,Dataset

# Importing the pure photo helper defines Store but never constructs a database.
sys.path.insert(0,str(ROOT/'apps/api'))
from app.photos import normalise_photo
from app.store import RuleError


class CleanedImages(Dataset):
    def __init__(self,photos,transform):self.photos,self.transform=photos,transform
    def __len__(self):return len(self.photos)
    def __getitem__(self,index):
        content,label=self.photos[index]
        with Image.open(BytesIO(content)) as image:
            return self.transform(ImageOps.exif_transpose(image).convert('RGB')),label


def predict(model,loader,device):
    model.eval();targets=[];predictions=[];loss_sum=0
    with torch.inference_mode():
        for images,labels in loader:
            labels=labels.to(device);logits=model(images.to(device))
            if not torch.isfinite(logits).all():raise ValueError('Nonfinite logits')
            loss_sum+=torch.nn.functional.cross_entropy(logits,labels,reduction='sum').item()
            targets.extend(labels.cpu().tolist());predictions.extend(logits.argmax(1).cpu().tolist())
    return {**classification_metrics(targets,predictions,8),'loss':loss_sum/len(targets)},predictions


def transition_counts(targets,before,after):
    if not targets or len(targets)!=len(before) or len(before)!=len(after):raise ValueError('Unpaired predictions')
    return {'predictions_changed':sum(a!=b for a,b in zip(before,after)),
        'correct_to_wrong':sum(a==t and b!=t for t,a,b in zip(targets,before,after)),
        'wrong_to_correct':sum(a!=t and b==t for t,a,b in zip(targets,before,after))}


def main():
    if not torch.cuda.is_available():raise ValueError('CUDA required for matched comparison')
    device=torch.device('cuda');seed_everything(3403,4)
    config=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    mapping,rows,_=load_baseline_data(config)
    cleaned=[];accepted=[];failures=Counter();resized=0;metadata_present=0
    for row in rows['val']:
        content=(ROOT/row['local_path']).read_bytes()
        if hashlib.sha256(content).hexdigest()!=row['sha256']:raise ValueError('Validation image changed')
        with Image.open(BytesIO(content)) as image:
            size=ImageOps.exif_transpose(image).size
            metadata_present+=bool(image.getexif())
        try:
            photo,width,height=normalise_photo(content)
        except RuleError as error:
            failures[error.message]+=1;continue
        resized+=(width,height)!=size
        cleaned.append((photo,int(row['class_index'])));accepted.append(row)
    transform=transforms_for()[1]
    output={'purpose':'Fixed-checkpoint validation upload compatibility; not phone/clinical validation',
        'validation_total':len(rows['val']),'upload_accepted':len(cleaned),'upload_rejected':sum(failures.values()),
        'rejection_reasons':dict(failures),'images_downsized':resized,'source_images_with_exif':metadata_present,
        'photo_helper_sha256':hashlib.sha256((ROOT/'apps/api/app/photos.py').read_bytes()).hexdigest(),
        'class_to_index':mapping,'runs':[],'test_images_evaluated':0,'training_steps':0}
    if not cleaned:raise ValueError('No accepted photos')
    for report in ('docs/ai/model_comparison/comparison-v1-efficientnet_b0/summary.json',
                   'docs/ai/efficientnet_tuning/tuning-v1-partial-freeze/summary.json'):
        reference=json.loads((ROOT/report).read_text());run_id=reference['run_id']
        path=ROOT/'ai/runs'/run_id/'best.pt'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['checkpoint_sha256']:raise ValueError('Checkpoint changed')
        saved=torch.load(path,map_location='cpu',weights_only=True)
        if saved['metadata']['class_to_index']!=mapping:raise ValueError('Class mapping changed')
        model=build('efficientnet_b0',pretrained=False).to(device)
        model.load_state_dict(saved['model_state_dict'])
        raw_all,_=predict(model,DataLoader(FrozenImages(rows['val'],transform),batch_size=16),device)
        assert_metrics(raw_all,reference['validation'])
        raw,pred_before=predict(model,DataLoader(FrozenImages(accepted,transform),batch_size=16),device)
        processed,pred_after=predict(model,DataLoader(CleanedImages(cleaned,transform),batch_size=16),device)
        targets=[int(row['class_index']) for row in accepted]
        result={'run_id':run_id,'checkpoint_sha256':reference['checkpoint_sha256'],
            'raw_all_validation_replay_verified':True,'accepted_subset_images':len(accepted),
            'raw_accepted_metrics':raw,'upload_accepted_metrics':processed,
            'upload_accepted_macro_precision':macro_precision(processed),
            **transition_counts(targets,pred_before,pred_after)}
        output['runs'].append(result)
        print(json.dumps({'run_id':run_id,'raw_accuracy':raw['accuracy'],'upload_accuracy':processed['accuracy'],
            'changed':result['predictions_changed'],'rejected':sum(failures.values())}),flush=True)
        del model;torch.cuda.empty_cache()
    destination=ROOT/'docs/ai/dataset_readiness/upload_compatibility.json'
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    print('No model changes, training or final-test inference.',flush=True)


if __name__=='__main__':main()
