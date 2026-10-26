from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import sqlite3
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class AddDoctorTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    admin={'X-Demo-Actor':'admin-demo'}

    def body(self,**changes):return {'name':'Dr Mira Fictional','phone':'+60 12-345 6789','email':'mira@example.test','request_id':'doctor-creation-request'}|changes
    def add(self,body=None,actor=None):return self.client.post('/admin/doctors',headers=actor or self.admin,json=body if body is not None else self.body())
    def created(self):
        result=self.add();self.assertEqual(result.status_code,201);self.user=result.json();self.new={'X-Demo-Actor':self.user['id']};return self.user
    def slot_for_new(self):
        self.created();result=self.client.post('/staff/slots',headers=self.staff,json={'doctor_id':self.user['id'],'clinic_date':self.slot['clinic_date'],'time':'14:00','capacity':2,'duration_minutes':30,'request_id':'new-doctor-slot'})
        self.assertEqual(result.status_code,201,result.text);return result.json()

    def test_created_doctor_has_basic_profile_and_no_inherited_slots_or_visits_after_reopening(self):
        user=self.created();self.assertEqual(user['role'],'doctor');self.assertTrue(user['id'].startswith('doctor-'))
        self.assertEqual(self.client.get('/me',headers=self.new).json(),user)
        profiles=self.client.get('/doctors',headers=self.patient).json();profile=next(row for row in profiles if row['doctor_id']==user['id'])
        self.assertEqual((profile['specialty'],profile['expertise'],profile['version']),('Not specified',[],0))
        for private in (user['email'],user['phone']):self.assertNotIn(private,str(profile))
        for route in ('/care','/consultations','/assessment-shares'):self.assertEqual(self.client.get(route,headers=self.new).json(),[])
        self.assertFalse(any(row['doctor_id']==user['id'] for row in self.client.get('/slots').json()))
        reopened=TestClient(create_app(self.path))
        self.assertFalse(any(row['doctor_id']==user['id'] for row in reopened.get('/slots').json()))
        self.assertEqual(reopened.get('/me',headers=self.new).json(),user)
        selector=reopened.get('/demo/doctors',headers=self.admin).json()
        self.assertEqual(len(selector),3)
        self.assertIn({'id':user['id'],'name':user['name']},selector)
        for row in selector:self.assertEqual(set(row),{'id','name'})

    def test_only_admin_can_create_and_cannot_supply_a_role_or_existing_identity(self):
        for actor in (self.patient,self.other,self.staff,{'X-Demo-Actor':'doctor-lim'}):self.assertEqual(self.add(actor=actor).status_code,403)
        for body in (self.body(name=' '),self.body(phone='bad'),self.body(email='bad'),self.body(request_id='x'),self.body()|{'role':'admin'},self.body()|{'id':'doctor-lim'}):
            self.assertEqual(self.add(body).status_code,422)
        self.assertEqual(len(self.client.get('/admin/users',headers=self.admin).json()),6)
        self.assertEqual(self.client.get('/care',headers={'X-Demo-Actor':'doctor-invented'}).status_code,401)
        self.assertEqual(self.client.get('/care',headers=self.admin).status_code,401)

    def test_concurrent_retries_and_distinct_doctors_receive_distinct_queue_prefixes(self):
        store=Store(self.path);body=self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:users=list(pool.map(lambda _:store.create_doctor('admin-demo',body['name'],body['phone'],body['email'],body['request_id']),range(4)))
        self.assertEqual(len({user['id'] for user in users}),1);self.assertEqual(self.add().json(),users[0])
        self.assertEqual(self.add(self.body(name='Changed')).status_code,409)
        second=self.add(self.body(name='Dr Other Fictional',request_id='second-doctor-request')).json()
        with store.connect() as db:
            self.assertEqual(store.queue_prefix(db,users[0]['id']),'D001');self.assertEqual(store.queue_prefix(db,second['id']),'D002')
            self.assertEqual(store.queue_prefix(db,'doctor-lim'),'L');self.assertEqual(store.queue_prefix(db,'doctor-anita'),'A')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM doctor_creations').fetchone()[0],2)
        edited=self.client.post('/admin/users/'+users[0]['id'],headers=self.admin,json={'name':'Dr Updated Fictional','phone':'','email':'','version':0}).json()
        self.assertEqual(self.add().json(),edited)

    def test_creation_rolls_back_basic_and_doctor_profiles_if_request_audit_fails(self):
        store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_doctor BEFORE INSERT ON doctor_creations BEGIN SELECT RAISE(ABORT,'Injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.create_doctor('admin-demo','Dr Fictional','','','rollback-doctor-request')
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM doctor_profiles').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM doctor_creations').fetchone()[0],0)

    def test_staff_configures_profile_and_weekly_hours_and_doctor_views_only_own_schedule(self):
        self.created();id=self.user['id'];week=date.today()+timedelta(days=21);week-=timedelta(days=week.weekday());week=week.isoformat()
        initial=self.client.get('/doctor/schedule',headers=self.new,params={'week_start':week}).json()
        self.assertEqual(initial['slots'],[]);self.assertEqual(initial['pattern']['version'],0)
        data={'specialty':'Fictional dermatology','expertise':['general','eczema'],'version':0}
        self.assertEqual(self.client.post('/staff/doctors/'+id,headers=self.new,json=data).status_code,403)
        self.assertEqual(self.client.post('/staff/doctors/'+id,headers=self.staff,json=data).status_code,200)
        pattern={'weekdays':[0],'start_time':'09:00','end_time':'10:00','duration_minutes':30,'capacity':2,'version':0}
        self.assertEqual(self.client.post('/staff/schedules/'+id,headers=self.staff,json=pattern).status_code,200)
        preview=self.client.post('/staff/schedules/'+id+'/preview',headers=self.staff,json={'week_start':week,'version':1}).json()
        generated=self.client.post('/staff/schedules/'+id+'/generate',headers=self.staff,json={'week_start':week,'version':1,'preview_token':preview['preview_token'],'request_id':'new-doctor-generation'})
        self.assertEqual(generated.status_code,201,generated.text)
        own=self.client.get('/doctor/schedule',headers=self.new,params={'week_start':week}).json()
        self.assertEqual(len(own['slots']),2);self.assertTrue(all(row['doctor_id']==id for row in own['slots']))
        other=self.client.get('/doctor/schedule',headers={'X-Demo-Actor':'doctor-lim'},params={'week_start':week}).json()
        self.assertTrue(all(row['doctor_id']!=id for row in other['slots']))
        match=self.client.get('/doctor-matches',headers=self.patient,params={'concern':'eczema'}).json()
        self.assertTrue(any(row['doctor_id']==id and row['match_level']=='concern' for row in match['doctors']))

    def test_new_doctor_handles_assigned_visit_corrections_handover_billing_and_reports(self):
        old_visit=self.prepare(completed=False);old_doctor=self.doctor
        slot=self.slot_for_new();id=self.user['id']
        visit=self.client.post('/bookings',headers=self.other,json={'slot_id':slot['id'],'request_id':'new-doctor-visit'}).json()
        self.assertEqual(visit['queue_prefix'],'D001')
        self.assertEqual(self.client.get('/care',headers=self.new).json()[0]['visit']['id'],visit['id'])
        self.assertEqual(self.client.get('/visits/'+old_visit+'/consultation',headers=self.new).status_code,404)
        self.client.post('/queue/call-next',headers=self.staff,json={'doctor_id':id,'clinic_date':slot['clinic_date']})
        self.assertEqual(self.client.post('/visits/'+visit['id']+'/consultation',headers=self.new,json={'findings':'Fictional','follow_up':'Demo'}).status_code,200)
        self.assertEqual(self.client.get('/visits/'+visit['id']+'/consultation',headers=old_doctor).status_code,404)
        self.doctor=self.new;rx=self.issue(visit['id']).json()
        corrected=self.client.post('/visits/'+visit['id']+'/prescription/directions',headers=self.new,json={'version':1,'reason':'Fictional','items':[{'medicine_id':'demo-a','directions':'Corrected fictional directions'}]})
        self.assertEqual(corrected.status_code,200)
        self.assertEqual(self.client.post('/prescriptions/'+rx['id']+'/dispense',headers=self.staff,json={'prescription_version':2}).status_code,200)
        self.assertEqual(self.client.post('/visits/'+visit['id']+'/consultation/finish',headers=self.new).status_code,200)
        self.client.post('/queue/'+visit['id']+'/complete',headers=self.staff)
        invoice=self.client.post('/visits/'+visit['id']+'/invoice',headers=self.staff).json()
        self.assertEqual(self.client.post('/invoices/'+invoice['id']+'/pay-simulated',headers=self.other).status_code,200)
        messages=self.client.get('/notifications',headers=self.other).json()['items']
        self.assertTrue(any('D001-001' in row['message'] for row in messages))
        report=Store(self.path).daily_report(slot['clinic_date'])
        self.assertEqual(next(row for row in report['visits_by_doctor'] if row['doctor_id']==id)['visits']['completed'],1)
        self.assertEqual(self.client.get('/admin/users',headers=self.new).status_code,403)

    def test_new_doctor_can_review_only_authorised_assessment_shares(self):
        self.created();store=Store(self.path);assessment=store.save_assessment('patient-ava','doctor-share-fixture','hash',b'fictional',1,1)
        share=self.client.post('/assessments/'+assessment['id']+'/share',headers=self.patient,json={'doctor_id':self.user['id'],'patient_message':'Fictional','request_id':'new-doctor-share'}).json()
        self.assertEqual(self.client.get('/assessment-shares/'+share['id'],headers=self.new).status_code,200)
        self.assertEqual(self.client.get('/assessment-shares/'+share['id'],headers={'X-Demo-Actor':'doctor-lim'}).status_code,404)
        result=self.client.post('/assessment-shares/'+share['id']+'/review',headers=self.new,json={'note':'Fictional review','follow_up':'Demo','doctor_assessment':'Fictional finding'})
        self.assertEqual(result.status_code,200,result.text)

    def test_doctor_role_lookups_and_names_reuse_the_current_transaction(self):
        self.created();store=Store(self.path)
        with store.connect() as db:
            def forbidden():raise AssertionError('Nested connection opened')
            store.connect=forbidden
            self.assertTrue(store.is_doctor(self.user['id'],db));self.assertFalse(store.is_patient(self.user['id'],db))
            self.assertEqual(store.user_name(db,self.user['id']),self.user['name'])
            self.assertEqual(store.schedule_pattern(db,self.user['id'])['version'],0)
