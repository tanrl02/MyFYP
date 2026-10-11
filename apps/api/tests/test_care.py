from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import unittest
import test_workflow as workflow


class CareTests(unittest.TestCase):
    setUp = workflow.WorkflowTests.setUp
    book = workflow.WorkflowTests.book
    def prepare(self, completed=True):
        visit = self.book().json()
        self.doctor = {'X-Demo-Actor': self.slot['doctor_id']}
        payload = {'doctor_id': self.slot['doctor_id'], 'clinic_date': self.slot['clinic_date']}
        self.client.post('/queue/call-next', headers=self.staff, json=payload)
        if completed:
            self.client.post(f"/queue/{visit['id']}/complete", headers=self.staff)
        return visit['id']

    def issue(self, visit, items=None, actor=None):
        return self.client.post(f'/visits/{visit}/prescription', headers=actor or self.doctor,
            json={'items': items or [{'medicine_id':'demo-a','quantity':2,'directions':'Demo instructions only'}]})

    def test_full_care_retry_and_persistence(self):
        visit = self.prepare()
        rx = self.issue(visit).json()
        self.assertEqual(self.issue(visit).json()['id'], rx['id'])
        invoice = self.client.post(f'/visits/{visit}/invoice', headers=self.staff).json()
        self.assertEqual(invoice['total_cents'], 4000)
        self.assertEqual(self.client.post(f'/visits/{visit}/invoice', headers=self.staff).json()['id'], invoice['id'])
        pay = f"/invoices/{invoice['id']}/pay-simulated"
        self.assertEqual(self.client.post(pay, headers=self.patient).status_code, 409)
        dispense = f"/prescriptions/{rx['id']}/dispense"
        self.assertEqual(self.client.post(dispense, headers=self.staff).json()['status'], 'dispensed')
        self.client.post(dispense, headers=self.staff)
        self.assertEqual(Store(self.path).catalog()[0]['stock'], 18)
        self.assertEqual(self.client.post(pay, headers=self.patient).json()['payment_mode'], 'simulation')
        self.client.post(pay, headers=self.staff)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='payment-simulated'").fetchone()[0], 1)
        reopened = TestClient(create_app(self.path))
        care = reopened.get('/care', headers=self.patient).json()[0]
        self.assertEqual(care['invoice']['status'], 'paid')
        self.assertEqual(care['prescription']['status'], 'dispensed')

    def test_care_access_and_invalid_states(self):
        visit = self.prepare()
        other_doctor = {'X-Demo-Actor': 'doctor-lim' if self.slot['doctor_id']=='doctor-anita' else 'doctor-anita'}
        self.assertEqual(self.issue(visit, actor=other_doctor).status_code, 403)
        self.assertEqual(self.issue(visit, actor=self.staff).status_code, 403)
        self.assertEqual(self.client.get('/care', headers=other_doctor).json(), [])
        self.assertEqual(self.client.get('/care', headers=self.other).json(), [])
        self.assertEqual(self.client.get('/medicines', headers=self.patient).status_code, 403)
        rx = self.issue(visit).json()
        self.assertEqual(self.client.post(f"/prescriptions/{rx['id']}/dispense", headers=self.doctor).status_code,403)
        invoice = self.client.post(f'/visits/{visit}/invoice', headers=self.staff).json()
        self.assertEqual(self.client.post(f"/invoices/{invoice['id']}/pay-simulated", headers=self.other).status_code,403)
        self.assertEqual(self.client.post(f"/invoices/{invoice['id']}/pay-simulated", headers=self.doctor).status_code,403)

    def test_validation_and_invoice_freeze(self):
        visit = self.book().json()['id']
        self.doctor = {'X-Demo-Actor': self.slot['doctor_id']}
        self.assertEqual(self.issue(visit).status_code,409)
        self.assertEqual(self.client.post(f'/visits/{visit}/invoice', headers=self.staff).status_code,409)
        for quantity in (0, -1, 1.5, True, 21):
            self.assertEqual(self.issue(visit, [{'medicine_id':'demo-a','quantity':quantity,'directions':'Demo'}]).status_code,422)
        self.client.post('/queue/call-next', headers=self.staff, json={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']})
        self.assertEqual(self.issue(visit,[{'medicine_id':'missing','quantity':1,'directions':'Demo'}]).status_code,422)
        item={'medicine_id':'demo-a','quantity':1,'directions':'Demo'}
        self.assertEqual(self.issue(visit,[item,item]).status_code,422)
        self.client.post(f'/queue/{visit}/complete',headers=self.staff)
        self.client.post(f'/visits/{visit}/invoice',headers=self.staff)
        self.assertEqual(self.issue(visit).status_code,409)

    def test_stock_rollback_and_concurrent_dispensing(self):
        visit = self.prepare()
        items=[{'medicine_id':m,'quantity':2,'directions':'Demo'} for m in ('demo-a','demo-b')]
        rx = self.issue(visit,items).json()
        store=Store(self.path)
        with store.connect() as db:
            db.execute("UPDATE medicines SET stock=1 WHERE id='demo-b'")
        self.assertEqual(self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff).status_code,409)
        self.assertEqual(store.catalog()[0]['stock'],20)
        with store.connect() as db:
            db.execute("UPDATE medicines SET stock=20 WHERE id='demo-b'")
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _: store.dispense(rx['id'],'staff-demo')['status'],range(3)))
        self.assertEqual(results,['dispensed']*3)
        self.assertEqual([m['stock'] for m in store.catalog()],[18,18])
