"""Frozen development challenge for the production photo-admission function."""
from collections import Counter, defaultdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps/api'))
from app.photo_checks import check_photo, photo_quality, MODEL_PATH, VERSION
from app.store import RuleError

DATA = ROOT / 'ai/data/photo-validation-v1'
OUTPUT = ROOT / 'docs/ai/photo_checks/challenge-v1'
REVIEW = ROOT / 'ai/scin_photo_review.json'
MANIFEST = ROOT / 'ai/data/scin/review/image_manifest.json'
NEGATIVES = ROOT / 'ai/data/photo-check-negatives'
PROTOCOL = ROOT / 'docs/ai/PHOTO_VALIDATION_PROTOCOL.md'
EXPECTATIONS = {
    'original_skin': 'accept', 'dimmer': 'probe', 'brighter': 'probe',
    'severe_blur': 'reject', 'low_resolution': 'reject',
    'skin_screenshot': 'reject', 'cropped_skin_screenshot': 'probe',
    'object': 'reject', 'document': 'reject', 'dashboard': 'reject',
    'pattern': 'reject', 'black': 'reject', 'white': 'reject',
}
SKIN_GROUPS = ('original_skin','dimmer','brighter','severe_blur','low_resolution',
               'skin_screenshot','cropped_skin_screenshot')


def sha(data): return hashlib.sha256(data).hexdigest()


def verified_bytes(path, expected):
    body = path.read_bytes()
    if sha(body) != expected: raise ValueError(f'Source hash mismatch: {path.name}')
    return body


def png(image):
    clean=Image.new('RGB',image.size);clean.paste(image)
    buffer = BytesIO(); clean.save(buffer, format='PNG'); return buffer.getvalue()


