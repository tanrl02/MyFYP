"""Offline, predeclared whole-frame context candidates; never imported by the API."""
from collections import defaultdict
from io import BytesIO
import json
from pathlib import Path

from PIL import Image,ImageDraw,ImageOps
from ai.evaluate_photo_validation import ROOT,DATA,sha,png,source_inputs,verified_bytes
from app.photo_checks import POSITIVE,NEGATIVE,MODEL_PATH,photo_quality
from app.photos import normalise_photo

OUTPUT=ROOT/'docs/ai/photo_checks/context-v1'
LOCAL=ROOT/'ai/data/photo-context-v1'
EXTRA=(
    'a screenshot of a web page containing a skin photograph',
    'a checkerboard pattern',
    'a screenshot of a medical application displaying a skin image')
RULES=('baseline','whole_frame','whole_frame_context')


def whole_view(image):
    fitted=ImageOps.contain(image,(224,224),Image.Resampling.BICUBIC)
    output=Image.new('RGB',(224,224),(127,127,127))
    output.paste(fitted,((224-fitted.width)//2,(224-fitted.height)//2))
    return output


def score_pass(positive,negative):return positive>=.22 and positive-negative>=.015


class ContextScorer:
    def __init__(self):
        import torch,clip
        expected=clip.clip._MODELS['ViT-B/32'].split('/')[-2]
        if sha(MODEL_PATH.read_bytes())!=expected:raise ValueError('Model hash mismatch')
        torch.set_num_threads(4)
        model,self.preprocess=clip.load(str(MODEL_PATH),device='cpu',jit=False);model.eval()
        with torch.inference_mode():
            text=model.encode_text(clip.tokenize(list(POSITIVE+NEGATIVE+EXTRA)))
            self.text=text/text.norm(dim=-1,keepdim=True)
        self.visual=model.visual.eval()

    def classify(self,image):
        import torch
        with torch.inference_mode():
            batch=torch.stack([self.preprocess(image),self.preprocess(whole_view(image))])
            features=self.visual(batch);features=features/features.norm(dim=-1,keepdim=True)
            scores=features@self.text.T
        p=len(POSITIVE);n=p+len(NEGATIVE)
        metrics={}
        for name,index,end in (('crop',0,n),('whole',1,n),('whole_context',1,len(POSITIVE+NEGATIVE+EXTRA))):
            positive=float(scores[index,:p].max());negative=float(scores[index,p:end].max())
            metrics[name]={'positive':positive,'negative':negative,'margin':positive-negative,
                           'passes':score_pass(positive,negative)}
        baseline=metrics['crop']['passes']
        return {'baseline':baseline,'whole_frame':baseline and metrics['whole']['passes'],
                'whole_frame_context':baseline and metrics['whole_context']['passes']},metrics


def novel_frame(image,split):
    if split=='development':
        output=Image.new('RGB',(1200,850),'#f2f2f2');draw=ImageDraw.Draw(output)
        draw.rectangle((0,0,1199,100),fill='#143e62')
        draw.text((25,35),'FICTIONAL CLINIC PORTAL | Example image viewer',fill='white')
        draw.rectangle((0,100,270,849),fill='#d6dfe4')
        for y,text in enumerate(('Home','Appointments','Images','Settings')):draw.text((30,160+y*90),text,fill='black')
        fitted=ImageOps.contain(image,(700,650),Image.Resampling.LANCZOS)
        output.paste(fitted,(300+(850-fitted.width)//2,140+(650-fitted.height)//2))
    else:
        output=Image.new('RGB',(720,1280),'#202020');draw=ImageDraw.Draw(output)
        draw.text((30,40),'9:41      Gallery - synthetic screen fixture',fill='white')
        draw.line((0,110,719,110),fill='white',width=2)
        fitted=ImageOps.contain(image,(660,900),Image.Resampling.LANCZOS)
        output.paste(fitted,((720-fitted.width)//2,150+(900-fitted.height)//2))
        draw.text((40,1160),'Share         Edit         Delete',fill='white')
    return output


def pattern(split,index):
    choices={'development':((12,'#508ba0','#204455'),(32,'#d0d0d0','#505050'),(48,'#b98a63','#684e37')),
             'validation':((17,'#9e7161','#372b25'),(29,'#e0b5b0','#724c52'),(53,'#91ac77','#374529'))}
    cell,a,b=choices[split][index];image=Image.new('RGB',(768,768),a);draw=ImageDraw.Draw(image)
    for y in range(0,768,cell):
        for x in range(0,768,cell):
            if (x//cell+y//cell)%2:draw.rectangle((x,y,x+cell-1,y+cell-1),fill=b)
    return image


def cases():
    sources=source_inputs();skins=sorted((row for row in sources if row[0]=='original_skin'),key=lambda row:sha(row[1].encode()))
    output=[]
    def add(split,group,source,body,known=None):
        output.append({'split':split,'group':group,'source_id':source,'body':body,'sha256':sha(body),'known_baseline':known})
    old=json.loads((ROOT/'docs/ai/photo_checks/challenge-v1/results.json').read_text())
    prior={(row['group'],row['source_id']):row for row in old['cases']}
    for index,(_,source,body) in enumerate(skins):
        split='development' if index<18 else 'validation'
        add(split,'skin',source,body,prior[('original_skin',source)]['accepted'])
        screen=(DATA/f'{source}-skin_screenshot.png').read_bytes()
        if sha(screen)!=prior[('skin_screenshot',source)]['sha256']:raise ValueError('Prior screenshot changed')
        add(split,'prior_screen',source,screen,prior[('skin_screenshot',source)]['accepted'])
        with Image.open(BytesIO(body)) as opened:image=ImageOps.exif_transpose(opened).convert('RGB')
        add(split,'novel_screen',source,png(novel_frame(image,split)))
    for _,source,body in sources:
        if ('object',source) in prior:add('development','object',source,body,prior[('object',source)]['accepted'])
    old_pattern=(DATA/'synthetic-pattern-pattern.png').read_bytes()
    if sha(old_pattern)!=prior[('pattern','synthetic-pattern')]['sha256']:raise ValueError('Prior pattern changed')
    add('development','pattern','prior-pattern',old_pattern,True)
    for source in json.loads((OUTPUT/'negative_sources.json').read_text()):
        path=(LOCAL/'negatives'/source['name']).resolve()
        if path.parent!=(LOCAL/'negatives').resolve():raise ValueError('Unexpected object path')
        add(source['split'],'object',source['name'],verified_bytes(path,source['sha256']))
    for split in ('development','validation'):
        for index in range(3):add(split,'pattern',f'{split}-pattern-{index}',png(pattern(split,index)))
    if len(output)!=128:raise AssertionError('Unexpected case count')
    return output


def summarise(rows):
    result={}
    for rule in RULES:
        groups=defaultdict(list)
        for row in rows:groups[row['group']].append(row)
        result[rule]={group:{'count':len(items),'accepted':sum(row['decisions'][rule] for row in items)} for group,items in groups.items()}
    return result


def guard(summary,rule,split):
    expected_skin=18 if split=='development' else 19
    candidate=summary[rule];baseline=summary['baseline']
    false_accepts=lambda data:sum(data[group]['accepted'] for group in ('prior_screen','novel_screen','pattern'))
    return {'passes':candidate['skin']['accepted']==expected_skin and candidate['object']['accepted']==0 and false_accepts(candidate)<false_accepts(baseline),
            'skin_accepted':candidate['skin']['accepted'],'object_accepted':candidate['object']['accepted'],
            'screen_pattern_accepted':false_accepts(candidate),'baseline_screen_pattern_accepted':false_accepts(baseline)}


def main():
    fixtures=cases();LOCAL.mkdir(parents=True,exist_ok=True);OUTPUT.mkdir(parents=True,exist_ok=True)
    contract={'script_sha256':sha(Path(__file__).read_bytes()),
        'protocol_sha256':sha((ROOT/'docs/ai/PHOTO_CONTEXT_PROTOCOL.md').read_bytes()),
        'model_sha256':sha(MODEL_PATH.read_bytes()),
        'production_sha256':sha((ROOT/'apps/api/app/photo_checks.py').read_bytes()),
        'prior_results_sha256':sha((ROOT/'docs/ai/photo_checks/challenge-v1/results.json').read_bytes()),
        'negative_manifest_sha256':sha((OUTPUT/'negative_sources.json').read_bytes()),
        'extra_prompts':EXTRA,'cases':[{key:row[key] for key in ('split','group','source_id','sha256')} for row in fixtures]}
    contract=json.loads(json.dumps(contract))
    path=OUTPUT/'contract.json'
    if path.exists() and json.loads(path.read_text())!=contract:raise ValueError('Frozen context contract changed')
    path.write_text(json.dumps(contract,indent=2)+'\n')
    model=ContextScorer();all_rows=[];summaries={};selection=None
    for split in ('development','validation'):
        rows=[]
        for fixture in (row for row in fixtures if row['split']==split):
            body=fixture['body']
            normalise_photo(body)  # Preserve the production upload/decode boundaries.
            with Image.open(BytesIO(body)) as opened:image=ImageOps.exif_transpose(opened).convert('RGB')
            reasons,_=photo_quality(image)
            decisions,metrics=({rule:False for rule in RULES},{}) if reasons else model.classify(image)
            if fixture['known_baseline'] is not None and decisions['baseline']!=fixture['known_baseline']:
                raise AssertionError('Known baseline no longer reproduces')
            row={key:value for key,value in fixture.items() if key!='body'}
            row.update(decisions=decisions,metrics=metrics,quality_reasons=reasons)
            rows.append(row)
            (LOCAL/f"{split}-{fixture['group']}-{fixture['source_id']}.png").write_bytes(body)
        summaries[split]=summarise(rows);all_rows+=rows
        if split=='development':
            guards={rule:guard(summaries[split],rule,split) for rule in RULES[1:]}
            eligible=[rule for rule in RULES[1:] if guards[rule]['passes']]
            selection=min(eligible,key=lambda rule:(guards[rule]['screen_pattern_accepted'],RULES.index(rule))) if eligible else None
            selection_record={'selected':selection,'development_guards':guards,
                              'development_rows_sha256':sha(json.dumps(rows,sort_keys=True).encode()),
                              'frozen_before_validation':True}
            (OUTPUT/'selection.json').write_text(json.dumps(selection_record,indent=2)+'\n')
            print('Development selection frozen:',selection,flush=True)
        else:
            if json.loads((OUTPUT/'selection.json').read_text())['selected']!=selection:raise AssertionError('Selection changed')
            print('Validation challenge completed',flush=True)
    validation_guards={rule:guard(summaries['validation'],rule,'validation') for rule in RULES[1:]}
    results={'contract_sha256':sha(path.read_bytes()),'selected_on_development':selection,
        'validation_guards':validation_guards,'passes_both_guards':bool(selection and validation_guards[selection]['passes']),
        'production_promoted':False,'disease_test_images_read':0,'groups':summaries,'cases':all_rows}
    (OUTPUT/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    lines=['# Whole-frame context experiment','',
           'Offline only. Skin sources were previously seen. Validation negatives/layouts are a small new challenge, not clinical validation.','',
           '| Split | Rule | Skin accepted | Objects accepted | Prior screens accepted | Novel screens accepted | Patterns accepted |',
           '|---|---|---:|---:|---:|---:|---:|']
    for split,summary in summaries.items():
        for rule,groups in summary.items():
            cells=[f"{groups[g]['accepted']}/{groups[g]['count']}" for g in ('skin','object','prior_screen','novel_screen','pattern')]
            lines.append(f"| {split} | {rule} | {' | '.join(cells)} |")
    lines+=['',f'Development selection: {selection or "none"}. Both technical guards passed: {results["passes_both_guards"]}. Live gate unchanged.','']
    (OUTPUT/'RESULTS.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'selected':selection,'validation_guards':validation_guards,'groups':summaries},indent=2))


if __name__=='__main__':main()
