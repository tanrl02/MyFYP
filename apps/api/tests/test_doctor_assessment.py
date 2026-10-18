import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews
from test_predictions import prediction


class DoctorAssessmentTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    lim=reviews.ReviewTests.lim
    anita=reviews.ReviewTests.anita

    def fixture(self):
        store=Store(self.path)
        assessment=store.save_assessment('patient-ava','doctor-assessment-fixture','hash',self.photo(),64,64,prediction=prediction('urticaria'))
        shared=self.share(assessment['id']).json()
        return assessment,shared,f"/assessment-shares/{shared['id']}"

    def test_private_assessment_draft_publish_reopen_and_ai_snapshot_unchanged(self):
        assessment,share,url=self.fixture()
        draft={'doctor_assessment':'Fictional: unable to determine from photo.','note':'Fictional observations.','follow_up':'Fictional in-person follow-up.','version':0}
        saved=self.client.post(url+'/draft',headers=self.lim,json=draft).json()
        self.assertEqual(saved['doctor_assessment'],draft['doctor_assessment'])
        self.assertNotIn(draft['doctor_assessment'],str(self.client.get('/assessment-shares',headers=self.patient).json()))
        changed=draft|{'doctor_assessment':'Fictional second independent assessment.','version':saved['version']}
        second=self.client.post(url+'/draft',headers=self.lim,json=changed).json()
        self.assertEqual(second['version'],2)
        self.assertEqual(self.client.post(url+'/draft',headers=self.lim,json=draft).status_code,409)
        body={key:second[key] for key in ('doctor_assessment','note','follow_up')}
        body['draft_version']=second['version']
        published=self.client.post(url+'/review',headers=self.lim,json=body).json()
        self.assertEqual(published['review']['doctor_assessment'],changed['doctor_assessment'])
        self.assertEqual(self.client.post(url+'/review',headers=self.lim,json=body).json(),published)
        self.assertEqual(self.client.post(url+'/review',headers=self.lim,json=body|{'doctor_assessment':'Replacement'}).status_code,409)
        reopened=TestClient(create_app(self.path))
        own=reopened.get('/assessment-shares',headers=self.patient).json()[0]
        self.assertEqual(own['review'],published['review'])
        self.assertEqual(reopened.get(f"/assessments/{assessment['id']}",headers=self.patient).json()['prediction'],assessment['prediction'])
        self.assertEqual(reopened.get(url,headers=self.other).status_code,403)
        self.assertEqual(reopened.get(url,headers=self.anita).status_code,404)
        self.assertEqual(reopened.get(url,headers=self.staff).status_code,403)
        self.client.post(url+'/revoke',headers=self.patient)
        self.assertEqual(self.client.get(url,headers=self.lim).status_code,404)
        self.assertEqual(self.client.get('/assessment-shares',headers=self.patient).json()[0]['review'],published['review'])

    def test_publish_requires_independent_assessment_and_length_is_bounded(self):
        _,_,url=self.fixture()
        base={'note':'Fictional note','follow_up':'Fictional follow-up'}
        for value in (None,'',' ','x'*501):
            payload=base if value is None else base|{'doctor_assessment':value}
            self.assertEqual(self.client.post(url+'/review',headers=self.lim,json=payload).status_code,422)
        self.assertEqual(self.client.post(url+'/draft',headers=self.lim,json=base|{'doctor_assessment':'x'*501,'version':0}).status_code,422)
        self.assertIsNone(self.client.get('/assessment-shares',headers=self.patient).json()[0]['review'])

    def test_legacy_review_migration_does_not_invent_an_assessment(self):
        _,share,url=self.fixture();store=Store(self.path)
        old=store.publish_review(share['id'],'doctor-lim','Old saved notes','Old follow-up')['review']
        with store.connect() as db:
            db.execute('ALTER TABLE assessment_reviews DROP COLUMN doctor_assessment')
            db.execute('ALTER TABLE assessment_review_drafts DROP COLUMN doctor_assessment')
        migrated=Store(self.path).shares('patient-ava')[0]['review']
        self.assertEqual(migrated,old);self.assertEqual(migrated['doctor_assessment'],'')


if __name__=='__main__':unittest.main()
