from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from io import BytesIO
import sqlite3
import unittest
from unittest.mock import Mock
from PIL import Image
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_workflow as workflow


def prediction(condition='eczema',model_id='test-model-v1'):
    return {'model_id':model_id,'checkpoint_sha256':'a'*64,'preprocessing':'test-contract',
        'dataset_version':'test-eight','validation_accuracy':.5958549222797928,
        'validation_macro_f1':.5214,'validation_cases':193,'test_evaluated':False,
        'input_sha256':'b'*64,'created_at':'2026-10-18T00:00:00+00:00',
        'top_predictions':[{'condition':condition,'label':condition.title(),'score':.55},
                           {'condition':'psoriasis','label':'Psoriasis','score':.25},
                           {'condition':'acne','label':'Acne','score':.1}]}


class PredictionTests(unittest.TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.predict=Mock(return_value=prediction())
        self.client=TestClient(create_app(self.path,photo_checker=lambda body:{'accepted':True},predictor=self.predict))
        image=Image.new('RGB',(384,384),(120,90,60));buffer=BytesIO();image.save(buffer,format='PNG');self.body=buffer.getvalue()

    def upload(self,actor=None,body=None):
        return self.client.post('/assessments',headers=actor or self.patient,
            data={'request_id':'prediction-request-one'},files={'photo':('image.png',body or self.body,'image/png')})

    def test_prediction_snapshot_reopen_retry_and_patient_isolation(self):
        saved=self.upload().json();self.assertEqual(saved['origin'],'experimental_ai')
        self.assertEqual(saved['prediction'],prediction());self.assertIsNone(saved['example_category'])
        self.assertEqual(self.predict.call_args.args[0],self.body)
        self.predict.side_effect=RuleError('Unavailable',503)
        self.assertEqual(self.upload().json(),saved);self.assertEqual(self.predict.call_count,1)
        self.assertEqual(self.upload(body=b'different image').status_code,409)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/assessments/{saved['id']}",headers=self.patient).json(),saved)
        self.assertEqual(reopened.get('/assessments',headers=self.patient).json()[0]['prediction'],prediction())
        self.assertEqual(reopened.get('/assessments',headers=self.other).json(),[])
        self.assertEqual(reopened.get(f"/assessments/{saved['id']}",headers=self.other).status_code,404)

    def test_model_failure_or_rejected_photo_never_creates_simulation_fallback(self):
        self.predict.side_effect=RuleError('Model unavailable',503)
        self.assertEqual(self.upload().status_code,503)
        self.assertEqual(Store(self.path).assessments('patient-ava'),[])
        self.predict.reset_mock()
        self.client=TestClient(create_app(self.path,photo_checker=lambda body:{'accepted':False,'reasons':['retake']},predictor=self.predict))
        self.assertEqual(self.upload().status_code,422);self.predict.assert_not_called()
        self.assertEqual(self.upload(actor=self.staff).status_code,403)
        self.assertEqual(Store(self.path).assessments('patient-ava'),[])

    def test_authorized_doctor_receives_same_snapshot_and_matching_uses_saved_class(self):
        saved=self.upload().json();store=Store(self.path)
        store.save_doctor_profile('doctor-anita','Fictional dermatology',['eczema'],0)
        result=store.doctor_matches('patient-ava',assessment_id=saved['id'])
        self.assertEqual(result['source'],'experimental_ai');self.assertEqual(result['concern'],'eczema')
        self.assertEqual(result['doctors'][0]['doctor_id'],'doctor-anita')
        shared=self.client.post(f"/assessments/{saved['id']}/share",headers=self.patient,
            json={'doctor_id':'doctor-anita','patient_message':'Fictional review request','request_id':'prediction-share-one'}).json()
        route=f"/assessment-shares/{shared['id']}"
        anita={'X-Demo-Actor':'doctor-anita'}
        self.assertEqual(self.client.get(route,headers=anita).json()['assessment']['prediction'],prediction())
        self.assertEqual(self.client.get(route,headers={'X-Demo-Actor':'doctor-lim'}).status_code,404)
        self.assertEqual(self.client.get(route,headers=self.staff).status_code,403)
        self.client.post(route+'/revoke',headers=self.patient)
        self.assertEqual(self.client.get(route,headers=anita).status_code,404)
        other=store.save_assessment('patient-ava','general-prediction','hash',self.body,384,384,prediction=prediction('scabies'))
        self.assertEqual(store.doctor_matches('patient-ava',assessment_id=other['id'])['concern'],'general')

    def test_old_database_migration_preserves_simulated_records(self):
        path=self.path.with_name('legacy.sqlite3')
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE assessments(id TEXT PRIMARY KEY,patient_id TEXT,request_id TEXT,source_hash TEXT,photo BLOB,width INTEGER,height INTEGER,created_at TEXT,UNIQUE(patient_id,request_id))')
            db.execute('INSERT INTO assessments VALUES(?,?,?,?,?,?,?,?)',('old','patient-ava','old-request','old-hash',self.body,384,384,'2026-10-01T00:00:00+00:00'))
        store=Store(path);old=store.assessment('old','patient-ava')
        self.assertEqual(old['origin'],'simulation');self.assertNotIn('prediction',old)
        self.assertEqual(Store(path).assessment('old','patient-ava'),old)
        new=store.save_assessment('patient-ava','new-prediction','hash',self.body,384,384,prediction=prediction())
        self.assertEqual(new['origin'],'experimental_ai');self.assertEqual(store.assessment('old','patient-ava'),old)

    def test_concurrent_retries_keep_first_prediction_immutable(self):
        def save(model_id):
            store=Store(self.path)
            return store.save_assessment('patient-ava','concurrent-prediction','same-hash',self.body,384,384,prediction=prediction(model_id=model_id))
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['model-one','model-two']))
        self.assertEqual(results[0],results[1]);self.assertEqual(len(Store(self.path).assessments('patient-ava')),1)


if __name__=='__main__':unittest.main()
