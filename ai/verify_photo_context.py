"""Audit the frozen context experiment and replay selected borderline/failure cases."""
from io import BytesIO
import json
from PIL import Image,ImageOps
from ai.photo_context_experiment import (
    ROOT,OUTPUT,MODEL_PATH,ContextScorer,cases,guard,summarise,sha,RULES,
)
from app.photo_checks import photo_quality


def main():
    contract_body=(OUTPUT/'contract.json').read_bytes();contract=json.loads(contract_body)
    result=json.loads((OUTPUT/'results.json').read_text());selection=json.loads((OUTPUT/'selection.json').read_text())
    dependencies={'script_sha256':ROOT/'ai/photo_context_experiment.py',
        'protocol_sha256':ROOT/'docs/ai/PHOTO_CONTEXT_PROTOCOL.md','model_sha256':MODEL_PATH,
        'production_sha256':ROOT/'apps/api/app/photo_checks.py',
        'prior_results_sha256':ROOT/'docs/ai/photo_checks/challenge-v1/results.json',
        'negative_manifest_sha256':OUTPUT/'negative_sources.json'}
    for key,path in dependencies.items():
        if sha(path.read_bytes())!=contract[key]:raise AssertionError(f'Changed dependency {key}')
    if sha(contract_body)!=result['contract_sha256']:raise AssertionError('Contract hash mismatch')
    fixtures=cases();rows=result['cases']
    if len(rows)!=128:raise AssertionError('Unexpected row count')
    keys=lambda row:(row['split'],row['group'],row['source_id'])
    indexed={keys(row):row for row in rows}
    if len(indexed)!=128:raise AssertionError('Duplicate results')
    for frozen,fixture in zip(contract['cases'],fixtures,strict=True):
        row=indexed[keys(fixture)]
        if any(frozen[key]!=fixture[key] or row[key]!=fixture[key] for key in ('split','group','source_id','sha256')):
            raise AssertionError('Fixture identity or bytes changed')
        if fixture['known_baseline'] is not None and row['decisions']['baseline']!=fixture['known_baseline']:
            raise AssertionError('Prior baseline mismatch')
    development=[row for row in rows if row['split']=='development']
    if sha(json.dumps(development,sort_keys=True).encode())!=selection['development_rows_sha256']:
        raise AssertionError('Selection does not match development rows')
    for split in ('development','validation'):
        summary=summarise([row for row in rows if row['split']==split])
        if summary!=result['groups'][split]:raise AssertionError('Group totals mismatch')
        guards={rule:guard(summary,rule,split) for rule in RULES[1:]}
        if guards!=(selection['development_guards'] if split=='development' else result['validation_guards']):
            raise AssertionError('Guard mismatch')
    eligible=[rule for rule in RULES[1:] if selection['development_guards'][rule]['passes']]
    winner=min(eligible,key=lambda rule:(selection['development_guards'][rule]['screen_pattern_accepted'],RULES.index(rule))) if eligible else None
    if winner!=selection['selected'] or winner!=result['selected_on_development']:raise AssertionError('Wrong selection')
    if result['passes_both_guards']!=bool(winner and result['validation_guards'][winner]['passes']):raise AssertionError('Wrong conclusion')
    chosen={}
    for row in rows:
        chosen.setdefault((row['split'],row['group']),row)
        if row['group']=='skin' and row['decisions']['baseline'] and not row['decisions']['whole_frame']:
            chosen[('validation','skin_false_rejection')]=row
    model=ContextScorer();replays=[]
    source_map={keys(fixture):fixture for fixture in fixtures}
    for row in chosen.values():
        body=source_map[keys(row)]['body']
        with Image.open(BytesIO(body)) as opened:image=ImageOps.exif_transpose(opened).convert('RGB')
        reasons,_=photo_quality(image)
        decisions=({rule:False for rule in RULES} if reasons else model.classify(image)[0])
        if decisions!=row['decisions'] or reasons!=row['quality_reasons']:raise AssertionError('Replay mismatch')
        replays.append({'split':row['split'],'group':row['group'],'source_id':row['source_id'],'matches':True})
    audit={'all_128_fixtures_and_dependencies_verified':True,'all_known_baselines_reproduced':True,
        'selection_and_group_accounting_verified':True,'representative_replays':replays,
        'results_sha256':sha((OUTPUT/'results.json').read_bytes()),'production_promoted':False,
        'disease_test_images_read':0}
    (OUTPUT/'verification.json').write_text(json.dumps(audit,indent=2)+'\n')
    print(f'All 128 fixtures, selection and totals verified; {len(replays)} decision replays match.')


if __name__=='__main__':main()
