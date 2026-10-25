from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_care as care


class UserInformationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    admin={'X-Demo-Actor':'admin-demo'}

    def body(self,**overrides):
        return {'name':'Ava Updated Demo','phone':'+60 12-345 6789','email':'ava@example.test','version':0}|overrides

    def save(self,user='patient-ava',body=None,actor=None):
        return self.client.post('/admin/users/'+user,headers=actor or self.admin,json=body if body is not None else self.body())

    def test_admin_directory_contains_basic_information_only_and_other_roles_only_see_self(self):
        response=self.client.get('/admin/users',headers=self.admin);self.assertEqual(response.status_code,200)
        users=response.json();self.assertEqual(len(users),6)
        self.assertEqual({row['role'] for row in users},{'patient','doctor','staff','admin'})
        for row in users:self.assertEqual(set(row),{'id','role','name','phone','email','version','updated_at','updated_by'})
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita','staff-demo'):
            headers={'X-Demo-Actor':actor}
            self.assertEqual(self.client.get('/admin/users',headers=headers).status_code,403)
            self.assertEqual(self.save(actor=headers).status_code,403)
            own=self.client.get('/me',headers=headers).json();self.assertEqual(own['id'],actor)
            self.assertEqual(self.client.get('/me?user_id=patient-ava',headers=headers).json()['id'],actor)
        self.assertEqual(self.client.get('/admin/users').status_code,422)
        self.assertEqual(self.client.get('/admin/users',headers={'X-Demo-Actor':'unknown'}).status_code,401)

    def test_admin_has_no_implicit_clinical_or_operational_access(self):
        visit=self.prepare(completed=False);self.issue(visit)
        routes=['/care','/consultations','/assessment-shares','/feedback','/assessments','/medicines',
                '/staff/slots',f'/visits/{visit}/consultation',f'/visits/{visit}/history']
        for route in routes:
            response=self.client.get(route,headers=self.admin)
            self.assertIn(response.status_code,(401,403),(route,response.status_code))
        self.assertEqual(self.client.post(f'/queue/{visit}/complete',headers=self.admin).status_code,401)
        with self.assertRaises(RuleError):Store(self.path).care('admin-demo')

    def test_saved_patient_information_persists_without_changing_ids_roles_or_other_records(self):
        visit=self.prepare(completed=False);rx=self.issue(visit).json();store=Store(self.path)
        def snapshot():
            with store.connect() as db:return {name:[tuple(row) for row in db.execute('SELECT * FROM "'+name+'" ORDER BY rowid')] for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='user_profiles'")}
        before=snapshot();saved=self.save().json()
        self.assertEqual(saved['id'],'patient-ava');self.assertEqual(saved['role'],'patient')
        self.assertEqual(saved['version'],1);self.assertTrue(saved['updated_at']);self.assertEqual(saved['updated_by'],'admin-demo')
        self.assertEqual(snapshot(),before)
        owned=self.client.get('/care',headers=self.patient).json()[0]
        self.assertEqual(owned['visit']['patient_name'],'Ava Updated Demo');self.assertEqual(owned['visit']['id'],visit)
        self.assertEqual(owned['prescription'],rx)
        self.assertNotIn(saved['phone'],str(owned));self.assertNotIn(saved['email'],str(owned))
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/me',headers=self.patient).json(),saved)
        self.assertIn(saved,reopened.get('/admin/users',headers=self.admin).json())

    def test_doctor_name_updates_profiles_slots_records_without_replacing_specialty_or_historical_messages(self):
        visit=self.prepare(completed=False);store=Store(self.path)
        profiles=self.client.get('/doctors',headers=self.patient).json();old=next(row for row in profiles if row['doctor_id']==self.slot['doctor_id'])
        with store.connect() as db:messages=[tuple(row) for row in db.execute('SELECT * FROM patient_notifications')]
        result=self.save(self.slot['doctor_id'],self.body(name='Dr Fictional Updated',phone='',email='doctor@example.test')).json()
        current=next(row for row in self.client.get('/doctors',headers=self.patient).json() if row['doctor_id']==self.slot['doctor_id'])
        self.assertEqual(current,old|{'doctor_name':result['name']})
        owned=next(row for row in self.client.get('/care',headers=self.patient).json() if row['visit']['id']==visit)
        self.assertEqual(owned['visit']['doctor_name'],result['name'])
        for slot in self.client.get('/slots').json():
            if slot['doctor_id']==self.slot['doctor_id']:self.assertEqual(slot['doctor_name'],result['name'])
        with store.connect() as db:self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM patient_notifications')],messages)

    def test_validation_role_and_id_changes_and_unknown_users_are_rejected(self):
        invalid=[self.body(name=' '),self.body(name='x'*101),self.body(name='Line\nBreak'),self.body(phone='123'),
                 self.body(phone='abc1234567'),self.body(phone='1234567890123456'),self.body(email='invalid'),
                 self.body(email='a @example.test'),self.body(version=True),self.body(version=-1),
                 self.body()|{'role':'doctor'},self.body()|{'id':'patient-noah'},self.body()|{'allergies':'secret'}]
        for body in invalid:self.assertEqual(self.save(body=body).status_code,422,body)
        self.assertEqual(self.save(user='missing').status_code,404)
        self.assertEqual(self.client.get('/me',headers=self.patient).json()['version'],0)
        saved=self.save(body=self.body(name='  Ava Updated Demo  ',phone=' ',email=' ')).json()
        self.assertEqual((saved['name'],saved['phone'],saved['email']),('Ava Updated Demo','',''))

    def test_stale_writers_cannot_overwrite_and_exact_retry_preserves_version_timestamp(self):
        saved=self.save().json();self.assertEqual(self.save().json(),saved)
        self.assertEqual(self.save(body=self.body(name='Stale edit')).status_code,409)
        second=self.save(body=self.body(name='Second updated name',version=1)).json()
        self.assertEqual(second['version'],2)
        self.assertEqual(self.save().status_code,409)
        self.assertEqual(self.client.get('/me',headers=self.patient).json(),second)

    def test_concurrent_edits_preserve_one_winner(self):
        store=Store(self.path)
        def attempt(name):
            try:return store.save_user_profile('patient-ava','admin-demo',name,'','',0)
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['First fictional name','Second fictional name']))
        self.assertEqual(sum(row==409 for row in results),1)
        self.assertEqual(self.client.get('/me',headers=self.patient).json()['version'],1)

    def test_staff_admin_and_patient_contact_details_remain_separate_after_edits(self):
        for user,name in [('staff-demo','Updated Staff Demo'),('admin-demo','Updated Admin Demo'),('patient-noah','Noah Updated Demo')]:
            self.assertEqual(self.save(user,self.body(name=name,email=user+'@example.test')).status_code,200)
        for user,name in [('staff-demo','Updated Staff Demo'),('admin-demo','Updated Admin Demo'),('patient-noah','Noah Updated Demo')]:
            own=self.client.get('/me',headers={'X-Demo-Actor':user}).json()
            self.assertEqual(own['id'],user);self.assertEqual(own['name'],name)
        self.assertEqual(self.client.get('/me',headers=self.patient).json()['name'],'Ava Demo')

    def test_name_resolution_reuses_the_current_transaction_without_opening_a_nested_reader(self):
        visit=self.prepare(completed=False);store=Store(self.path)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE user_profiles SET name='Transaction-visible name' WHERE id='patient-ava'")
            # Opening a second connection here would both miss this update and
            # risk blocking a pending writer during ordinary polling.
            def forbidden():raise AssertionError('Nested connection opened during name resolution')
            store.connect=forbidden
            self.assertEqual(store.record(db,visit)['patient_name'],'Transaction-visible name')
            profile=db.execute("SELECT * FROM doctor_profiles WHERE doctor_id=?",(self.slot['doctor_id'],)).fetchone()
            self.assertEqual(store.doctor_profile(db,profile)['doctor_id'],self.slot['doctor_id'])
            self.assertEqual(store.managed_slot(db,self.slot['id'])['doctor_id'],self.slot['doctor_id'])
            db.rollback()
