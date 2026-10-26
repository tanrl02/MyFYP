from concurrent.futures import ThreadPoolExecutor
import sqlite3
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_care as care


class AddPatientTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    admin={'X-Demo-Actor':'admin-demo'}

    def body(self,**changes):
        return {'name':'Mia Fictional Demo','phone':'+60 12-345 6789','email':'mia@example.test','request_id':'new-patient-request-one'}|changes

    def add(self,body=None,actor=None):
        return self.client.post('/admin/patients',headers=actor or self.admin,json=body if body is not None else self.body())

    def created(self):
        response=self.add();self.assertEqual(response.status_code,201)
        self.user=response.json();self.new={'X-Demo-Actor':self.user['id']}
        return self.user

    def test_admin_creates_unique_patient_and_minimal_demo_selector_without_contacts(self):
        before=self.client.get('/admin/users',headers=self.admin).json();user=self.created()
        self.assertTrue(user['id'].startswith('patient-'));self.assertEqual(user['role'],'patient')
        self.assertEqual(user['version'],0);self.assertEqual(user['updated_by'],'admin-demo')
        self.assertTrue(user['updated_at']);self.assertEqual(user['name'],self.body()['name'])
        users=self.client.get('/admin/users',headers=self.admin).json()
        self.assertEqual(len(users),7)
        for row in before:self.assertIn(row,users)
        selector=self.client.get('/demo/patients',headers=self.patient).json()
        self.assertEqual(len(selector),3)
        for item in selector:self.assertEqual(set(item),{'id','name'})
        self.assertIn({'id':user['id'],'name':user['name']},selector)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/me',headers=self.new).json(),user)
        self.assertIn({'id':user['id'],'name':user['name']},reopened.get('/demo/patients',headers=self.staff).json())

    def test_role_validation_and_unknown_identities_cannot_create_or_spoof_patients(self):
        for actor in (self.patient,self.other,self.staff,{'X-Demo-Actor':'doctor-lim'}):self.assertEqual(self.add(actor=actor).status_code,403)
        self.assertEqual(self.add(actor={'X-Demo-Actor':'patient-invented'}).status_code,401)
        for body in (self.body(name=' '),self.body(phone='abc'),self.body(email='bad'),self.body(request_id='x'),
                     self.body(name='a\nb'),self.body()|{'role':'doctor'},self.body()|{'id':'patient-ava'}):
            self.assertEqual(self.add(body).status_code,422,body)
        self.assertEqual(len(self.client.get('/admin/users',headers=self.admin).json()),6)
        self.assertEqual(self.client.get('/care',headers={'X-Demo-Actor':'patient-invented'}).status_code,401)
        self.assertEqual(self.client.get('/care',headers=self.admin).status_code,401)

    def test_retry_concurrency_and_later_edit_keep_one_patient_for_the_same_request(self):
        store=Store(self.path);body=self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:
            users=list(pool.map(lambda _:store.create_patient('admin-demo',body['name'],body['phone'],body['email'],body['request_id']),range(4)))
        self.assertEqual(len({row['id'] for row in users}),1)
        user=users[0];self.assertEqual(self.add().json(),user)
        self.assertEqual(self.add(self.body(name='Different patient')).status_code,409)
        edited=self.client.post('/admin/users/'+user['id'],headers=self.admin,
            json={'name':'Mia Updated Demo','phone':'','email':'','version':0}).json()
        self.assertEqual(self.add().json(),edited)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],7)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_creations').fetchone()[0],1)

    def test_creation_failure_does_not_leave_a_partial_profile(self):
        store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_creation BEFORE INSERT ON patient_creations BEGIN SELECT RAISE(ABORT,'Injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.create_patient('admin-demo','Mia Demo','','','rollback-request')
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_creations').fetchone()[0],0)

    def test_new_patient_empty_state_background_and_assessment_ownership(self):
        user=self.created();store=Store(self.path)
        for route in ('/bookings','/care','/assessments','/assessment-shares','/consultations','/feedback'):
            response=self.client.get(route,headers=self.new);self.assertEqual(response.status_code,200,route);self.assertEqual(response.json(),[])
        self.assertEqual(self.client.get('/notifications',headers=self.new).json()['items'],[])
        background=self.client.get('/patient-background',headers=self.new).json()
        self.assertEqual(background['allergies'],'')
        saved=self.client.post('/patient-background',headers=self.new,json={'allergies':'Mia fictional allergy','medicines':'','conditions':'','version':0})
        self.assertEqual(saved.status_code,200)
        self.assertNotEqual(self.client.get('/patient-background',headers=self.patient).json()['allergies'],'Mia fictional allergy')
        assessment=store.save_assessment(user['id'],'new-patient-assessment','hash',b'fictional',1,1)
        self.assertEqual(self.client.get('/assessments/'+assessment['id'],headers=self.new).status_code,200)
        self.assertEqual(self.client.get('/assessments/'+assessment['id'],headers=self.patient).status_code,404)
        share=self.client.post('/assessments/'+assessment['id']+'/share',headers=self.new,
            json={'doctor_id':'doctor-lim','patient_message':'Fictional','request_id':'new-patient-share'}).json()
        self.assertEqual(share['patient_id'],user['id'])
        self.assertEqual(self.client.get('/assessment-shares/'+share['id'],headers=self.patient).status_code,403)
        self.assertEqual(self.client.get('/assessment-shares',headers=self.new).json()[0]['id'],share['id'])
        self.assertEqual(self.client.post('/assessment-shares/'+share['id']+'/revoke',headers=self.new).status_code,200)

    def test_new_patient_booking_counter_booking_reschedule_and_cancel_remain_private(self):
        self.created()
        visit=self.client.post('/counter-bookings',headers=self.staff,json={'patient_id':self.user['id'],'slot_id':self.slot['id'],'request_id':'new-counter-request'}).json()
        self.assertEqual(visit['patient_name'],self.user['name'])
        self.assertEqual(self.client.get('/bookings',headers=self.new).json()[0]['id'],visit['id'])
        self.assertEqual(self.client.get('/bookings',headers=self.patient).json(),[])
        self.assertEqual(self.client.get('/bookings/'+visit['id']+'/details',headers=self.patient).status_code,404)
        slots=self.client.get('/slots').json();other=next(row for row in slots if row['id']!=self.slot['id'])
        moved=self.client.post('/bookings/'+visit['id']+'/reschedule',headers=self.new,
            json={'slot_id':other['id'],'request_id':'new-patient-reschedule'});self.assertEqual(moved.status_code,200)
        self.assertEqual(self.client.post('/bookings/'+moved.json()['id']+'/cancel',headers=self.new).status_code,200)
        bad=self.client.post('/counter-bookings',headers=self.staff,json={'patient_id':'doctor-lim','slot_id':self.slot['id'],'request_id':'invalid-role-booking'})
        self.assertEqual(bad.status_code,422)

    def test_new_patient_full_checkout_notifications_feedback_and_other_patient_separation(self):
        self.created();visit=self.client.post('/bookings',headers=self.new,json={'slot_id':self.slot['id'],'request_id':'new-booking'}).json()['id']
        self.doctor={'X-Demo-Actor':self.slot['doctor_id']}
        self.client.post('/queue/call-next',headers=self.staff,json={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']})
        rx=self.issue(visit).json()
        self.client.post(f'/visits/{visit}/consultation',headers=self.doctor,json={'findings':'Fictional new patient note','follow_up':'Demo only'})
        self.assertEqual(self.client.get('/visits/'+visit+'/consultation',headers=self.new).status_code,200)
        self.assertEqual(self.client.get('/visits/'+visit+'/consultation',headers=self.patient).status_code,404)
        self.assertEqual(self.client.get('/care',headers=self.new).json()[0]['prescription']['id'],rx['id'])
        self.assertEqual(self.client.get('/care',headers=self.patient).json(),[])
        self.client.post('/prescriptions/'+rx['id']+'/dispense',headers=self.staff)
        self.client.post('/queue/'+visit+'/complete',headers=self.staff)
        invoice=self.client.post('/visits/'+visit+'/invoice',headers=self.staff).json()
        self.assertEqual(self.client.post('/invoices/'+invoice['id']+'/pay-simulated',headers=self.new).status_code,200)
        messages=self.client.get('/notifications',headers=self.new).json()['items']
        self.assertTrue(any(row['kind']=='payment_recorded' for row in messages))
        item=messages[0];self.assertEqual(self.client.post('/notifications/'+item['id']+'/read',headers=self.patient).status_code,404)
        read=self.client.post('/notifications/'+item['id']+'/read',headers=self.new).json()
        self.assertTrue(read['read_at']);self.assertEqual(self.client.post('/notifications/'+item['id']+'/unread',headers=self.new).status_code,200)
        self.assertEqual(self.client.post('/notifications/read-displayed',headers=self.new,json={'notification_ids':[item['id']]}).status_code,200)
        self.assertEqual(self.client.post('/visits/'+visit+'/feedback',headers=self.new,json={'rating':4,'comment':'Fictional feedback'}).status_code,201)
        self.assertEqual(self.client.get('/feedback',headers=self.new).json()[0]['booking_id'],visit)
        self.assertEqual(self.client.get('/feedback',headers=self.patient).json(),[])
