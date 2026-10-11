from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_workflow as workflow

class CounterBookingTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    def counter(self,patient='patient-ava',actor=None,request='counter-request-one',slot=None):
        return self.client.post('/counter-bookings',headers=actor or self.staff,json={
            'patient_id':patient,'slot_id':slot or self.slot['id'],'request_id':request})

    def test_shared_records_retry_scoping_audit_and_reopen(self):
        saved=self.counter().json()
        self.assertEqual(saved['patient_id'],'patient-ava')
        self.assertEqual(self.counter().json()['id'],saved['id'])
        self.assertEqual(self.client.get('/bookings',headers=self.patient).json()[0]['id'],saved['id'])
        self.assertEqual(self.client.get('/bookings',headers=self.other).json(),[])
        params={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']}
        self.assertEqual(self.client.get('/queue',headers=self.staff,params=params).json()[0]['id'],saved['id'])
        self.assertEqual(self.counter(request='different-counter-request').status_code,409)
        other_slot=next(s for s in self.client.get('/slots').json() if s['id']!=self.slot['id'])
        self.assertEqual(self.counter(slot=other_slot['id']).status_code,409)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/bookings',headers=self.patient).json()[0]['id'],saved['id'])
        with Store(self.path).connect() as db:
            events=db.execute("SELECT actor_id FROM events WHERE action='counter-booked'").fetchall()
            self.assertEqual([r['actor_id'] for r in events],['staff-demo'])
        self.assertEqual(self.client.post(f"/bookings/{saved['id']}/cancel",headers=self.patient).status_code,200)
        self.assertEqual(next(s for s in self.client.get('/slots').json() if s['id']==self.slot['id'])['available'],2)

    def test_roles_input_unknown_and_full_slot(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.counter(actor=actor).status_code,403)
        self.assertEqual(self.counter(patient='unknown-patient').status_code,422)
        self.assertEqual(self.counter(slot='unknown-slot').status_code,404)
        self.assertEqual(self.counter(request='short').status_code,422)
        with Store(self.path).connect() as db:
            db.execute('UPDATE slots SET capacity=1 WHERE id=?',(self.slot['id'],))
        self.counter()
        self.assertEqual(self.counter(patient='patient-noah',request='full-slot-request').status_code,409)
        self.assertEqual(len(self.client.get('/bookings',headers=self.other).json()),0)

    def test_concurrent_retries_and_mixed_channel_capacity(self):
        store=Store(self.path)
        def counter(_):
            return store.book('patient-ava',self.slot['id'],'concurrent-counter',created_by='staff-demo')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(len(set(pool.map(counter,range(4)))),1)
        # Phone and counter compete for the last remaining place for the same patient.
        def mixed(staff):
            try:
                return store.book('patient-noah',self.slot['id'],'counter-channel' if staff else 'phone-channel',created_by='staff-demo' if staff else None)
            except RuleError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(mixed,[True,False]))
        self.assertEqual(sum(isinstance(r,dict) for r in results),1)
        self.assertIn(409,results)
        self.assertEqual(next(s for s in store.slots() if s['id']==self.slot['id'])['available'],0)
