from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_appointment_links as links

class ConsultationTests(unittest.TestCase):
    setUp=links.AppointmentLinkTests.setUp
    photo=links.AppointmentLinkTests.photo
    upload=links.AppointmentLinkTests.upload
    book=links.AppointmentLinkTests.book
    link=links.AppointmentLinkTests.link
    lim=links.AppointmentLinkTests.lim
    anita=links.AppointmentLinkTests.anita

    def call(self,visit):
        return self.client.post('/queue/call-next',headers=self.staff,json={'doctor_id':visit['doctor_id'],'clinic_date':visit['clinic_date']})

    def publish(self,visit,actor=None,findings='Fictional consultation findings.',follow_up='Demo follow-up.'):
        return self.client.post(f"/visits/{visit['id']}/consultation",headers=actor or self.lim,json={'findings':findings,'follow_up':follow_up})

    def test_publication_scoping_retry_and_completed_persistence(self):
        visit=self.book()
        self.assertEqual(self.publish(visit).status_code,404)
        self.call(visit)
        self.assertEqual(self.client.get('/consultations',headers=self.patient).json(),[])
        for actor in (self.other,self.anita,self.staff):
            self.assertIn(self.client.get(f"/visits/{visit['id']}/consultation",headers=actor).status_code,(403,404))
            self.assertIn(self.publish(visit,actor).status_code,(403,404))
        saved=self.publish(visit).json()['note']
        self.assertEqual(self.publish(visit).json()['note']['id'],saved['id'])
        self.assertEqual(self.publish(visit,findings='Altered').status_code,409)
        self.assertEqual(self.client.get('/consultations',headers=self.patient).json()[0]['note'],saved)
        self.assertEqual(self.client.get('/consultations',headers=self.other).json(),[])
        self.assertEqual(self.client.get('/consultations',headers=self.anita).json(),[])
        self.assertEqual(self.client.get('/consultations',headers=self.staff).status_code,403)
        self.assertNotIn(saved['findings'],str(self.client.get('/care',headers=self.staff).json()))
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.assertEqual(self.publish(visit).json()['note']['id'],saved['id'])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/consultations',headers=self.patient).json()[0]['note'],saved)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='consultation-published'").fetchone()[0],1)

    def test_linked_photo_requires_live_grant_and_revocation_keeps_note(self):
        visit=self.book(); photo=self.upload().json(); grant=self.link(photo,visit).json(); self.call(visit)
        route=f"/visits/{visit['id']}/consultation"
        opened=self.client.get(route,headers=self.lim).json()
        self.assertEqual(opened['linked_share']['assessment']['photo_uri'],photo['photo_uri'])
        self.assertNotIn('assessment',self.client.get('/consultations',headers=self.lim).json()[0]['linked_share'])
        self.publish(visit)
        self.client.post(f"/assessment-shares/{grant['id']}/revoke",headers=self.patient)
        opened=self.client.get(route,headers=self.lim).json()
        self.assertIsNone(opened['linked_share']); self.assertIsNotNone(opened['note'])
        self.assertIsNone(self.client.get(route,headers=self.patient).json()['linked_share'])

    def test_input_limits_and_no_late_initial_note(self):
        visit=self.book(); self.call(visit)
        for findings,follow in [('   ','Demo'),('Demo','\n'),('x'*2001,'Demo'),('Demo','x'*1001)]:
            self.assertEqual(self.publish(visit,findings=findings,follow_up=follow).status_code,422)
        self.assertIsNone(self.client.get(f"/visits/{visit['id']}/consultation",headers=self.lim).json()['note'])
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.assertEqual(self.publish(visit).status_code,409)

    def test_concurrent_publication_retries_write_one_note(self):
        visit=self.book(); self.call(visit); store=Store(self.path)
        def publish(_):
            return store.publish_consultation(visit['id'],'doctor-lim','Demo findings','Demo follow-up')['note']['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(len(set(pool.map(publish,range(4)))),1)
