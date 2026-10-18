from concurrent.futures import ThreadPoolExecutor
import json
import unittest
from unittest.mock import Mock
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_predictions as predictions
from test_predictions import prediction


class AssessmentSymptomsTests(unittest.TestCase):
    def setUp(self):
        predictions.PredictionTests.setUp(self)
        self.predict=Mock(return_value=prediction())
        self.client=TestClient(create_app(self.path,photo_checker=lambda body:{'accepted':True},predictor=self.predict))
        self.symptoms={'body_area':'Forearm','onset':'3 days ago','itching':'yes','pain':'not_sure','description':'Fictional symptom context.'}

    def upload(self,symptoms=None):
        return self.client.post('/assessments',headers=self.patient,data={'request_id':'symptom-request-one','symptoms':json.dumps(self.symptoms if symptoms is None else symptoms)},files={'photo':('x.png',self.body,'image/png')})

    def test_context_reopens_retries_canonically_and_does_not_change_model_input(self):
        saved=self.upload().json();self.assertEqual(saved['symptoms'],self.symptoms)
        self.assertEqual(self.predict.call_args.args,(self.body,));self.assertEqual(saved['prediction'],prediction())
        reordered={key:self.symptoms[key] for key in reversed(self.symptoms)}
        reordered['body_area']='  Forearm  '
        self.assertEqual(self.upload(reordered).json(),saved);self.assertEqual(self.predict.call_count,1)
        self.assertEqual(self.upload(self.symptoms|{'pain':'yes'}).status_code,409)
        self.assertEqual(self.predict.call_count,1)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/assessments',headers=self.patient).json()[0]['symptoms'],self.symptoms)
        self.assertEqual(reopened.get(f"/assessments/{saved['id']}",headers=self.patient).json(),saved)
        self.assertEqual(reopened.get('/assessments',headers=self.other).json(),[])

    def test_only_authorized_doctor_sees_context_with_photo(self):
        saved=self.upload().json()
        share=self.client.post(f"/assessments/{saved['id']}/share",headers=self.patient,json={'doctor_id':'doctor-lim','patient_message':'Fictional request','request_id':'symptom-share-one'}).json()
        route=f"/assessment-shares/{share['id']}";lim={'X-Demo-Actor':'doctor-lim'}
        self.assertEqual(self.client.get(route,headers=lim).json()['assessment']['symptoms'],self.symptoms)
        self.assertEqual(self.client.get(route,headers={'X-Demo-Actor':'doctor-anita'}).status_code,404)
        self.assertEqual(self.client.get(route,headers=self.staff).status_code,403)
        self.client.post(route+'/revoke',headers=self.patient)
        self.assertEqual(self.client.get(route,headers=lim).status_code,404)
        self.assertEqual(self.client.get(f"/assessments/{saved['id']}",headers=self.patient).json()['symptoms'],self.symptoms)

    def test_invalid_details_are_rejected_before_inference_and_never_assume_no(self):
        for changes in ({'body_area':' '},{'body_area':'x'*81},{'onset':''},{'onset':'x'*101},
                        {'itching':False},{'pain':'sometimes'},{'description':'x'*1001},{'extra':'unsupported'}):
            self.assertEqual(self.upload(self.symptoms|changes).status_code,422,changes)
        self.predict.assert_not_called();self.assertEqual(Store(self.path).assessments('patient-ava'),[])
        unknown=self.symptoms|{'onset':'not sure','itching':'not_sure','pain':'not_sure','description':''}
        saved=self.upload(unknown).json();self.assertEqual(saved['symptoms']['itching'],'not_sure')

    def test_concurrent_conflicting_context_cannot_overwrite_saved_details(self):
        def save(description):
            try:
                return Store(self.path).save_assessment('patient-ava','same-symptom-request','same-photo',self.body,384,384,
                    prediction=prediction(),symptoms=self.symptoms|{'description':description})['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(save,['Fictional A','Fictional B']))
        self.assertEqual(sum(result==409 for result in results),1)
        self.assertEqual(len(Store(self.path).assessments('patient-ava')),1)

    def test_legacy_migration_preserves_record_and_missing_context(self):
        store=Store(self.path)
        old=store.save_assessment('patient-ava','old-no-symptoms','hash',self.body,384,384,prediction=prediction())
        self.assertIsNone(old['symptoms'])
        with store.connect() as db:db.execute('ALTER TABLE assessments DROP COLUMN symptoms_json')
        reopened=Store(self.path).assessment(old['id'],'patient-ava')
        self.assertEqual(reopened,old);self.assertIsNone(reopened['symptoms'])


if __name__=='__main__':unittest.main()
