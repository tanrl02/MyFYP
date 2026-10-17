"""Aggregate only independently verified matched-model runs; never reads images."""
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    config=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    output=ROOT/'docs/ai/model_comparison'
    rows=[]
    for architecture in config['architectures']:
        path=output/('comparison-v1-'+architecture)/'summary.json'
        result=json.loads(path.read_text())
        if result['architecture']!=architecture or result['run']['config']!=config:
            raise ValueError('Mismatched architecture/protocol')
        if not result['validation_replay_verified'] or not result['frozen_batchnorm_verified'] or not result['features_updated']:
            raise ValueError('Incomplete checkpoint verification')
        if result['test_images_evaluated']!=0: raise ValueError('Test evaluation forbidden in this development comparison')
        metrics=result['validation']
        if sum(row['support'] for row in metrics['per_class'])!=193: raise ValueError('Wrong validation support')
        rows.append({'architecture':architecture,'run_id':result['run_id'],'best_epoch':result['best_epoch'],
            'epochs_completed':result['epochs_completed'],'accuracy':metrics['accuracy'],'macro_f1':metrics['macro_f1'],
            'macro_precision':result['macro_precision'],'loss':metrics['loss'],'per_class':metrics['per_class'],
            'confusion_matrix':metrics['confusion_matrix'],'parameters':result['run']['parameters'],
            'epoch_seconds':result['epoch_seconds'],'checkpoint_sha256':result['checkpoint_sha256']})
    ranked=sorted(rows,key=lambda r:(r['accuracy'],r['macro_f1'],-r['loss']),reverse=True)
    baseline=json.loads((ROOT/'docs/ai/finetune_results/summary.json').read_text())
    summary={'protocol':config,'validation_images':193,'training_images':1374,'test_images_evaluated':0,
        'class_to_index':baseline['environment']['class_to_index'], 'matched_runs':ranked,
        'winner':ranked[0]['run_id'],'accuracy_target_reached':ranked[0]['accuracy']>=config['accuracy_target'],
        'target_minimum_correct':math.ceil(193*config['accuracy_target']),
        'prior_user_selected_model':{'run_id':baseline['run_id'],'accuracy':baseline['finetuned']['accuracy'],
            'macro_f1':baseline['finetuned']['macro_f1'],'macro_precision':baseline['finetuned_macro_precision'],
            'note':'Historical comparison only; training protocol differs'},
        'scin_images_included':0,'limitations':['Single seed and one repeatedly used development split',
            'No independent clinical diagnoses, patient-independence or real-phone performance established',
            'Pretrained weights and inherent model regularisation differ; not architecture-only causation',
            'The 85% target is evaluated on all193 images without selective rejection or excluded failed classes']}
    (output/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n')
    for row in ranked:
        print(f"{row['architecture']}: accuracy={row['accuracy']:.4%}, macro_precision={row['macro_precision']:.4%}, macroF1={row['macro_f1']:.4f}, epoch={row['best_epoch']}/{row['epochs_completed']}")
    print('85% validation accuracy target reached: '+str(summary['accuracy_target_reached']))


if __name__=='__main__':main()
