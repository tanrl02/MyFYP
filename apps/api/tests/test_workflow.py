from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # mkdtemp + no cleanup here: tests run within ignored project .test-data.
        root = Path(__file__).parents[1] / '.test-data'
        root.mkdir(exist_ok=True)
        self.path = Path(tempfile.mkdtemp(dir=root)) / 'test.sqlite3'
        self.client = TestClient(create_app(self.path))
        self.slot = self.client.get('/slots').json()[0]
        self.patient = {'X-Demo-Actor':'patient-ava'}
        self.other = {'X-Demo-Actor':'patient-noah'}
        self.staff = {'X-Demo-Actor':'staff-demo'}

    def book(self, actor=None, request='request-one'):
        return self.client.post('/bookings', headers=actor or self.patient,
            json={'slot_id':self.slot['id'],'request_id':request})

    def test_connected_persistence_and_scoping(self):
        booking = self.book().json()
        self.assertEqual(self.book().json()['id'], booking['id'])
        self.assertEqual(self.book(request='request-two').status_code,409)
        self.assertEqual(self.client.get('/bookings', headers=self.other).json(), [])
        self.assertEqual(self.client.post(f"/bookings/{booking['id']}/cancel", headers=self.other).status_code,403)
        payload={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']}
        self.assertEqual(self.client.get('/queue',params=payload,headers=self.patient).status_code,403)
        self.assertEqual(self.client.post('/queue/call-next',json=payload,headers=self.staff).json()['id'],booking['id'])
        self.assertEqual(self.client.post('/queue/call-next',json=payload,headers=self.staff).status_code,409)
        self.assertEqual(self.client.post(f"/bookings/{booking['id']}/cancel",headers=self.patient).status_code,409)
        self.assertEqual(self.client.post(f"/queue/{booking['id']}/complete",headers=self.staff).json()['status'],'completed')
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/bookings',headers=self.patient).json()[0]['status'],'completed')

    def test_cancel_releases_capacity_and_preserves_token(self):
        first=self.book().json()
        second=self.book(self.other,'request-noah').json()
        self.assertNotEqual(first['queue_number'],second['queue_number'])
        self.assertEqual(self.client.post(f"/bookings/{first['id']}/cancel",headers=self.patient).status_code,200)
        third=self.book(request='request-new').json()
        self.assertGreater(third['queue_number'],second['queue_number'])
        self.assertEqual(self.client.get('/slots').json()[0]['available'],0)

    def test_simultaneous_duplicate_and_capacity(self):
        store=Store(self.path)
        def reserve(_):
            try:return store.book('patient-ava',self.slot['id'],'same-retry')['id']
            except RuleError as e:return e.message
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(reserve,range(4)))
        self.assertEqual(len(set(results)),1)
        self.assertEqual(len(store.mine('patient-ava')),1)

    def test_staff_and_invalid_inputs(self):
        self.assertEqual(self.book(self.staff).status_code,403)
        self.assertEqual(self.client.post('/bookings',headers=self.patient,json={}).status_code,422)
        self.assertEqual(self.client.get('/bookings').status_code,422)
        self.assertEqual(self.client.get('/bookings',headers={'X-Demo-Actor':'made-up'}).status_code,401)

    def test_competing_patients_cannot_overbook(self):
        store=Store(self.path)
        with store.connect() as db:
            db.execute('UPDATE slots SET capacity=1 WHERE id=?',(self.slot['id'],))
        def reserve(patient):
            try:
                store.book(patient,self.slot['id'],'competing-request')
                return 'saved'
            except RuleError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reserve,['patient-ava','patient-noah']))
        self.assertCountEqual(results,['saved','rejected'])
        self.assertEqual(store.slots()[0]['available'],0)

    def test_waiting_cannot_complete_and_past_cannot_book(self):
        booking=self.book().json()
        self.assertEqual(self.client.post(f"/queue/{booking['id']}/complete",headers=self.staff).status_code,409)
        store=Store(self.path)
        with store.connect() as db:
            db.execute("UPDATE slots SET starts_at='2000-01-01T09:00:00+08:00' WHERE id=?",(self.slot['id'],))
        self.assertEqual(self.book(self.other,'past-request').status_code,409)

if __name__ == '__main__':unittest.main()
