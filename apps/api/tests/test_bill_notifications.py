from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class BillNotificationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def bills(self, actor=None):
        response=self.client.get('/notifications',headers=actor or self.patient)
        self.assertEqual(response.status_code,200)
        return [item for item in response.json()['items'] if item['kind']=='bill_ready']

    def test_new_bill_notification_is_patient_scoped_and_persists(self):
        visit=self.prepare(completed=False);url=f'/visits/{visit}/invoice'
        self.assertEqual(self.client.post(url,headers=self.staff).status_code,409)
        self.assertEqual(self.bills(),[])
        self.client.post(f'/queue/{visit}/complete',headers=self.staff)
        for actor in (self.patient,self.other,self.doctor):
            self.assertEqual(self.client.post(url,headers=actor).status_code,403)
        self.assertEqual(self.client.post(url,headers=self.staff,json={'prescription_id':'wrong'}).status_code,409)
        self.assertEqual(self.bills(),[])
        invoice=self.client.post(url,headers=self.staff,json={'prescription_id':None}).json()
        self.assertEqual(invoice['total_cents'],3000)
        item,=self.bills()
        self.assertEqual((item['source_id'],item['target_id']),(invoice['id'],visit))
        self.assertEqual(item['title'],'Bill ready');self.assertIsNone(item['read_at'])
        self.assertIn('RM 30.00',item['message']);self.assertIn('Malaysia time',item['message'])
        self.assertIn(self.slot['doctor_name'],item['message'])
        self.assertEqual(self.bills(self.other),[])
        self.assertEqual(self.client.post(f"/notifications/{item['id']}/read",headers=self.other).status_code,404)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        self.assertEqual(TestClient(create_app(self.path)).get('/notifications',headers=self.patient).json()['items'][0],item)

    def test_prescription_bill_concurrent_retries_payment_and_read_state_do_not_duplicate(self):
        visit=self.prepare();rx=self.issue(visit).json();store=Store(self.path)
        stock=store.catalog()
        with ThreadPoolExecutor(max_workers=4) as pool:
            invoices=list(pool.map(lambda _:store.generate_invoice(visit,'staff-demo'),range(4)))
        self.assertEqual(len({invoice['id'] for invoice in invoices}),1)
        self.assertEqual(invoices[0]['total_cents'],4000)
        item,=self.bills();self.assertIn('RM 40.00',item['message'])
        self.assertNotIn('Demo instructions',str(item));self.assertNotIn('Demo item A',str(item))
        self.assertEqual(store.catalog(),stock)
        read=self.client.post(f"/notifications/{item['id']}/read",headers=self.patient).json()
        self.client.post(f'/prescriptions/{rx["id"]}/dispense',headers=self.staff,
            json={'allocations':[{'medicine_id':'demo-a','receipt_id':None,'quantity':2}]})
        self.assertEqual(self.client.post(f'/invoices/{invoices[0]["id"]}/pay-simulated',headers=self.patient).status_code,200)
        self.assertEqual(self.client.post(f'/visits/{visit}/invoice',headers=self.staff).status_code,200)
        self.assertEqual(self.bills(),[read])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='invoice-generated'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='bill_ready'").fetchone()[0],1)

    def test_notification_failure_rolls_back_bill_lines_and_event(self):
        visit=self.prepare();store=Store(self.path);stock=store.catalog()
        def fail(*args):raise RuntimeError('Injected bill notification failure')
        store.notify=fail
        with self.assertRaises(RuntimeError):store.generate_invoice(visit,'staff-demo')
        with store.connect() as db:
            for table in ('invoices','invoice_lines'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='invoice-generated'").fetchone()[0],0)
        self.assertEqual(self.bills(),[]);self.assertEqual(store.catalog(),stock)
        Store(self.path).generate_invoice(visit,'staff-demo')
        self.assertEqual(len(self.bills()),1)

    def test_existing_bill_is_not_backfilled_on_retry(self):
        visit=self.prepare();store=Store(self.path)
        # Represent an invoice saved before this notification feature existed.
        store.notify=lambda *args:None
        saved=store.generate_invoice(visit,'staff-demo')
        self.assertEqual(self.bills(),[])
        retry=TestClient(create_app(self.path)).post(f'/visits/{visit}/invoice',headers=self.staff).json()
        self.assertEqual(retry,saved);self.assertEqual(self.bills(),[])
