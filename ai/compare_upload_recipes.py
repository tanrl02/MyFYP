"""Fixed-checkpoint, validation-only recipe comparison. No fitting or app writes."""
from collections import Counter
import hashlib
from io import BytesIO
import json
import statistics

try:
    from ai.check_upload_preprocessing import (ROOT,build,transforms_for,FrozenImages,torch,
        seed_everything,load_baseline_data,assert_metrics,macro_precision,CleanedImages,predict,transition_counts)
    from ai.upload_recipes import render_variants,RECIPE_NAMES
except ModuleNotFoundError:
    from check_upload_preprocessing import (ROOT,build,transforms_for,FrozenImages,torch,
        seed_everything,load_baseline_data,assert_metrics,macro_precision,CleanedImages,predict,transition_counts)
    from upload_recipes import render_variants,RECIPE_NAMES
from PIL import Image
from torch.utils.data import DataLoader
from app.store import RuleError


def size_summary(sizes):
    if not sizes:raise ValueError('No encoded images')
    return {'total_bytes':sum(sizes),'mean_bytes':statistics.mean(sizes),
            'median_bytes':statistics.median(sizes),'max_bytes':max(sizes),
            'outputs_over_5_mib':sum(s>5*1024*1024 for s in sizes)}


def main():
    config=json.loads((ROOT/'ai/upload_recipe_config.json').read_text())
    if tuple(config['recipes'])!=RECIPE_NAMES or config['test_evaluation']!='disabled' or config['training_steps']!=0:
        raise ValueError('Recipe protocol changed')
    if not torch.cuda.is_available():raise ValueError('Matched evaluation requires CUDA')
    device=torch.device('cuda');seed_everything(config['seed'],4)
    control=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    mapping,rows,_=load_baseline_data(control)
    if len(rows['val'])!=config['validation_images']:raise ValueError('Validation split changed')
    previous=json.loads((ROOT/'docs/ai/dataset_readiness/upload_compatibility.json').read_text())
    helper_sha=hashlib.sha256((ROOT/'apps/api/app/photos.py').read_bytes()).hexdigest()
    if helper_sha!=previous['photo_helper_sha256']:raise ValueError('Production helper changed since control audit')
    photos={name:[] for name in RECIPE_NAMES};failures=Counter()
    for row in rows['val']:
        content=(ROOT/row['local_path']).read_bytes()
        if hashlib.sha256(content).hexdigest()!=row['sha256']:raise ValueError('Validation bytes changed')
        try:encoded,dimensions=render_variants(content)
        except RuleError as error:
            failures[error.message]+=1;continue
        for name,body in encoded.items():
            with Image.open(BytesIO(body)) as image:
                if image.size!=dimensions or image.mode!='RGB' or image.getexif():raise ValueError('Image invariants failed')
                if any(key in image.info for key in ('icc_profile','comment','xmp','XML:com.adobe.xmp')):
                    raise ValueError('Unexpected retained source metadata')
            photos[name].append((body,int(row['class_index'])))
    if failures:raise ValueError('Input rejection; abort fixed-193 protocol rather than silently subset: '+str(failures))
    print('All193 photos encoded; current recipe byte-matches helper; all geometry/RGB/EXIF checks passed.',flush=True)
    result={'protocol':config,'validation_images':len(rows['val']),'class_to_index':mapping,
        'dataset_lock_sha256_lf':control['dataset_lock_sha256_lf'],'helper_sha256':helper_sha,
        'recipe_module_sha256':hashlib.sha256((ROOT/'ai/upload_recipes.py').read_bytes()).hexdigest(),
        'environment':{'torch':str(torch.__version__),'pillow':Image.__version__,
                       'device':torch.cuda.get_device_name(0)},
        'input_rejected':0,'current_helper_byte_match_images':len(rows['val']),
        'metadata_rgb_geometry_checks_passed':True,
        'storage':{name:size_summary([len(body) for body,_ in values]) for name,values in photos.items()},
        'runs':[],'test_images_evaluated':0,'training_steps':0,'app_changed':False}
    transform=transforms_for()[1];targets=[int(row['class_index']) for row in rows['val']]
    references=[json.loads((ROOT/path).read_text()) for path in (
        'docs/ai/model_comparison/comparison-v1-efficientnet_b0/summary.json',
        'docs/ai/efficientnet_tuning/tuning-v1-partial-freeze/summary.json')]
    if [r['run_id'] for r in references]!=config['checkpoints']:raise ValueError('Checkpoint protocol changed')
    for reference in references:
        path=ROOT/'ai/runs'/reference['run_id']/'best.pt'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['checkpoint_sha256']:raise ValueError('Weights changed')
        saved=torch.load(path,map_location='cpu',weights_only=True)
        if saved['metadata']['class_to_index']!=mapping or saved['metadata']['validation_transform']!=repr(transform):
            raise ValueError('Checkpoint preprocessing/mapping mismatch')
        model=build('efficientnet_b0',pretrained=False).to(device);model.load_state_dict(saved['model_state_dict'])
        raw,before=predict(model,DataLoader(FrozenImages(rows['val'],transform),batch_size=16),device)
        assert_metrics(raw,reference['validation'])
        run={'run_id':reference['run_id'],'checkpoint_sha256':reference['checkpoint_sha256'],
            'raw_validation':raw,'raw_replay_verified':True,'recipes':{}}
        prior=next(r for r in previous['runs'] if r['run_id']==reference['run_id'])
        for name in RECIPE_NAMES:
            metrics,after=predict(model,DataLoader(CleanedImages(photos[name],transform),batch_size=16),device)
            transitions=transition_counts(targets,before,after)
            if name=='current_jpeg85':
                assert_metrics(metrics,prior['upload_accepted_metrics'])
                if any(transitions[k]!=prior[k] for k in transitions):raise ValueError('Control prediction changes differ')
            run['recipes'][name]={'metrics':metrics,'macro_precision':macro_precision(metrics),
                'prediction_agreement':1-transitions['predictions_changed']/len(targets),**transitions}
            print(json.dumps({'run':reference['run_id'],'recipe':name,'accuracy':metrics['accuracy'],
                              'changed':transitions['predictions_changed']}),flush=True)
        result['runs'].append(run);del model;torch.cuda.empty_cache()
    def rank(name):
        changes=[r['recipes'][name]['predictions_changed'] for r in result['runs']]
        return max(changes),sum(changes),result['storage'][name]['total_bytes']
    ranked=sorted(RECIPE_NAMES,key=rank)
    result['prediction_preservation_ranking']=ranked
    result['prediction_preservation_winner']=ranked[0]
    result['current_control_replay_verified']=True
    result['limitations']=['Single repeatedly used development split; fixed checkpoints; no new training',
        'Preserving predictions does not prove clinical accuracy or a reliable 85% classifier',
        'Shared resize remains; original input can already be lossy; phone-side processing unmeasured',
        'Output file sizes measured, but latency, bandwidth and storage policy not benchmarked']
    output=ROOT/'docs/ai/upload_recipes';output.mkdir(parents=True,exist_ok=True)
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('Preservation winner: '+ranked[0]+'. No training, app changes or final-test inference.',flush=True)


if __name__=='__main__':main()
