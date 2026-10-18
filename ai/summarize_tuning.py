"""Summarise two predeclared trials against the verified B0 control; no pixels."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads((ROOT/path).read_text(encoding='utf-8'))


def main():
    base=read('ai/model_comparison_config.json')
    control=read('docs/ai/model_comparison/comparison-v1-efficientnet_b0/summary.json')
    if control['run']['config']!=base:raise ValueError('Control protocol changed')
    control_epochs=read('docs/ai/model_comparison/comparison-v1-efficientnet_b0/epochs.json')
    rows=[]
    for label,folder in [('Control','docs/ai/model_comparison/comparison-v1-efficientnet_b0'),
                         ('Lower LR, full','docs/ai/efficientnet_tuning/tuning-v1-lower-lr-full'),
                         ('Partial freezing','docs/ai/efficientnet_tuning/tuning-v1-partial-freeze')]:
        result=read(folder+'/summary.json');run=result['run']
        if result['architecture']!='efficientnet_b0' or result['test_images_evaluated']!=0:
            raise ValueError('Wrong architecture or test evaluation')
        if not all(result[k] for k in ('validation_replay_verified','frozen_batchnorm_verified','features_updated')):
            raise ValueError('Checkpoint verification missing')
        for key in ('class_to_index','dataset_lock','pretrained_sha256','train_transform','validation_transform'):
            if run[key]!=control['run'][key]:raise ValueError('Unmatched control field: '+key)
        if label!='Control':
            variant=run['config']['tuning_variant']
            expected=read('ai/tuning_'+variant+'_config.json')
            if run['config']!=expected:raise ValueError('Wrong tuning config')
            history=read(folder+'/epochs.json')
            for actual,reference in zip(history[:3],control_epochs[:3]):
                a,b=actual['validation'],reference['validation']
                for key in ('accuracy','macro_f1','per_class','confusion_matrix'):
                    if a[key]!=b[key]:raise ValueError('Warm-up does not match control')
                if not math.isclose(a['loss'],b['loss'],rel_tol=1e-6,abs_tol=1e-6):raise ValueError('Warm-up loss mismatch')
            if variant=='partial_freeze' and result.get('changed_feature_blocks')!={'6':True,'7':True,'8':True}:
                raise ValueError('Upper-block updates missing')
        metrics=result['validation']
        if sum(m['support'] for m in metrics['per_class'])!=193:raise ValueError('Validation support changed')
        correct=sum(metrics['confusion_matrix'][i][i] for i in range(8))
        if metrics['accuracy']!=correct/193:raise ValueError('Inconsistent accuracy')
        rows.append({'label':label,'run_id':result['run_id'],'accuracy':metrics['accuracy'],
            'correct':correct,'macro_precision':result['macro_precision'],'macro_f1':metrics['macro_f1'],
            'loss':metrics['loss'],'per_class':metrics['per_class'],'confusion_matrix':metrics['confusion_matrix'],
            'best_epoch':result['best_epoch'],'epochs_completed':result['epochs_completed'],
            'epoch_seconds':result['epoch_seconds'],'checkpoint_sha256':result['checkpoint_sha256']})
    ranked=sorted(rows,key=lambda r:(r['accuracy'],r['macro_f1'],-r['loss']),reverse=True)
    summary={'experiment':'efficientnet-tuning-v1','training_images':1374,'validation_images':193,
        'test_images_evaluated':0,'scin_images_included':0,'warmup_metrics_match_control':True,
        'class_to_index':control['run']['class_to_index'],'trials':rows,'winner':ranked[0]['run_id'],
        'accuracy_target':.85,'accuracy_target_reached':ranked[0]['accuracy']>=.85,
        'improves_control_accuracy':ranked[0]['accuracy']>rows[0]['accuracy'],
        'limitations':['One seed; repeatedly consulted development set; final test reserved',
            'Frozen lower blocks disable their stochastic depth; not identical post-warm-up random views',
            'No real-phone or clinical validation; no app model change']}
    output=ROOT/'docs/ai/efficientnet_tuning';output.mkdir(exist_ok=True)
    (output/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    for row in rows:print(f"{row['label']}: {row['accuracy']:.2%} ({row['correct']}/193), F1 {row['macro_f1']:.4f}")
    print('Winner: '+summary['winner']+'; 85% target reached: '+str(summary['accuracy_target_reached']))


if __name__=='__main__':main()
