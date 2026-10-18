"""Audit all challenge evidence and replay one representative per category."""
import json
from ai.evaluate_photo_validation import (
    ROOT,DATA,OUTPUT,REVIEW,MANIFEST,NEGATIVES,PROTOCOL,MODEL_PATH,
    source_inputs,summarise,sha,evaluate,
)


def main():
    contract_body=(OUTPUT/'contract.json').read_bytes();contract=json.loads(contract_body)
    results=json.loads((OUTPUT/'results.json').read_text())
    paths={'protocol_sha256':PROTOCOL,'script_sha256':ROOT/'ai/evaluate_photo_validation.py',
        'photo_checker_sha256':ROOT/'apps/api/app/photo_checks.py',
        'photos_helper_sha256':ROOT/'apps/api/app/photos.py','model_sha256':MODEL_PATH,
        'review_sha256':REVIEW,'manifest_sha256':MANIFEST,
        'negative_manifest_sha256':NEGATIVES/'manifest.json'}
    for key,path in paths.items():
        if sha(path.read_bytes())!=contract[key]:raise AssertionError(f'Changed dependency: {key}')
    if results['contract_sha256']!=sha(contract_body):raise AssertionError('Contract hash mismatch')
    sources={(group,source):body for group,source,body in source_inputs()}
    rows=results['cases'];keys=[(row['group'],row['source_id']) for row in rows]
    if len(rows)!=270 or len(set(keys))!=270:raise AssertionError('Missing/duplicate results')
    for frozen,row in zip(contract['cases'],rows,strict=True):
        if any(frozen[key]!=row[key] for key in ('group','source_id','sha256')):raise AssertionError('Case identity mismatch')
        body=sources.get((row['group'],row['source_id']))
        if body is None:body=(DATA/f"{row['source_id']}-{row['group']}.png").read_bytes()
        if sha(body)!=row['sha256'] or len(body)!=row['bytes']:raise AssertionError('Case bytes changed')
    if summarise(rows)!=results['groups']:raise AssertionError('Summary mismatch')
    selected={}
    for row in rows:
        group=row['group']
        if group not in selected:selected[group]=row
        if group in ('dimmer','brighter') and not row['accepted']:selected[group]=row
        if group=='skin_screenshot' and row['accepted']:selected[group]=row
    replay=[]
    for group,row in selected.items():
        body=sources.get((group,row['source_id']))
        if body is None:body=(DATA/f"{row['source_id']}-{group}.png").read_bytes()
        if evaluate(group,row['source_id'],body)!=row:raise AssertionError(f'Replay mismatch: {group}')
        replay.append({'group':group,'source_id':row['source_id'],'matches':True})
    evidence={'all_270_case_hashes_verified':True,'all_dependency_hashes_verified':True,
        'summary_accounting_verified':True,'representative_replays':replay,
        'results_sha256':sha((OUTPUT/'results.json').read_bytes()),
        'contract_sha256':sha(contract_body),'disease_test_images_read':0}
    (OUTPUT/'verification.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(f'All 270 case hashes and accounting verified; {len(replay)} category replays match.')


if __name__=='__main__':main()
