"""Metadata-only readiness census; never opens photos or changes class scope."""
from collections import Counter,defaultdict
import hashlib
import json

try:
    from ai.audit_metadata import ROOT,load_locked_sources,read_csv,index_unique
    from ai.audit_scin_expansion import screen_case
    from ai.baseline_data import load_baseline_data
except ModuleNotFoundError:
    from audit_metadata import ROOT,load_locked_sources,read_csv,index_unique
    from audit_scin_expansion import screen_case
    from baseline_data import load_baseline_data


def main():
    registry,paths=load_locked_sources()
    control=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    mapping,_,dataset=load_baseline_data(control)
    cases=index_unique(read_csv(paths['scin_cases']),'case_id')
    labels=index_unique(read_csv(paths['scin_labels']),'case_id')
    if cases.keys()!=labels.keys():raise ValueError('Case/annotation identifiers differ')
    path_cases=defaultdict(set)
    for identity,case in cases.items():
        for i in (1,2,3):
            path=case.get(f'image_{i}_path','').strip()
            if path:path_cases[path].add(identity)
    shared={p for p,ids in path_cases.items() if len(ids)>1}
    strict=Counter()
    for identity,case in cases.items():
        screened=screen_case(case,labels[identity],shared)
        if screened['strict_screen']:strict[screened['top_label']]+=1
    rules=json.loads((ROOT/'ai/candidate_classes.json').read_text())['classes']
    photo_review=json.loads((ROOT/'ai/scin_photo_review.json').read_text())
    retained=Counter(r['target_candidate'] for r in photo_review['decisions']
                     if r['decision']=='candidate_for_research_preparation_only')
    old=json.loads((ROOT/'docs/ai/model_comparison/comparison-v1-efficientnet_b0/summary.json').read_text())
    latest=json.loads((ROOT/'docs/ai/efficientnet_tuning/tuning-v1-partial-freeze/summary.json').read_text())
    rows=[]
    for name,index in sorted(mapping.items(),key=lambda item:item[1]):
        rows.append({'condition':name,'frozen_images':dataset['per_class'][name],
            'full_control_f1':old['validation']['per_class'][index]['f1'],
            'partial_freezing_f1':latest['validation']['per_class'][index]['f1'],
            'scin_strict_metadata_cases':sum(strict[label] for label in rules[name]['scin']),
            'scin_reviewed_preparation_candidates':retained[name],
            'additional_training_approved':0})
    corrected=read_csv(paths['fitz_corrected_zenodo'])
    counts=defaultdict(Counter)
    for row in corrected:counts[row['label']][row['partition']]+=1
    replacement_labels=('lichen planus','pityriasis rosea','vitiligo','rosacea')
    replacements=[{'source_label':label,'metadata_partition_counts':dict(sorted(counts[label].items())),
                   'metadata_total':sum(counts[label].values()),'replacement_approved':False,
                   'images_acquired_for_this_candidate':0} for label in replacement_labels]
    summary={'scope':'Metadata-only readiness and exploratory replacement census',
        'source_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in paths.items()},
        'frozen_dataset_version':dataset['dataset_version'],'current_conditions':rows,
        'strict_scin_all_labels':dict(sorted(strict.items())),
        'exploratory_replacements':replacements,'test_pixels_read':0,'new_training_runs':0,
        'class_mapping_changed':False,'limitations':[
            'Metadata counts are not verified diagnoses, unique patients or approved training images',
            'SCIN strict weights are ranking weights; most current focus cases have one grader',
            'No replacement photos acquired or clinically reviewed; no replacement performance measured',
            'Frozen dataset visual review remains partial; patient independence unproven',
            'Current upload sanitation is not a validated model photo-quality or out-of-scope detector']}
    out=ROOT/'docs/ai/dataset_readiness';out.mkdir(parents=True,exist_ok=True)
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    for row in rows:
        print(f"{row['condition']}: train={row['frozen_images']['train']}, SCIN strict cases={row['scin_strict_metadata_cases']}, reviewed candidates={row['scin_reviewed_preparation_candidates']}")
    for row in replacements:print(row['source_label'],row['metadata_partition_counts'])
    print('No images opened, scope changes or training.')


if __name__=='__main__':main()
