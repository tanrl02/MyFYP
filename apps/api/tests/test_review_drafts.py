import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_reviews as reviews

class ReviewDraftTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    lim=reviews.ReviewTests.lim
    anita=reviews.ReviewTests.anita

    def fixture(self):
        assessment=self.upload().json()
        share=self.share(assessment['id']).json()
        return assessment,share,f"/assessment-shares/{share['id']}/draft"

    def test_private_partial_draft_validation_retry_and_reopen(self):
        assessment,share,url=self.fixture()
        self.assertEqual(self.client.get(url,headers=self.lim).json()['version'],0)
        payload={'note':' Fictional unfinished draft ','follow_up':'','version':0}
        saved=self.client.post(url,headers=self.lim,json=payload).json()
        self.assertEqual(saved['version'],1)
        self.assertEqual(saved['note'],'Fictional unfinished draft')
        self.assertEqual(self.client.post(url,headers=self.lim,json=payload).json(),saved)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(url,headers=self.lim).json(),saved)
        for actor in (self.patient,self.other,self.staff):
            self.assertEqual(self.client.get(url,headers=actor).status_code,403)
            self.assertEqual(self.client.post(url,headers=actor,json=payload).status_code,403)
        self.assertEqual(self.client.get(url,headers=self.anita).status_code,404)
        for path in ('/assessment-shares','/notifications',f"/assessments/{assessment['id']}"):
            patient_data=str(self.client.get(path,headers=self.patient).json())
            self.assertNotIn(saved['note'],patient_data)
            self.assertNotIn('draft',patient_data)
        self.assertEqual(self.client.get('/notifications',headers=self.patient).json()['items'],[])
        for changes in ({'note':'x'*2001},{'follow_up':'x'*1001},{'version':True},{'version':-1}):
            self.assertEqual(self.client.post(url,headers=self.lim,json=payload|changes).status_code,422)

    def test_concurrent_edits_conflict_and_no_stale_overwrite(self):
        _,share,url=self.fixture()
        store=Store(self.path)
        def save(text):
            try:return store.save_review_draft(share['id'],'doctor-lim',text,'',0)['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,['Draft one','Draft two'])),[1,409])
        self.assertEqual(self.client.post(url,headers=self.lim,json={'note':'stale','follow_up':'','version':0}).status_code,409)
        self.assertNotEqual(self.client.get(url,headers=self.lim).json()['note'],'stale')

    def test_publication_version_atomic_conversion_and_notification_retry(self):
        _,share,url=self.fixture()
        self.client.post(url,headers=self.lim,json={'note':'Saved private','follow_up':'Later','version':0})
        publish=f"/assessment-shares/{share['id']}/review"
        body={'note':'Confirmed fictional final','follow_up':'Fictional follow-up','draft_version':0}
        self.assertEqual(self.client.post(publish,headers=self.lim,json=body).status_code,409)
        body['draft_version']=1
        result=self.client.post(publish,headers=self.lim,json=body).json()
        self.assertEqual(result['review']['note'],body['note'])
        self.assertEqual(self.client.post(publish,headers=self.lim,json=body).json(),result)
        self.assertEqual(self.client.get(url,headers=self.lim).status_code,409)
        self.assertEqual(self.client.post(url,headers=self.lim,json={'note':'edit','follow_up':'','version':1}).status_code,409)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_review_drafts').fetchone()[0],0)
        inbox=self.client.get('/notifications',headers=self.patient).json()
        self.assertEqual(len(inbox['items']),1)
        self.assertEqual(inbox['items'][0]['kind'],'review_published')
        self.assertEqual(self.client.get('/assessment-shares',headers=self.patient).json()[0]['review'],result['review'])

    def test_revocation_and_new_consent_do_not_reopen_old_draft(self):
        assessment,share,url=self.fixture()
        self.client.post(url,headers=self.lim,json={'note':'Private old grant','follow_up':'','version':0})
        self.client.post(f"/assessment-shares/{share['id']}/revoke",headers=self.patient)
        self.assertEqual(self.client.get(url,headers=self.lim).status_code,404)
        self.assertEqual(self.client.post(url,headers=self.lim,json={'note':'retry','follow_up':'','version':1}).status_code,404)
        for doctor,actor in (('doctor-lim',self.lim),('doctor-anita',self.anita)):
            fresh=self.share(assessment['id'],doctor=doctor,request='fresh-'+doctor).json()
            draft=self.client.get(f"/assessment-shares/{fresh['id']}/draft",headers=actor).json()
            self.assertEqual((draft['note'],draft['version']),('',0))

    def test_failed_publication_retains_saved_draft_and_no_notification(self):
        _,share,_=self.fixture()
        store=Store(self.path)
        draft=store.save_review_draft(share['id'],'doctor-lim','Saved private','Later',0)
        def fail(*args):raise RuntimeError('Injected notification failure')
        store.notify=fail
        with self.assertRaises(RuntimeError):
            store.publish_review(share['id'],'doctor-lim','Final text','Final follow-up',1)
        self.assertEqual(store.review_draft(share['id'],'doctor-lim'),draft)
        self.assertIsNone(store.shares('patient-ava')[0]['review'])
        self.assertEqual(store.notifications('patient-ava')['items'],[])
