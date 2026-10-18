"""Prepare frozen train/validation PNG inputs only; never touches final-test photos."""
import hashlib
import json

try:
    from ai.enhancement_pipeline import ROOT,MANIFEST,CONTRACT,VARIANTS,prepare_input,expected_config
    from ai.baseline_data import load_baseline_data
except ModuleNotFoundError:
    from enhancement_pipeline import ROOT,MANIFEST,CONTRACT,VARIANTS,prepare_input,expected_config
    from baseline_data import load_baseline_data


def main():
    control=json.loads((ROOT/'ai/model_comparison_config.json').read_text())
    mapping,rows,_=load_baseline_data(control)
    if MANIFEST.exists():raise ValueError('Prepared version already exists; verify rather than overwrite')
    manifest={'contract':CONTRACT,'class_to_index':mapping,'rows':{},'test_pixels_read':0}
    for split in ('train','val'):
        manifest['rows'][split]=[]
        for row in rows[split]:
            content=(ROOT/row['local_path']).read_bytes()
            if hashlib.sha256(content).hexdigest()!=row['sha256']:raise ValueError('Source image changed')
            body=prepare_input(content)
            path=MANIFEST.parent/split/(row['sha256']+'.png')
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(body)
            source={k:row[k] for k in ('sha256','class_index','partition','target_class','local_path')}
            manifest['rows'][split].append({'source':source,'local_path':path.relative_to(ROOT).as_posix(),
                'sha256':hashlib.sha256(body).hexdigest(),'bytes':len(body)})
        print(split+': '+str(len(manifest['rows'][split]))+' prepared PNGs',flush=True)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    for variant in VARIANTS:
        path=ROOT/'ai'/('enhancement_'+variant+'_config.json')
        path.write_text(json.dumps(expected_config(control,variant),indent=2)+'\n',encoding='utf-8')
    print('All inputs checked, no drops; three locked trial configs created. Final-test pixels: zero.',flush=True)


if __name__=='__main__':main()
