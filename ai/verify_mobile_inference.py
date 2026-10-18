"""Integration replay on three existing public development photos, never final-test data."""
from io import BytesIO
import json
from pathlib import Path
import sys
from uuid import uuid4
from unittest.mock import patch
from PIL import Image,ImageOps
import torch
from torchvision.models import efficientnet_b0,EfficientNet_B0_Weights

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'apps/api'))
from fastapi.testclient import TestClient
from app.main import create_app
from app.disease_model import CONFIG,DiseaseModel
from app.store import RuleError
from ai.evaluate_photo_validation import source_inputs,sha


def main():
    config=json.loads(CONFIG.read_text());checkpoint_path=ROOT/config['checkpoint_path']
    if sha(checkpoint_path.read_bytes())!=config['checkpoint_sha256']:raise AssertionError('Checkpoint changed')
    checkpoint=torch.load(checkpoint_path,map_location='cpu',weights_only=True)
    reference=efficientnet_b0(weights=None)
    reference.classifier[-1]=torch.nn.Linear(reference.classifier[-1].in_features,8)
    reference.load_state_dict(checkpoint['model_state_dict']);reference.eval()
    transform=EfficientNet_B0_Weights.IMAGENET1K_V1.transforms()
    path=ROOT/'tmp'/f'inference-verification-{uuid4()}.sqlite3'
    patient={'X-Demo-Actor':'patient-ava'};other={'X-Demo-Actor':'patient-noah'}
    client=TestClient(create_app(path));evidence=[];first=None
    for index,(_,case_id,body) in enumerate(row for row in source_inputs() if row[0]=='original_skin'):
        if index==3:break
        with Image.open(BytesIO(body)) as source:image=ImageOps.exif_transpose(source).convert('RGB')
        with torch.inference_mode():expected=reference(transform(image).unsqueeze(0)).softmax(dim=1)[0]
        preflight=client.post('/photo-check',headers=patient,files={'photo':('dev.png',body,'image/png')})
        if preflight.status_code!=200 or not preflight.json()['accepted']:raise AssertionError('Known usable development skin rejected')
        response=client.post('/assessments',headers=patient,data={'request_id':f'integration-replay-{index}'},files={'photo':('dev.png',body,'image/png')})
        if response.status_code!=201:raise AssertionError(response.text)
        saved=response.json();prediction=saved['prediction']
        if prediction['checkpoint_sha256']!=config['checkpoint_sha256'] or prediction['input_sha256']!=sha(body):raise AssertionError('Wrong model/input identity')
        indices=sorted(range(8),key=lambda value:(-float(expected[value]),value))[:3]
        actual=prediction['top_predictions']
        for item,label_index in zip(actual,indices,strict=True):
            if item['condition']!=list(config['class_to_index'])[label_index] or abs(item['score']-float(expected[label_index]))>1e-6:
                raise AssertionError('API prediction differs from independent model forward')
        reopened=TestClient(create_app(path))
        if reopened.get(f"/assessments/{saved['id']}",headers=patient).json()!=saved:raise AssertionError('Reopen changed saved prediction')
        if reopened.get(f"/assessments/{saved['id']}",headers=other).status_code!=404:raise AssertionError('Another patient saw prediction')
        evidence.append({'case_id':case_id,'input_sha256':sha(body),'reference_matches':True,
                         'prediction':prediction,'reopen_matches':True,'other_patient_denied':True})
        if first is None:first=(saved,body)
    # A damaged/missing checkpoint fails closed, without a silent example result.
    failing=TestClient(create_app(path,photo_checker=lambda body:{'accepted':True}))
    before=len(client.get('/assessments',headers=patient).json())
    with patch('app.disease_model._model',None),patch('app.disease_model.DiseaseModel',side_effect=ValueError('hash mismatch')):
        bad=failing.post('/assessments',headers=patient,data={'request_id':'missing-model-replay'},files={'photo':('x.png',first[1],'image/png')})
        if bad.status_code!=503:raise AssertionError('Corrupt model did not fail closed')
    if len(client.get('/assessments',headers=patient).json())!=before:raise AssertionError('Failed inference saved a row')
    output=ROOT/'docs/ai/mobile_integration';output.mkdir(parents=True,exist_ok=True)
    result={'purpose':'Integration replay, not disease accuracy evaluation','runtime_contract_sha256':sha(CONFIG.read_bytes()),
        'model_id':config['model_id'],'checkpoint_sha256':config['checkpoint_sha256'],
        'independent_forward_comparisons':3,'missing_model_fails_closed':True,'cases':evidence,
        'disease_final_test_images_read':0,'live_database_written':False}
    (output/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Three real API/model forwards match; reopen/isolation and corrupt-model failure verified. No live rows written.')


if __name__=='__main__':main()
