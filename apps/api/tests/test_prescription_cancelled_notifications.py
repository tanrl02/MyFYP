from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class PrescriptionCancelledNotificationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    reason='Private fictional cancellation reason.'

    def messages(self,actor=None):
        response=self.client.get('/notifications',headers=actor or self.patient)
        self.assertEqual(response.status_code,200)
        return [item for item in response.json()['items'] if item['kind']=='prescription_cancelled']

    def cancel(self,visit,actor=None,version=1):
        return self.client.post(f'/visits/{visit}/prescription/cancel',headers=actor or self.doctor,
            json={'version':version,'reason':self.reason})

    def test_only_successful_assigned_doctor_cancellation_notifies_owner_without_private_details(self):
        visit=self.prepare(completed=False)
        self.assertEqual(self.cancel(visit).status_code,404)
        rx=self.issue(visit).json()
        wrong={'X-Demo-Actor':'doctor-anita' if self.slot['doctor_id']=='doctor-lim' else 'doctor-lim'}
        for actor in (self.patient,self.other,self.staff,wrong):self.assertEqual(self.cancel(visit,actor).status_code,403)
        self.assertEqual(self.cancel(visit,version=2).status_code,409)
        self.assertEqual(self.messages(),[])
        self.assertEqual(self.cancel(visit).json()['status'],'cancelled')
        item,=self.messages()
        self.assertEqual((item['source_id'],item['target_id']),(rx['id'],visit))
        self.assertEqual(item['title'],'Prescription cancelled');self.assertIsNone(item['read_at'])
        self.assertIn(self.slot['doctor_name'],item['message']);self.assertIn('Malaysia time',item['message'])
        self.assertIn('not an active prescription',item['message'])
        for private in (self.reason,rx['items'][0]['name'],rx['items'][0]['directions']):self.assertNotIn(private,str(item))
        self.assertEqual(self.messages(self.other),[])
        self.assertEqual(self.client.post(f'/notifications/{item["id"]}/read',headers=self.other).status_code,404)
        reopened=TestClient(create_app(self.path))
        self.assertIn(item,reopened.get('/notifications',headers=self.patient).json()['items'])
        owned,=[row for row in reopened.get('/care',headers=self.patient).json() if row['visit']['id']==item['target_id']]
        self.assertEqual(owned['prescription']['status'],'cancelled')
        self.assertEqual(reopened.get(f'/bookings/{visit}',headers=self.other).status_code,404)

    def test_concurrent_retries_and_later_checkout_keep_one_message_and_read_status(self):
        visit=self.prepare(completed=False);rx=self.issue(visit).json();store=Store(self.path);stock=store.catalog()
        issued,=[item for item in self.client.get('/notifications',headers=self.patient).json()['items'] if item['kind']=='prescription_issued']
        issued_read=self.client.post(f'/notifications/{issued["id"]}/read',headers=self.patient).json()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:store.cancel_prescription(visit,self.slot['doctor_id'],1,self.reason),range(4)))
        self.assertEqual(len({row['cancelled_at'] for row in results}),1)
        item,=self.messages()
        read=self.client.post(f'/notifications/{item["id"]}/read',headers=self.patient).json()
        self.client.post(f'/queue/{visit}/complete',headers=self.staff)
        invoice=self.client.post(f'/visits/{visit}/invoice',headers=self.staff).json()
        self.assertEqual(invoice['total_cents'],3000)
        self.assertEqual(self.cancel(visit).json()['status'],'cancelled')
        self.assertEqual(self.messages(),[read]);self.assertEqual(store.catalog(),stock)
        all_messages=self.client.get('/notifications',headers=self.patient).json()['items']
        self.assertIn(issued_read,all_messages)
        reopened=TestClient(create_app(self.path))
        self.assertIn(read,reopened.get('/notifications',headers=self.patient).json()['items'])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='prescription_cancelled'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-cancelled'").fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dispensing_allocations WHERE prescription_id=?',(rx['id'],)).fetchone()[0],0)

    def test_notification_failure_rolls_back_cancellation_and_event(self):
        visit=self.prepare(completed=False);rx=self.issue(visit).json();store=Store(self.path);stock=store.catalog()
        def fail(*args):raise RuntimeError('Injected cancellation notification failure')
        store.notify=fail
        with self.assertRaises(RuntimeError):store.cancel_prescription(visit,self.slot['doctor_id'],1,self.reason)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM prescription_cancellations').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-cancelled'").fetchone()[0],0)
        self.assertEqual(self.messages(),[]);self.assertEqual(store.catalog(),stock)
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],rx)
        self.assertEqual(self.cancel(visit).status_code,200);self.assertEqual(len(self.messages()),1)

    def test_older_cancellation_is_not_backfilled_and_locked_failures_send_nothing(self):
        visit=self.prepare(completed=False);self.issue(visit);store=Store(self.path)
        store.notify=lambda *args:None
        saved=store.cancel_prescription(visit,self.slot['doctor_id'],1,self.reason)
        self.assertEqual(self.messages(),[])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.post(f'/visits/{visit}/prescription/cancel',headers=self.doctor,
            json={'version':1,'reason':self.reason}).json(),saved)
        self.assertEqual(self.messages(),[])
        self.setUp();visit=self.prepare(completed=False);rx=self.issue(visit).json()
        self.client.post(f'/prescriptions/{rx["id"]}/dispense',headers=self.staff)
        self.assertEqual(self.cancel(visit).status_code,409);self.assertEqual(self.messages(),[])
