import unittest
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_workflow as workflow

class SlotTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book

    def add(self,actor=None,**changes):
        day=(datetime.now(timezone(timedelta(hours=8)))+timedelta(days=4)).date().isoformat()
        body={'doctor_id':'doctor-lim','clinic_date':day,'time':'13:30','capacity':3,'request_id':'new-slot-test-request'}|changes
        return self.client.post('/staff/slots',headers=actor or self.staff,json=body)

    def test_add_retry_validation_roles_booking_and_queue(self):
        slot=self.add().json();self.assertEqual(slot['available'],3);self.assertEqual(slot['booking_count'],0)
        self.assertEqual(self.add().json()['id'],slot['id'])
        self.assertEqual(self.add(capacity=4).status_code,409)
        self.assertEqual(self.add(request_id='duplicate-slot-request').status_code,409)
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.add(actor).status_code,403)
            self.assertEqual(self.client.get('/staff/slots',headers=actor).status_code,403)
            self.assertEqual(self.client.post(f"/staff/slots/{slot['id']}/close",headers=actor).status_code,403)
        for changes in ({'capacity':0},{'capacity':21},{'capacity':True},{'time':'24:00'},{'time':'9:30'},{'clinic_date':'bad'},{'doctor_id':'unknown'}):
            self.assertEqual(self.add(**changes).status_code,422)
        self.assertEqual(self.add(clinic_date='2000-01-01').status_code,409)
        self.assertIn(slot['id'],[s['id'] for s in self.client.get('/slots').json()])
        visit=self.client.post('/bookings',headers=self.patient,json={'slot_id':slot['id'],'request_id':'staff-created-slot-book'}).json()
        queue=self.client.get('/queue',headers=self.staff,params={'doctor_id':slot['doctor_id'],'clinic_date':slot['clinic_date']}).json()
        self.assertEqual(queue[0]['id'],visit['id'])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/bookings',headers=self.patient).json()[0]['id'],visit['id'])
        self.assertEqual(reopened.get('/bookings',headers=self.other).json(),[])

    def test_close_persistence_seed_protection_and_rescheduling(self):
        target=self.add().json();route=f"/staff/slots/{target['id']}/close"
        self.assertEqual(self.client.post(route,headers=self.staff).json()['closed'],1)
        self.assertEqual(self.client.post(route,headers=self.staff).json()['closed'],1)
        self.assertNotIn(target['id'],[s['id'] for s in self.client.get('/slots').json()])
        self.assertEqual(self.client.post('/bookings',headers=self.patient,json={'slot_id':target['id'],'request_id':'closed-target-book'}).status_code,409)
        visit=self.book().json()
        self.assertEqual(self.client.post(f"/bookings/{visit['id']}/reschedule",headers=self.patient,json={'slot_id':target['id'],'request_id':'closed-reschedule'}).status_code,409)
        self.assertEqual(self.client.post(f"/staff/slots/{visit['slot_id']}/close",headers=self.staff).status_code,409)
        self.client.post(f"/bookings/{visit['id']}/cancel",headers=self.patient)
        self.assertEqual(self.client.post(f"/staff/slots/{visit['slot_id']}/close",headers=self.staff).status_code,409)
        empty=next(s for s in self.client.get('/slots').json() if s['id']!=visit['slot_id'])
        self.client.post(f"/staff/slots/{empty['id']}/close",headers=self.staff)
        reopened=TestClient(create_app(self.path))
        self.assertNotIn(empty['id'],[s['id'] for s in reopened.get('/slots').json()])
        self.assertEqual(self.add(request_id='cannot-recreate-closed').status_code,409)
        self.assertEqual(reopened.get('/bookings',headers=self.patient).json()[0]['status'],'cancelled')

    def test_creation_and_closure_booking_races(self):
        slot=self.add().json();store=Store(self.path)
        def action(kind):
            try:
                if kind=='close':store.close_slot(slot['id'])
                else:store.book('patient-ava',slot['id'],'slot-race-booking')
                return kind
            except RuleError:return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(action,['close','book']))
        self.assertEqual(result.count('rejected'),1)
        with store.connect() as db:
            saved=store.managed_slot(db,slot['id'])
            self.assertFalse(saved['closed'] and saved['booking_count'])
        day=slot['clinic_date']
        def create(index):
            try:return store.add_slot('doctor-lim',day,'15:00',2,f'concurrent-slot-{index}')['id']
            except RuleError:return 'rejected'
        with ThreadPoolExecutor(max_workers=3) as pool:
            result=list(pool.map(create,[1,1,2]))
        self.assertEqual(len(set(r for r in result if r!='rejected')),1)
