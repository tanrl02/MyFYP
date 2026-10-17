import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_workflow as workflow

class FollowUpTests(unittest.TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.store=Store(self.path)
        slots=self.client.get('/slots').json()
        self.source_slot=next(s for s in slots if s['doctor_id']=='doctor-lim')
        self.source=self.store.book('patient-ava',self.source_slot['id'],'follow-up-source')
        with self.store.connect() as db:db.execute("UPDATE bookings SET status='called' WHERE id=?",(self.source['id'],))
        self.due=(date.fromisoformat(self.source['clinic_date'])+timedelta(days=1)).isoformat()
        self.targets=[s for s in slots if s['doctor_id']=='doctor-lim' and s['clinic_date']>=self.due]
        self.url=f"/visits/{self.source['id']}/follow-up"
        self.lim={'X-Demo-Actor':'doctor-lim'}

    def recommend(self,**changes):
        return self.client.post(self.url,headers=self.lim,json={'recommended_date':self.due,'reason':'Fictional follow-up recommendation.'}|changes)

    def book_follow_up(self,slot=None,key='follow-up-booking',actor=None):
        return self.client.post(self.url+'/book',headers=actor or self.patient,json={'slot_id':(slot or self.targets[0])['id'],'request_id':key})

    def test_recommendation_role_date_validation_retry_and_patient_display(self):
        payload={'recommended_date':self.due,'reason':'Fictional follow-up recommendation.'}
        for actor in (self.patient,self.other,self.staff):
            self.assertEqual(self.client.post(self.url,headers=actor,json=payload).status_code,403)
        self.assertEqual(self.client.post(self.url,headers={'X-Demo-Actor':'doctor-anita'},json=payload).status_code,404)
        for changes in ({'recommended_date':self.source['clinic_date']},{'reason':' '},{'reason':'x'*1001}):
            self.assertEqual(self.recommend(**changes).status_code,422)
        saved=self.recommend().json()
        self.assertIsNone(saved['booked_visit'])
        self.assertEqual(self.recommend().json(),saved)
        self.assertEqual(self.recommend(reason='Changed').status_code,409)
        self.assertEqual(self.client.get(f"/visits/{self.source['id']}/consultation",headers=self.lim).json()['follow_up'],saved)
        self.assertEqual(self.client.get(f"/bookings/{self.source['id']}/details",headers=self.patient).json()['follow_up'],saved)
        self.assertEqual(self.client.get(f"/bookings/{self.source['id']}/details",headers=self.other).status_code,404)

    def test_patient_booking_links_persist_retry_and_no_implicit_sharing(self):
        self.recommend()
        self.assertEqual(self.book_follow_up(actor=self.other).status_code,404)
        self.assertEqual(self.book_follow_up(actor=self.lim).status_code,403)
        result=self.book_follow_up()
        self.assertEqual(result.status_code,201)
        booked=result.json()
        self.assertEqual(booked['follow_up_source_id'],self.source['id'])
        self.assertEqual(self.book_follow_up().json(),booked)
        self.assertEqual(self.book_follow_up(self.targets[1],key='another-follow-up').status_code,409)
        detail=self.client.get(f"/bookings/{booked['id']}/details",headers=self.patient).json()
        self.assertEqual(detail['follow_up_of']['id'],self.source['id'])
        self.assertEqual(detail['linked_shares'],[])
        self.assertEqual(self.store.shares('patient-ava'),[])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/bookings/{self.source['id']}/details",headers=self.patient).json()['follow_up']['booked_visit']['id'],booked['id'])

    def test_slot_doctor_date_closed_capacity_and_request_key_rules(self):
        self.assertEqual(self.book_follow_up().status_code,404)
        self.recommend()
        self.assertEqual(self.book_follow_up(self.source_slot).status_code,409)
        other=next(s for s in self.client.get('/slots').json() if s['doctor_id']=='doctor-anita' and s['clinic_date']>=self.due)
        self.assertEqual(self.book_follow_up(other).status_code,409)
        self.store.close_slot(self.targets[0]['id'])
        self.assertEqual(self.book_follow_up().status_code,409)
        with self.store.connect() as db:db.execute('UPDATE slots SET capacity=1 WHERE id=?',(self.targets[1]['id'],))
        self.store.book('patient-noah',self.targets[1]['id'],'fill-follow-up')
        self.assertEqual(self.book_follow_up(self.targets[1]).status_code,409)
        normal=self.store.book('patient-ava',self.targets[2]['id'],'normal-key-collision')
        self.assertEqual(self.book_follow_up(self.targets[2],key='normal-key-collision').status_code,409)
        self.assertIsNone(self.store.visit_details(self.source['id'],'patient-ava')['follow_up']['booked_visit'])

    def test_concurrent_double_booking_capacity_and_cancel_rebook(self):
        self.recommend()
        def book(index):
            try:return self.store.book('patient-ava',self.targets[index]['id'],f'concurrent-follow-up-{index}',follow_up_source=self.source['id'])['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(book,[0,1]))
        self.assertEqual(sum(isinstance(value,str) for value in results),1)
        self.assertIn(409,results)
        booked=next(value for value in results if isinstance(value,str))
        self.store.cancel(booked,'patient-ava')
        again=self.book_follow_up(self.targets[2],key='rebook-cancelled-follow-up').json()
        self.assertNotEqual(again['id'],booked)
        self.assertEqual(self.store.visit_details(self.source['id'],'patient-ava')['follow_up']['booked_visit']['id'],again['id'])

    def test_reschedule_preserves_link_doctor_and_recommended_date(self):
        self.recommend()
        booked=self.book_follow_up().json()
        moved=self.store.reschedule(booked['id'],'patient-ava',self.targets[1]['id'],'move-follow-up')
        self.assertEqual(moved['follow_up_source_id'],self.source['id'])
        self.assertEqual(self.store.visit_details(moved['id'],'patient-ava')['follow_up_of']['id'],self.source['id'])
        self.assertEqual(self.store.visit_details(self.source['id'],'patient-ava')['follow_up']['booked_visit']['id'],moved['id'])
        other=next(s for s in self.client.get('/slots').json() if s['doctor_id']=='doctor-anita' and s['clinic_date']>=self.due)
        for slot in (other,self.source_slot):
            with self.assertRaises(RuleError):self.store.reschedule(moved['id'],'staff-demo',slot['id'],'invalid-'+slot['id'])