def skin_variants(image):
    bounded = image.copy(); bounded.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    small = bounded.copy(); small.thumbnail((100, 100), Image.Resampling.LANCZOS)
    screen = Image.new('RGB', (1024, 800), '#eeeeee'); draw = ImageDraw.Draw(screen)
    draw.rectangle((0, 0, 1023, 65), fill='#263846')
    draw.text((25, 25), 'DEMO BROWSER | Skin image on a web page', fill='white')
    draw.text((25, 100), 'Synthetic screenshot fixture - not a camera photograph', fill='black')
    fitted = ImageOps.contain(bounded, (560, 600), Image.Resampling.LANCZOS)
    screen.paste(fitted, ((1024-fitted.width)//2, 150+(600-fitted.height)//2))
    return {
        'dimmer': ImageEnhance.Brightness(bounded).enhance(.65),
        'brighter': ImageEnhance.Brightness(bounded).enhance(1.35),
        'severe_blur': bounded.filter(ImageFilter.GaussianBlur(20)),
        'low_resolution': small, 'skin_screenshot': screen,
        'cropped_skin_screenshot': bounded,
    }


def negative_graphics():
    document = Image.new('RGB', (768, 768), 'white'); draw = ImageDraw.Draw(document)
    for y in range(25, 750, 22): draw.text((25, y), 'Fictional document: appointment records and sample text only. '*2, fill='black')
    dashboard = Image.new('RGB', (768, 768), '#eeeeee'); draw = ImageDraw.Draw(dashboard)
    draw.rectangle((0, 0, 767, 80), fill='#153c55'); draw.text((20, 30), 'SAMPLE APPLICATION DASHBOARD', fill='white')
    for y in range(130, 700, 110):
        draw.rectangle((40, y, 720, y+75), fill='white', outline='#444444', width=2)
        draw.text((60, y+20), 'Fictional appointment | Waiting | View record', fill='black')
    pattern = Image.new('RGB', (768, 768), '#aa7860'); draw = ImageDraw.Draw(pattern)
    for y in range(0, 768, 24):
        for x in range(0, 768, 24):
            if (x//24+y//24)%2: draw.rectangle((x, y, x+23, y+23), fill='#663f35')
    return {'document':document, 'dashboard':dashboard, 'pattern':pattern,
            'black':Image.new('RGB',(768,768),'black'), 'white':Image.new('RGB',(768,768),'white')}


def source_inputs():
    review = json.loads(REVIEW.read_text()); manifest_bytes = MANIFEST.read_bytes()
    if sha(manifest_bytes) != review['image_manifest_sha256']: raise ValueError('SCIN manifest changed')
    retained = {row['case_id']:row for row in review['decisions'] if row['decision']=='candidate_for_research_preparation_only'}
    manifest = json.loads(manifest_bytes)
    selected = [row for row in manifest if row['case_id'] in retained]
    if len(selected)!=37 or len(retained)!=37: raise ValueError('Expected exactly 37 retained skin sources')
    sources=[]
    for row in selected:
        if row['sha256']!=retained[row['case_id']]['image_sha256']: raise ValueError('Review image mismatch')
        path=(ROOT/row['local_path']).resolve()
        if not path.is_relative_to((ROOT/'ai/data/scin/review/images').resolve()): raise ValueError('Unexpected skin path')
        sources.append(('original_skin',row['case_id'],verified_bytes(path,row['sha256'])))
    negatives=json.loads((NEGATIVES/'manifest.json').read_text())
    if len(negatives)!=6: raise ValueError('Expected six existing object fixtures')
    for row in negatives:
        path=(NEGATIVES/row['name']).resolve()
        if path.parent!=NEGATIVES.resolve(): raise ValueError('Unexpected negative path')
        sources.append(('object',row['name'],verified_bytes(path,row['sha256'])))
    return sources


def evaluate(group, source_id, body):
    image_hash=sha(body)
    with Image.open(BytesIO(body)) as opened: image=ImageOps.exif_transpose(opened).convert('RGB')
    quality_reasons, metrics=photo_quality(image)
    try: decision=check_photo(body)
    except RuleError as error:
        if error.status!=422: raise
        decision={'accepted':False,'skin_content':'not_checked','reasons':[error.message],'version':VERSION}
    expected=EXPECTATIONS[group]
    disagreement=expected!='probe' and decision['accepted']!=(expected=='accept')
    return {'source_id':source_id,'group':group,'sha256':image_hash,'bytes':len(body),
            'width':image.width,'height':image.height,'expectation':expected,
            'disagreement':disagreement,'quality_reasons':quality_reasons,'quality_metrics':metrics,**decision}


def summarise(rows):
    groups=defaultdict(list)
    for row in rows: groups[row['group']].append(row)
    original={row['source_id']:row['accepted'] for row in rows if row['group']=='original_skin'}
    summary={}
    for group,items in groups.items():
        summary[group]={'count':len(items),'expectation':EXPECTATIONS[group],
            'accepted':sum(row['accepted'] for row in items),
            'quality_blocked':sum(not row['accepted'] and bool(row['quality_reasons']) for row in items),
            'content_blocked':sum(not row['accepted'] and not row['quality_reasons'] for row in items),
            'disagreements':sum(row['disagreement'] for row in items),
            'changed_from_original':sum(row['accepted']!=original[row['source_id']] for row in items if group!='original_skin' and row['source_id'] in original)}
        if summary[group]['accepted']+summary[group]['quality_blocked']+summary[group]['content_blocked']!=len(items):
            raise AssertionError('Group accounting mismatch')
    return summary


def main():
    sources=source_inputs(); DATA.mkdir(parents=True,exist_ok=True); OUTPUT.mkdir(parents=True,exist_ok=True)
    cases=[]
    for group,source_id,body in sources:
        cases.append((group,source_id,body))
        if group=='original_skin':
            with Image.open(BytesIO(body)) as opened: image=ImageOps.exif_transpose(opened).convert('RGB')
            cases.extend((name,source_id,png(variant)) for name,variant in skin_variants(image).items())
    cases.extend((name,f'synthetic-{name}',png(image)) for name,image in negative_graphics().items())
    if len(cases)!=270: raise AssertionError('Challenge count changed')
    contract={'protocol_sha256':sha(PROTOCOL.read_bytes()),'script_sha256':sha(Path(__file__).read_bytes()),
        'photo_checker_sha256':sha((ROOT/'apps/api/app/photo_checks.py').read_bytes()),
        'photos_helper_sha256':sha((ROOT/'apps/api/app/photos.py').read_bytes()),
        'model_sha256':sha(MODEL_PATH.read_bytes()),'review_sha256':sha(REVIEW.read_bytes()),
        'manifest_sha256':sha(MANIFEST.read_bytes()),'negative_manifest_sha256':sha((NEGATIVES/'manifest.json').read_bytes()),
        'version':VERSION,'real_source_count':len(sources),'check_count':len(cases),
        'cases':[{'group':g,'source_id':s,'sha256':sha(b)} for g,s,b in cases]}
    # Freeze all inputs before the first inference; never silently overwrite a different run.
    contract_path=OUTPUT/'contract.json'
    if contract_path.exists() and json.loads(contract_path.read_text())!=contract: raise ValueError('Frozen contract changed; use a separately reviewed version')
    contract_path.write_text(json.dumps(contract,indent=2)+'\n')
    rows=[]
    for index,(group,source_id,body) in enumerate(cases,1):
        if group!='original_skin' and group!='object': (DATA/f'{source_id}-{group}.png').write_bytes(body)
        rows.append(evaluate(group,source_id,body))
        if index%25==0: print(f'Checked {index}/{len(cases)}',flush=True)
    counts=Counter(row['group'] for row in rows)
    expected_counts=Counter({**{g:37 for g in SKIN_GROUPS},'object':6,
                             **{g:1 for g in negative_graphics()}})
    if counts!=expected_counts: raise AssertionError('Missing or additional challenge cases')
    previous=json.loads((ROOT/'docs/ai/photo_checks/development_checks.json').read_text())['examples']
    reference={row['case_id']:row['status']=='likely_skin' for row in previous if row['kind']=='skin'}
    original={row['source_id']:row['accepted'] for row in rows if row['group']=='original_skin'}
    if original!=reference: raise AssertionError('Original decisions no longer reproduce')
    summary=summarise(rows)
    result={'purpose':'Correlated development challenge, not independent or clinical validation',
        'contract_sha256':sha(contract_path.read_bytes()),'disease_test_images_read':0,
        'original_replay_matches':True,'groups':summary,'cases':rows}
    (OUTPUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    lines=['# Photo-admission development challenge results','',
        '270 checks from 43 real source images; derivatives are correlated. No pooled accuracy. No reserved disease-test images. Original decisions reproduce.','',
        '| Group | Checks | Accepted | Quality blocked | Content blocked | Expected-decision disagreements | Changed from original |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for group,item in summary.items():
        disagreements=str(item['disagreements']) if item['expectation']!='probe' else 'unlabelled probe'
        lines.append(f"| {group} | {item['count']} | {item['accepted']} | {item['quality_blocked']} | {item['content_blocked']} | {disagreements} | {item['changed_from_original']} |")
    lines+=['','## All expected-decision disagreements','']
    failures=[row for row in rows if row['disagreement']]
    lines.extend(f"- `{row['source_id']}` / {row['group']}: expected {row['expectation']}, {'accepted' if row['accepted'] else 'blocked'}; {', '.join(row['reasons']) or 'checks passed'}." for row in failures)
    if not failures: lines.append('None in this development challenge.')
    lines+=['','Brightness probes have no ground truth for clinical usability. Screenshots are synthetic; cropped screenshots intentionally preserve skin pixels. These are not independent patients. No verified skin-tone subgroup labels, expert quality labels or new phone capture dataset. No prompts/thresholds changed in response to this run. Full case hashes, decisions and quality metrics are in results.json.','']
    (OUTPUT/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
