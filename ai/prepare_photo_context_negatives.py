"""Acquire four licensed public challenge fixtures; no user photos uploaded."""
import ast
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'ai/data/photo-context-v1/negatives'
BASE='https://raw.githubusercontent.com/scikit-image/scikit-image/v0.25.2/skimage/data/'
LICENCES={
    'camera.png':('development','CC0; Lav Varshney; distant person/camera, not a skin close-up'),
    'eagle.png':('development','CC0; Dayane Machado'),
    'clock_motion.png':('validation','Public domain; Stefan van der Walt'),
    'horse.png':('validation','CC0; Andreas Preuss (marauder)')}


def main():
    TARGET.mkdir(parents=True,exist_ok=True)
    registry_body=urllib.request.urlopen(BASE+'_registry.py',timeout=60).read()
    tree=ast.parse(registry_body)
    registry=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                  and any(isinstance(target,ast.Name) and target.id=='registry' for target in node.targets))
    urls=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
              and any(isinstance(target,ast.Name) and target.id=='registry_urls' for target in node.targets))
    (TARGET/'_registry.py').write_bytes(registry_body)
    for name in ('_fetchers.py','README.txt'):
        (TARGET/name).write_bytes(urllib.request.urlopen(BASE+name,timeout=60).read())
    manifest=[]
    for name,(split,licence) in LICENCES.items():
        expected=registry['data/'+name];path=TARGET/name
        url=urls.get('data/'+name,BASE+name)
        body=path.read_bytes() if path.exists() else urllib.request.urlopen(url,timeout=60).read()
        if hashlib.sha256(body).hexdigest()!=expected:raise ValueError(f'Upstream hash mismatch: {name}')
        path.write_bytes(body)
        manifest.append({'name':name,'split':split,'licence_note':licence,'url':url,'sha256':expected})
    output=ROOT/'docs/ai/photo_checks/context-v1'
    output.mkdir(parents=True,exist_ok=True)
    (output/'negative_sources.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Four public fixtures verified; source notices retained locally.')


if __name__=='__main__':main()
