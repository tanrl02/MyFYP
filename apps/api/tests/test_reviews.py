from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store
import test_assessments as assessments

class ReviewTests(unittest.TestCase):
    setUp = assessments.AssessmentTests.setUp
    photo = assessments.AssessmentTests.photo
    upload = assessments.AssessmentTests.upload
    lim = {'X-Demo-Actor':'doctor-lim'}
    anita = {'X-Demo-Actor':'doctor-anita'}

    def share(self, assessment_id, actor=None, doctor='doctor-lim', request='share-request-one', message='Fictional itch for two days.'):
        return self.client.post(f'/assessments/{assessment_id}/share',headers=actor or self.patient,
            json={'doctor_id':doctor,'patient_message':message,'request_id':request})

    def publish(self, share_id, actor=None, note='Fictional review only.', follow_up='Demo follow-up appointment.'):
        return self.client.post(f'/assessment-shares/{share_id}/review',headers=actor or self.lim,
            json={'doctor_assessment':'Fictional doctor assessment','note':note,'follow_up':follow_up})

    def test_explicit_share_scoping_and_publication(self):
        photo=self.upload().json()
        self.assertEqual(self.client.get('/assessment-shares',headers=self.lim).json(),[])
        self.assertEqual(self.share(photo['id'],actor=self.other).status_code,404)
        self.assertEqual(self.share(photo['id'],actor=self.staff).status_code,403)
        share=self.share(photo['id']).json()
        self.assertEqual(self.share(photo['id']).json()['id'],share['id'])
        self.assertEqual(self.share(photo['id'],message='Changed message').status_code,409)
        for actor in (self.other,self.anita):
            self.assertEqual(self.client.get('/assessment-shares',headers=actor).json(),[])
        self.assertEqual(self.client.get('/assessment-shares',headers=self.staff).status_code,403)
        for actor in (self.anita,self.other,self.staff):
            self.assertIn(self.client.get(f"/assessment-shares/{share['id']}",headers=actor).status_code,(403,404))
            self.assertIn(self.publish(share['id'],actor).status_code,(403,404))
        opened=self.client.get(f"/assessment-shares/{share['id']}",headers=self.lim).json()
        self.assertEqual(opened['assessment']['photo_uri'],photo['photo_uri'])
        self.assertNotIn('assessment', self.client.get('/assessment-shares',headers=self.lim).json()[0])
        reviewed=self.publish(share['id']).json()
        self.assertEqual(self.publish(share['id']).json()['review']['id'],reviewed['review']['id'])
        self.assertEqual(self.publish(share['id'],note='Changed published note').status_code,409)
        self.assertEqual(self.client.get('/assessment-shares',headers=self.patient).json()[0]['review'],reviewed['review'])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/assessment-shares',headers=self.patient).json()[0]['review'],reviewed['review'])

    def test_revocation_retains_patient_review_and_reshare_is_new_consent(self):
        photo=self.upload().json()
        share=self.share(photo['id']).json()
        self.publish(share['id'])
        route=f"/assessment-shares/{share['id']}/revoke"
        self.assertEqual(self.client.post(route,headers=self.other).status_code,404)
        self.assertEqual(self.client.post(route,headers=self.lim).status_code,403)
        revoked=self.client.post(route,headers=self.patient).json()
        self.assertEqual(self.client.post(route,headers=self.patient).json()['revoked_at'],revoked['revoked_at'])
        self.assertEqual(self.client.get('/assessment-shares',headers=self.lim).json(),[])
        self.assertEqual(self.client.get(f"/assessment-shares/{share['id']}",headers=self.lim).status_code,404)
        self.assertEqual(self.publish(share['id']).status_code,404)
        self.assertIsNotNone(revoked['review'])
        # A delayed retry cannot silently reactivate revoked consent.
        self.assertEqual(self.share(photo['id']).json()['revoked_at'],revoked['revoked_at'])
        new=self.share(photo['id'],request='share-request-two').json()
        self.assertNotEqual(new['id'],share['id'])
        self.assertIsNone(new['review'])
        self.assertEqual(len(self.client.get('/assessment-shares',headers=self.patient).json()),2)
        self.assertEqual(len(self.client.get('/assessment-shares',headers=self.lim).json()),1)

    def test_validation_and_independent_doctor_grants(self):
        photo=self.upload().json()
        lim=self.share(photo['id']).json()
        anita=self.share(photo['id'],doctor='doctor-anita',request='share-request-anita').json()
        self.client.post(f"/assessment-shares/{lim['id']}/revoke",headers=self.patient)
        self.assertEqual(self.client.get('/assessment-shares',headers=self.anita).json()[0]['id'],anita['id'])
        for note,follow in [('   ','Demo'),('Demo','\n'),('x'*2001,'Demo'),('Demo','x'*1001)]:
            self.assertEqual(self.publish(anita['id'],actor=self.anita,note=note,follow_up=follow).status_code,422)
        self.assertEqual(self.share(photo['id'],doctor='staff-demo',request='share-request-invalid').status_code,422)
        self.assertEqual(self.share(photo['id'],message='x'*1001).status_code,422)
        self.assertIsNone(self.client.get('/assessment-shares',headers=self.anita).json()[0]['review'])

    def test_concurrent_retries_and_revoke_publication_order(self):
        photo=self.upload().json()
        store=Store(self.path)
        def share(_):
            return store.share_assessment(photo['id'],'patient-ava','doctor-lim','Demo','concurrent-share')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(share,range(4)))
        self.assertEqual(len({s['id'] for s in results}),1)
        share_id=results[0]['id']
        def publish():
            try:
                return store.publish_review(share_id,'doctor-lim','Demo note','Demo follow-up')
            except RuleError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            publication=pool.submit(publish)
            revocation=pool.submit(store.revoke_share,share_id,'patient-ava')
            published=publication.result(); revocation.result()
        own=store.shares('patient-ava')[0]
        self.assertIsNotNone(own['revoked_at'])
        self.assertEqual(store.shares('doctor-lim'),[])
        self.assertEqual(publish(),404)
        self.assertEqual(own['review'] is not None,isinstance(published,dict))
