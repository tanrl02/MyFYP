from concurrent.futures import ThreadPoolExecutor
from datetime import date,timedelta
import sqlite3
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class AddStaffTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    admin={'X-Demo-Actor':'admin-demo'}
    def body(self,**changes):return {'name':'Nora Fictional Staff','phone':'+60 12-345 6789','email':'nora@example.test','request_id':'staff-creation-request'}|changes
    def add(self,body=None,actor=None):return self.client.post('/admin/staff',headers=actor or self.admin,json=body if body is not None else self.body())
    def created(self):
        result=self.add();self.assertEqual(result.status_code,201);self.user=result.json();self.new={'X-Demo-Actor':self.user['id']};return self.user
    def receipt(self,request='new-staff-receipt',quantity=2):return {'medicine_id':'demo-a','quantity':quantity,'reason':'Fictional staff receipt','request_id':request}

    def test_admin_creates_staff_with_private_basic_profile_and_minimal_staff_selector(self):
        user=self.created();self.assertEqual(user['role'],'staff');self.assertTrue(user['id'].startswith('staff-'))
        self.assertEqual((user['version'],user['updated_by']),(0,'admin-demo'))
        self.assertEqual(self.client.get('/me',headers=self.new).json(),user)
        rows=self.client.get('/demo/staff',headers=self.new).json();self.assertEqual(len(rows),2)
        self.assertIn({'id':user['id'],'name':user['name']},rows)
        for row in rows:self.assertEqual(set(row),{'id','name'})
        reopened=TestClient(create_app(self.path));self.assertEqual(reopened.get('/me',headers=self.new).json(),user)
        self.assertIn(user,reopened.get('/admin/users',headers=self.admin).json())

    def test_roles_validation_and_clinical_privacy_remain_restricted(self):
        self.created()
        for actor in (self.patient,self.other,self.staff,self.new,{'X-Demo-Actor':'doctor-lim'}):self.assertEqual(self.add(actor=actor).status_code,403)
        for body in (self.body(name=' '),self.body(phone='bad'),self.body(email='bad'),self.body(request_id='x'),self.body()|{'role':'admin'},self.body()|{'id':'staff-demo'}):self.assertEqual(self.add(body).status_code,422)
        self.assertEqual(self.add(actor={'X-Demo-Actor':'staff-invented'}).status_code,401)
        for route in ('/admin/users','/assessments','/patient-background','/consultations','/assessment-shares'):
            self.assertEqual(self.client.get(route,headers=self.new).status_code,403,route)
        for actor in (self.patient,{'X-Demo-Actor':'doctor-lim'}):self.assertEqual(self.client.get('/demo/staff',headers=actor).status_code,403)
        self.assertEqual(self.client.get('/care',headers=self.admin).status_code,401)
        self.assertEqual(self.client.get('/care',headers={'X-Demo-Actor':'staff-invented'}).status_code,401)

    def test_concurrent_creation_retries_and_later_edits_keep_one_staff_member(self):
        store=Store(self.path);body=self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:users=list(pool.map(lambda _:store.create_staff('admin-demo',body['name'],body['phone'],body['email'],body['request_id']),range(4)))
        self.assertEqual(len({row['id'] for row in users}),1)
        self.assertEqual(self.add().json(),users[0]);self.assertEqual(self.add(self.body(name='Different staff')).status_code,409)
        edited=self.client.post('/admin/users/'+users[0]['id'],headers=self.admin,json={'name':'Nora Updated Staff','phone':'','email':'','version':0}).json()
        self.assertEqual(self.add().json(),edited)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_creations').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],7)

    def test_creation_failure_rolls_back_new_basic_profile(self):
        store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_staff BEFORE INSERT ON staff_creations BEGIN SELECT RAISE(ABORT,'Injected failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.create_staff('admin-demo','Nora Fictional','','','rollback-staff-request')
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM user_profiles').fetchone()[0],6)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_creations').fetchone()[0],0)

    def test_new_staff_queue_counter_dispensing_billing_and_feedback_use_actual_actor(self):
        self.created();visit=self.book().json()['id'];self.doctor={'X-Demo-Actor':self.slot['doctor_id']}
        self.assertEqual(self.client.post('/queue/call-next',headers=self.new,json={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']}).status_code,200)
        counter=self.client.post('/counter-bookings',headers=self.new,json={'patient_id':'patient-noah','slot_id':self.slot['id'],'request_id':'staff-counter-request'});self.assertEqual(counter.status_code,201)
        self.assertEqual(self.client.get('/visits/'+visit+'/consultation',headers=self.new).status_code,403)
        rx=self.issue(visit).json()
        self.assertEqual(self.client.post('/prescriptions/'+rx['id']+'/dispense',headers=self.new).status_code,200)
        self.assertEqual(self.client.post('/queue/'+visit+'/complete',headers=self.new).status_code,200)
        invoice=self.client.post('/visits/'+visit+'/invoice',headers=self.new).json()
        self.assertEqual(self.client.post('/invoices/'+invoice['id']+'/pay-simulated',headers=self.new).status_code,200)
        self.assertEqual(self.client.post('/visits/'+visit+'/feedback',headers=self.patient,json={'rating':4,'comment':'Fictional'}).status_code,201)
        self.assertEqual(self.client.get('/feedback',headers=self.new).json()[0]['booking_id'],visit)
        self.assertEqual(self.client.get('/feedback',headers=self.other).json(),[])
        with Store(self.path).connect() as db:
            actions=db.execute("SELECT action,actor_id FROM events WHERE action IN ('called','counter-booked','prescription-dispensed','completed','invoice-generated','payment-simulated')").fetchall()
            self.assertEqual(len(actions),6);self.assertTrue(all(row['actor_id']==self.user['id'] for row in actions))
            audit=db.execute('SELECT * FROM staff_activity WHERE staff_id=?',(self.user['id'],)).fetchall()
            self.assertEqual(len(audit),6)
            self.assertTrue(all(row['action'].startswith('POST ') for row in audit))

    def test_new_staff_stock_batch_holds_and_schedule_changes_record_actor_and_retry_once(self):
        self.created();body=self.receipt()|{'batch_number':'SYN-STAFF','expiry_date':(date.today()+timedelta(days=365)).isoformat()}
        received=self.client.post('/stock/receive',headers=self.new,json=body);self.assertEqual(received.status_code,201,received.text);receipt=received.json()
        self.assertEqual(self.client.post('/stock/receive',headers=self.new,json=body).json(),receipt)
        route='/stock/demo-a/batches/'+receipt['id']+'/hold'
        for version,held in ((0,True),(1,False)):
            self.assertEqual(self.client.post(route,headers=self.new,json={'held':held,'reason':'Fictional hold check','version':version,'request_id':'staff-hold-'+str(version)}).status_code,200)
        doctor=self.slot['doctor_id'];pattern={'weekdays':[0],'start_time':'09:00','end_time':'10:00','duration_minutes':30,'capacity':2,'version':0}
        self.assertEqual(self.client.post('/staff/schedules/'+doctor,headers=self.new,json=pattern).status_code,200)
        self.assertEqual(self.client.post('/staff/doctors/'+doctor,headers=self.new,json={'specialty':'Fictional staff profile edit','expertise':['general'],'version':0}).status_code,200)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT actor_id FROM stock_receipts WHERE id=?',(receipt['id'],)).fetchone()[0],self.user['id'])
            self.assertTrue(all(row[0]==self.user['id'] for row in db.execute('SELECT actor_id FROM batch_hold_changes')))
            self.assertEqual(db.execute('SELECT actor_id FROM doctor_schedule_patterns WHERE doctor_id=?',(doctor,)).fetchone()[0],self.user['id'])
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_activity WHERE staff_id=?',(self.user['id'],)).fetchone()[0],5)

    def test_staff_audit_failure_rolls_back_action_and_retry_does_not_duplicate_audit(self):
        self.created();store=Store(self.path);before=store.catalog()
        with store.connect() as db:db.execute("CREATE TRIGGER fail_staff_audit BEFORE INSERT ON staff_activity BEGIN SELECT RAISE(ABORT,'Injected audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):self.client.post('/stock/receive',headers=self.new,json=self.receipt())
        self.assertEqual(store.catalog(),before)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM stock_receipts').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_activity').fetchone()[0],0)
            db.execute('DROP TRIGGER fail_staff_audit')
        self.assertEqual(self.client.post('/stock/receive',headers=self.new,json=self.receipt()).status_code,201)
        self.assertEqual(self.client.post('/stock/receive',headers=self.new,json=self.receipt()).status_code,201)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_activity').fetchone()[0],1)

    def test_concurrent_staff_requests_do_not_mix_actor_context(self):
        self.created();second=self.add(self.body(name='Owen Fictional Staff',request_id='second-staff-request')).json()
        def receive(user):return self.client.post('/stock/receive',headers={'X-Demo-Actor':user['id']},json=self.receipt('receipt-'+user['id'],1)).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(list(pool.map(receive,[self.user,second])),[201,201])
        with Store(self.path).connect() as db:
            self.assertEqual({row[0] for row in db.execute('SELECT actor_id FROM stock_receipts')},{self.user['id'],second['id']})
            self.assertEqual({row[0] for row in db.execute('SELECT staff_id FROM staff_activity')},{self.user['id'],second['id']})
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_activity').fetchone()[0],2)
