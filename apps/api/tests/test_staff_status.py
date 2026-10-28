from concurrent.futures import ThreadPoolExecutor
import sqlite3
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_add_staff as added

class StaffStatusTests(unittest.TestCase):
    setUp=added.AddStaffTests.setUp
    book=added.AddStaffTests.book
    body=added.AddStaffTests.body
    add=added.AddStaffTests.add
    created=added.AddStaffTests.created
    receipt=added.AddStaffTests.receipt
    admin=added.AddStaffTests.admin
    def change(self,active=False,version=0,request='status-request-one',actor=None,staff_id=None,extra=None):
        return self.client.post('/admin/staff/'+(staff_id or self.user['id'])+'/status',headers=actor or self.admin,
            json={'active':active,'version':version,'request_id':request}|(extra or {}))
    def snapshots(self):
        with sqlite3.connect(self.path) as db:
            return {n:list(db.execute('SELECT * FROM "'+n+'" ORDER BY rowid')) for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('staff_status','staff_status_changes')")}

    def test_status_persists_active_roster_and_reactivation_restores_same_profile(self):
        original=self.created();self.assertEqual(self.client.get('/admin/staff-status',headers=self.admin).json(),[{'staff_id':original['id'],'active':True,'version':0,'updated_at':None,'updated_by':None}])
        before=self.snapshots();saved=self.change().json();self.assertEqual((saved['active'],saved['version'],saved['updated_by']),(False,1,'admin-demo'))
        reopened=TestClient(create_app(self.path));self.assertEqual(reopened.get('/admin/staff-status',headers=self.admin).json(),[saved])
        self.assertEqual(reopened.get('/demo/staff',headers=self.staff).json(),[{'id':'staff-demo','name':'Staff Demo'}])
        self.assertEqual(self.snapshots(),before)
        active=self.change(True,1,'status-reactivate-request').json();self.assertEqual(active['version'],2)
        self.assertEqual(self.client.get('/me',headers=self.new).json(),original)
        self.assertIn({'id':original['id'],'name':original['name']},self.client.get('/demo/staff',headers=self.new).json())
        self.assertEqual(self.snapshots(),before)

    def test_permissions_protected_identities_and_strict_validation(self):
        self.created()
        for actor in (self.staff,self.new,self.patient,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.change(actor=actor).status_code,403)
            self.assertEqual(self.client.get('/admin/staff-status',headers=actor).status_code,403)
        for identity in ('staff-demo','admin-demo','patient-ava','doctor-lim','staff-unknown'):
            self.assertEqual(self.change(staff_id=identity).status_code,404)
        for extra in ({'active':0},{'active':'false'},{'version':True},{'version':-1},{'request_id':'x'},{'request_id':'        '},{'role':'admin'}):
            self.assertEqual(self.change(extra=extra).status_code,422,extra)
        self.assertEqual(self.change(True).status_code,422)
        self.assertEqual(self.client.get('/admin/staff-status',headers=self.admin).json()[0]['version'],0)

    def test_inactive_staff_cannot_read_or_write_operational_or_own_endpoints(self):
        self.created();self.book();self.assertEqual(self.change().status_code,200);before=self.snapshots()
        for route in ('/me','/demo/staff','/demo/patients','/doctors','/care','/feedback','/medicines','/admin/users','/staff/schedules'):
            self.assertEqual(self.client.get(route,headers=self.new).status_code,401,route)
        for route,body in [('/stock/receive',self.receipt()),('/queue/call-next',{'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']}),('/admin/patients',self.body()),('/counter-bookings',{'patient_id':'patient-ava','slot_id':self.slot['id'],'request_id':'inactive-counter-request'})]:
            self.assertEqual(self.client.post(route,headers=self.new,json=body).status_code,401,route)
        self.assertIsNone(Store(self.path).user_role(self.user['id']));self.assertFalse(Store(self.path).is_staff(self.user['id']))
        with self.assertRaises(RuleError):Store(self.path).user_profile(self.user['id'])
        self.assertEqual(self.snapshots(),before)
        self.assertEqual(self.client.get('/care',headers=self.patient).status_code,200)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        self.change(True,1,'status-enable-operational');result=self.client.post('/stock/receive',headers=self.new,json=self.receipt());self.assertEqual(result.status_code,201,result.text)

    def test_concurrent_retries_stale_versions_and_old_retry_cannot_undo_reactivation(self):
        self.created();store=Store(self.path);sid=self.user['id']
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:store.save_staff_status(sid,'admin-demo',False,0,'concurrent-status-request'),range(4)))
        self.assertTrue(all(row==results[0] for row in results))
        self.assertEqual(self.change(False,0,'different-stale-request').status_code,409)
        self.assertEqual(self.change(True,1,'concurrent-status-request').status_code,409)
        active=self.change(True,1,'reactivate-new-request').json()
        retried=store.save_staff_status(sid,'admin-demo',False,0,'concurrent-status-request');self.assertEqual(retried,active)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_status_changes').fetchone()[0],2)
        second=self.add(self.body(request_id='second-staff-create')).json()
        self.assertEqual(self.change(staff_id=second['id'],request='concurrent-status-request').status_code,409)

    def test_change_history_failure_rolls_back_status_and_keeps_staff_active(self):
        self.created();store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_status BEFORE INSERT ON staff_status_changes BEGIN SELECT RAISE(ABORT,'Injected status failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.save_staff_status(self.user['id'],'admin-demo',False,0,'rollback-status-request')
        self.assertTrue(store.is_staff(self.user['id']))
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM staff_status').fetchone()[0],0)
            db.execute('DROP TRIGGER fail_status')
        self.assertEqual(self.change().status_code,200)

    def test_deactivation_after_http_admission_rolls_back_schedule_write(self):
        self.created();original=Store.save_schedule_pattern;store=Store(self.path)
        def deactivate_then_write(target,*args,**kwargs):
            store.save_staff_status(self.user['id'],'admin-demo',False,0,'admission-gap-request')
            return original(target,*args,**kwargs)
        pattern={'weekdays':[0],'start_time':'09:00','end_time':'10:00','duration_minutes':30,'capacity':2,'version':0}
        before=self.snapshots()
        with patch.object(Store,'save_schedule_pattern',deactivate_then_write):
            result=self.client.post('/staff/schedules/doctor-lim',headers=self.new,json=pattern)
        self.assertEqual(result.status_code,403,result.text);self.assertEqual(self.snapshots(),before)

    def test_previous_receipt_audit_and_basic_information_survive_disable_enable(self):
        self.created();self.assertEqual(self.client.post('/stock/receive',headers=self.new,json=self.receipt()).status_code,201)
        before=self.snapshots();self.change();self.change(True,1,'preserve-reactivate-request');self.assertEqual(self.snapshots(),before)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT staff_id FROM staff_activity').fetchone()[0],self.user['id'])
            self.assertEqual(db.execute('SELECT actor_id FROM stock_receipts').fetchone()[0],self.user['id'])
