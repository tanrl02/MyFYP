from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class PrescriptionNotificationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def messages(self, actor=None):
        response=self.client.get('/notifications',headers=actor or self.patient)
        self.assertEqual(response.status_code,200)
        return [item for item in response.json()['items'] if item['kind']=='prescription_issued']

    def test_only_successful_assigned_doctor_issue_notifies_the_owner(self):
        visit=self.book().json()['id'];self.doctor={'X-Demo-Actor':self.slot['doctor_id']}
        self.assertEqual(self.issue(visit).status_code,409)
        self.assertEqual(self.messages(),[])
        self.client.post('/queue/call-next',headers=self.staff,
            json={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']})
        wrong={'X-Demo-Actor':'doctor-anita' if self.slot['doctor_id']=='doctor-lim' else 'doctor-lim'}
        for actor in (self.patient,self.other,self.staff,wrong):
            self.assertEqual(self.issue(visit,actor=actor).status_code,403)
        self.assertEqual(self.issue(visit,items=[{'medicine_id':'unknown','quantity':1,'directions':'Demo only.'}]).status_code,422)
        self.assertEqual(self.messages(),[])
        rx=self.issue(visit).json();item,=self.messages()
        self.assertEqual((item['source_id'],item['target_id']),(rx['id'],visit))
        self.assertEqual(item['title'],'Prescription issued');self.assertIsNone(item['read_at'])
        self.assertIn(self.slot['doctor_name'],item['message']);self.assertIn('Malaysia time',item['message'])
        self.assertNotIn('Demo instructions',str(item));self.assertNotIn('Demo item A',str(item))
        self.assertEqual(self.messages(self.other),[])
        self.assertEqual(self.client.post(f'/notifications/{item["id"]}/read',headers=self.other).status_code,404)
        self.assertIn(item,TestClient(create_app(self.path)).get('/notifications',headers=self.patient).json()['items'])

    def test_concurrent_issue_retries_and_later_dispensing_keep_one_message_and_read_state(self):
        visit=self.prepare();store=Store(self.path);stock=store.catalog()
        items=[{'medicine_id':'demo-a','quantity':2,'directions':'Demo instructions only'}]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:store.issue_prescription(visit,self.slot['doctor_id'],items),range(4)))
        self.assertEqual(len({rx['id'] for rx in results}),1)
        self.assertEqual(store.catalog(),stock)
        item,=self.messages()
        read=self.client.post(f'/notifications/{item["id"]}/read',headers=self.patient).json()
        self.assertEqual(self.client.post(f'/prescriptions/{results[0]["id"]}/dispense',headers=self.staff,
            json={'allocations':[{'medicine_id':'demo-a','receipt_id':None,'quantity':2}]}).status_code,200)
        self.assertEqual(self.issue(visit).json()['status'],'dispensed')
        self.assertEqual(self.messages(),[read])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='prescription_issued'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-issued'").fetchone()[0],1)

    def test_notification_failure_rolls_back_prescription_items_and_event(self):
        visit=self.prepare();store=Store(self.path);stock=store.catalog()
        def fail(*args):raise RuntimeError('Injected prescription notification failure')
        store.notify=fail
        items=[{'medicine_id':'demo-a','quantity':2,'directions':'Fictional directions.'}]
        with self.assertRaises(RuntimeError):store.issue_prescription(visit,self.slot['doctor_id'],items)
        with store.connect() as db:
            for table in ('prescriptions','prescription_items'):
                self.assertEqual(db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-issued'").fetchone()[0],0)
        self.assertEqual(self.messages(),[]);self.assertEqual(store.catalog(),stock)
        Store(self.path).issue_prescription(visit,self.slot['doctor_id'],items)
        self.assertEqual(len(self.messages()),1)

    def test_existing_prescription_retry_does_not_backfill_or_replace(self):
        visit=self.prepare();store=Store(self.path)
        # Represent a prescription saved before the new notification existed.
        store.notify=lambda *args:None
        saved=store.issue_prescription(visit,self.slot['doctor_id'],
            [{'medicine_id':'demo-a','quantity':2,'directions':'Demo instructions only'}])
        self.assertEqual(self.messages(),[])
        response=TestClient(create_app(self.path)).post(f'/visits/{visit}/prescription',headers=self.doctor,
            json={'items':[{'medicine_id':'demo-a','quantity':2,'directions':'Demo instructions only'}]})
        self.assertEqual(response.json(),saved)
        self.assertEqual(self.issue(visit,items=[{'medicine_id':'demo-a','quantity':3,'directions':'Different'}]).status_code,409)
        self.assertEqual(self.messages(),[])
