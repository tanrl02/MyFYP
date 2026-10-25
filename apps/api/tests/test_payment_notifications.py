from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class PaymentNotificationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def payments(self, actor=None):
        response=self.client.get('/notifications',headers=actor or self.patient)
        self.assertEqual(response.status_code,200)
        return [item for item in response.json()['items'] if item['kind']=='payment_recorded']

    def invoice(self, visit):
        response=self.client.post(f'/visits/{visit}/invoice',headers=self.staff)
        self.assertEqual(response.status_code,200)
        return response.json()

    def test_own_patient_payment_notifies_only_after_dispensing_and_persists(self):
        visit=self.prepare();rx=self.issue(visit).json();invoice=self.invoice(visit)
        route=f'/invoices/{invoice["id"]}/pay-simulated'
        self.assertEqual(self.payments(),[])
        for actor in (self.other,self.doctor):
            self.assertEqual(self.client.post(route,headers=actor).status_code,403)
        for actor in (self.patient,self.staff):
            self.assertEqual(self.client.post(route,headers=actor).status_code,409)
        self.assertEqual(self.payments(),[])
        self.assertEqual(self.client.post(f'/prescriptions/{rx["id"]}/dispense',headers=self.staff,
            json={'allocations':[{'medicine_id':'demo-a','receipt_id':None,'quantity':2}]}).status_code,200)
        paid=self.client.post(route,headers=self.patient).json()
        self.assertEqual(paid['status'],'paid');self.assertEqual(paid['payment_mode'],'simulation')
        item,=self.payments()
        self.assertEqual((item['source_id'],item['target_id']),(invoice['id'],visit))
        self.assertEqual(item['title'],'Payment recorded · simulation');self.assertIsNone(item['read_at'])
        self.assertIn('RM 40.00',item['message']);self.assertIn(invoice['id'][:8],item['message'])
        self.assertIn('No money was transferred.',item['message']);self.assertIn('Malaysia time',item['message'])
        self.assertNotIn('Demo instructions',str(item));self.assertNotIn('Demo item A',str(item))
        self.assertEqual(self.payments(self.other),[])
        self.assertEqual(self.client.post(f'/notifications/{item["id"]}/read',headers=self.other).status_code,404)
        reopened=TestClient(create_app(self.path)).get('/notifications',headers=self.patient).json()['items']
        self.assertIn(item,reopened)

    def test_staff_and_patient_concurrent_retries_keep_one_notification_and_read_state(self):
        visit=self.prepare();invoice=self.invoice(visit);store=Store(self.path)
        with ThreadPoolExecutor(max_workers=4) as pool:
            paid=list(pool.map(lambda actor:store.pay_simulated(invoice['id'],actor),
                ['staff-demo','patient-ava','staff-demo','patient-ava']))
        self.assertTrue(all(row==paid[0] for row in paid))
        item,=self.payments();self.assertIn('RM 30.00',item['message'])
        read=self.client.post(f'/notifications/{item["id"]}/read',headers=self.patient).json()
        for actor in (self.staff,self.patient):
            self.assertEqual(self.client.post(f'/invoices/{invoice["id"]}/pay-simulated',headers=actor).status_code,200)
        self.assertEqual(self.payments(),[read])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='payment_recorded'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='payment-simulated'").fetchone()[0],1)

    def test_notification_failure_rolls_back_payment_and_event(self):
        visit=self.prepare();invoice=self.invoice(visit);store=Store(self.path);stock=store.catalog()
        def fail(*args):raise RuntimeError('Injected payment notification failure')
        store.notify=fail
        with self.assertRaises(RuntimeError):store.pay_simulated(invoice['id'],'staff-demo')
        with store.connect() as db:
            self.assertEqual(store.invoice(db,visit),invoice)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='payment-simulated'").fetchone()[0],0)
        self.assertEqual(self.payments(),[]);self.assertEqual(store.catalog(),stock)
        Store(self.path).pay_simulated(invoice['id'],'staff-demo')
        self.assertEqual(len(self.payments()),1)

    def test_preexisting_paid_invoice_does_not_get_a_notification_on_retry(self):
        visit=self.prepare();invoice=self.invoice(visit);store=Store(self.path)
        # Represent a simulated payment saved before this notification was introduced.
        store.notify=lambda *args:None
        paid=store.pay_simulated(invoice['id'],'staff-demo')
        self.assertEqual(self.payments(),[])
        response=TestClient(create_app(self.path)).post(f'/invoices/{invoice["id"]}/pay-simulated',headers=self.patient)
        self.assertEqual(response.json(),paid);self.assertEqual(self.payments(),[])
