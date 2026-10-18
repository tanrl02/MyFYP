"""Aggregate verified enhancement trials and enforce the predeclared replication rule."""
import json

try:
    from ai.enhancement_pipeline import ROOT,MANIFEST,VARIANTS,digest,expected_config
    from ai.enhancement_evaluation import candidate_guard
except ModuleNotFoundError:
    from enhancement_pipeline import ROOT,MANIFEST,VARIANTS,digest,expected_config
    from enhancement_evaluation import candidate_guard


def main():
    folder=ROOT/'docs/ai/enhancement'
    control=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    def load(variant,seed):
        name='enhancement-v1-'+variant.replace('_','-')+'-s'+str(seed)
        result=json.loads((folder/name/'summary.json').read_text())
        if result['run']['config']!=expected_config(control,variant,seed):raise ValueError('Unmatched enhancement config')
        if not all(result[k] for k in ('validation_replay_verified','frozen_batchnorm_verified','features_updated')):
            raise ValueError('Missing checkpoint verification')
        if result['test_images_evaluated']!=0 or sum(m['support'] for m in result['validation']['per_class'])!=193:
            raise ValueError('Unexpected evaluation cases')
        if set(result['lighting_probes'])!={'0.8','1.2'}:raise ValueError('Wrong lighting probes')
        for probe in result['lighting_probes'].values():
            if sum(m['support'] for m in probe['per_class'])!=193:raise ValueError('Probe support differs')
        return result
    initial={variant:load(variant,3403) for variant in VARIANTS}
    guards={variant:candidate_guard(initial['baseline'],initial[variant]) for variant in VARIANTS[1:]}
    passing=[v for v in VARIANTS[1:] if guards[v]['passes']]
    selected=max(passing,key=lambda v:(initial[v]['validation']['accuracy'],initial[v]['validation']['macro_f1'],
                 -initial[v]['validation']['loss'])) if passing else None
    replication={'performed':False,'seed':3404}
    repeated={}
    if selected:
        repeated={v:load(v,3404) for v in ('baseline',selected)}
        replication.update(performed=True,variant=selected,guard=candidate_guard(repeated['baseline'],repeated[selected]))
    def row(variant,result):
        return {'variant':variant,'run_id':result['run_id'],'seed':result['run']['config']['seed'],
            'validation':result['validation'],'macro_precision':result['macro_precision'],
            'lighting_probe_mean_accuracy':result['lighting_probe_mean_accuracy'],
            'lighting_probes':{key:{'accuracy':m['accuracy'],'macro_f1':m['macro_f1']} for key,m in result['lighting_probes'].items()},
            'best_epoch':result['best_epoch'],'epochs_completed':result['epochs_completed'],
            'checkpoint_sha256':result['checkpoint_sha256'],'epoch_seconds':result['epoch_seconds']}
    verified=bool(selected and replication['guard']['passes'])
    summary={'experiment':'enhancement-v1','prepared_manifest_sha256_lf':digest(MANIFEST),
        'training_images':1374,'validation_images':193,'test_images_evaluated':0,
        'initial_runs':[row(v,initial[v]) for v in VARIANTS],'initial_guards':guards,
        'initial_passing_candidate':selected,'replication':replication,
        'replication_runs':[row(v,r) for v,r in repeated.items()],
        'replicated_guard_benefit':verified,'recommended_enhancement':selected if verified else None,
        'any_clean_accuracy_at_least_85_percent':any(r['validation']['accuracy']>=.85 for r in (*initial.values(),*repeated.values())),
        'decision':'Replicated development benefit; final/phone validation still required' if verified else
            ('Initial benefit did not replicate under preset guard' if selected else 'No enhancement passed the preset initial guard'),
        'limitations':['Repeatedly used validation set; not final test or clinical validation',
            'Lighting probes reuse193 cases and simulate brightness only, not real camera conditions',
            '10-point class recall guard is an engineering choice on small supports',
            'All eight labels/source splits preserved; no SCIN additions; no app model changed']}
    (folder/'comparison.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    for record in (*summary['initial_runs'],*summary['replication_runs']):
        print(f"{record['variant']} seed{record['seed']}: accuracy {record['validation']['accuracy']:.2%}, F1 {record['validation']['macro_f1']:.4f}, probes {record['lighting_probe_mean_accuracy']:.2%}")
    print(summary['decision'])


if __name__=='__main__':main()
