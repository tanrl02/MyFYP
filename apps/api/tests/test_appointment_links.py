import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews

class AppointmentLinkTests(unittest.TestCase):
    setUp = reviews.ReviewTests.setUp
    photo = reviews.ReviewTests.photo
    upload = reviews.ReviewTests.upload
    share = reviews.ReviewTests.share
    publish = reviews.ReviewTests.publish
    lim = reviews.ReviewTests.lim
    anita = reviews.ReviewTests.anita

    def book(self, actor=None, doctor='doctor-lim'):
        slot=next(s for s in self.client.get('/slots').json() if s['doctor_id']==doctor)
        return self.client.post('/bookings',headers=actor or self.patient,json={'slot_id':slot['id'],'request_id':'booking-link-test'}).json()

    def link(self, photo, visit, actor=None, request='appointment-link-request'):
        return self.client.post(f"/assessments/{photo['id']}/link-appointment",headers=actor or self.patient,
            json={'booking_id':visit['id'],'patient_message':'Fictional appointment concern.','request_id':request})

    def test_link_ownership_assignment_retry_and_reopen(self):
        photo=self.upload().json(); visit=self.book()
        self.assertEqual(self.link(photo,visit,self.other).status_code,404)
        self.assertEqual(self.link(photo,self.book(self.other),self.patient).status_code,404)
        self.assertEqual(self.link(photo,visit,self.staff).status_code,403)
        linked=self.link(photo,visit).json()
        self.assertEqual(linked['doctor_id'],'doctor-lim')
        self.assertEqual(linked['visit']['id'],visit['id'])
        self.assertEqual(self.link(photo,visit).json()['id'],linked['id'])
        self.assertEqual(self.client.get(f"/assessment-shares/{linked['id']}",headers=self.anita).status_code,404)
        self.assertEqual(self.publish(linked['id'],self.anita).status_code,404)
        self.assertEqual(self.client.get('/assessment-shares',headers=self.other).json(),[])
        other_photo=self.upload(actor=self.other).json()
        self.assertEqual(self.link(other_photo,visit,request='wrong-photo-request').status_code,404)
        second=self.upload(request='another-photo-request').json()
        self.assertEqual(self.link(second,visit).status_code,409)
        self.assertEqual(self.link(second,visit,request='replacement-link-request').status_code,409)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/assessment-shares',headers=self.patient).json()[0]['booking_id'],visit['id'])

    def test_cancellation_revokes_link_but_preserves_direct_share(self):
        photo=self.upload().json(); visit=self.book()
        direct=self.share(photo['id']).json(); linked=self.link(photo,visit).json()
        self.publish(linked['id'])
        self.assertEqual(self.client.post(f"/bookings/{visit['id']}/cancel",headers=self.patient).status_code,200)
        mine=self.client.get('/assessment-shares',headers=self.patient).json()
        saved=next(s for s in mine if s['id']==linked['id'])
        self.assertIsNotNone(saved['revoked_at']); self.assertIsNotNone(saved['review'])
        self.assertEqual(saved['visit']['status'],'cancelled')
        self.assertEqual([s['id'] for s in self.client.get('/assessment-shares',headers=self.lim).json()],[direct['id']])
        self.assertEqual(self.publish(linked['id']).status_code,404)
        self.assertEqual(self.link(photo,visit).json()['revoked_at'],saved['revoked_at'])
        self.assertEqual(self.link(photo,visit,request='cancelled-new-request').status_code,409)

    def test_completion_retains_authorized_link_and_revoke_allows_replacement(self):
        photo=self.upload().json(); visit=self.book(); link=self.link(photo,visit).json()
        self.client.post(f"/assessment-shares/{link['id']}/revoke",headers=self.patient)
        second=self.upload(request='second-photo-request').json()
        new=self.link(second,visit,request='fresh-link-request').json()
        self.assertNotEqual(link['id'],new['id'])
        payload={'doctor_id':visit['doctor_id'],'clinic_date':visit['clinic_date']}
        self.client.post('/queue/call-next',headers=self.staff,json=payload)
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.assertEqual(self.client.get(f"/assessment-shares/{new['id']}",headers=self.lim).status_code,200)
        self.assertEqual(self.publish(new['id']).status_code,200)
        self.assertEqual(self.link(photo,visit,request='late-link-request').status_code,409)

    def test_migration_preserves_existing_direct_share_and_review(self):
        photo=self.upload().json(); direct=self.share(photo['id']).json(); self.publish(direct['id'])
        with Store(self.path).connect() as db:
            db.execute('DROP INDEX active_direct_share'); db.execute('DROP INDEX active_visit_share')
            db.execute('ALTER TABLE assessment_shares DROP COLUMN booking_id')
            db.execute('CREATE UNIQUE INDEX active_assessment_share ON assessment_shares(assessment_id,doctor_id) WHERE revoked_at IS NULL')
        reopened=TestClient(create_app(self.path))
        saved=reopened.get('/assessment-shares',headers=self.lim).json()[0]
        self.assertEqual(saved['id'],direct['id']); self.assertIsNone(saved['booking_id']); self.assertIsNotNone(saved['review'])
