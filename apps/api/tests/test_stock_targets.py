import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow
import test_care as care


class StockTargetTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def change(self,target=20,version=0,key='target-change-one',medicine='demo-a',actor=None,**extra):
        return self.client.post(f'/medicines/{medicine}/target',headers=actor or self.staff,
            json=dict(target_stock=target,version=version,request_id=key)|extra)

    def test_roles_strict_bounds_and_no_write_failures(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.change(actor=actor).status_code,403)
        for target in (-1,4,100000,True,'20',20.5):self.assertEqual(self.change(target).status_code,422,target)
        for extra in ({'stock':20},{'version':True},{'version':-1},{'request_id':'x'}):self.assertEqual(self.change(**extra).status_code,422)
        self.assertEqual(self.change(medicine='missing').status_code,404)
        self.assertEqual(self.change(None).status_code,422)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_save_clear_reopen_retries_and_current_stock(self):
        store=Store(self.path);before=store.catalog()[0]
        self.assertIsNone(before['target_stock'])
        saved=self.change().json();self.assertEqual(saved['target_stock'],20);self.assertEqual(saved['version'],1)
        for field in ('name','stock','price_cents','active','low_stock_threshold','strength','form'):self.assertEqual(saved[field],before[field])
        self.assertEqual(self.change().json(),saved)
        self.assertEqual(self.change(21).status_code,409)
        self.assertEqual(self.change(25,key='target-stale-edit').status_code,409)
        self.assertIn(saved,TestClient(create_app(self.path)).get('/stock',headers=self.staff).json()['medicines'])
        store.receive_stock('demo-a',3,'Fictional delivery','target-delivery-one','staff-demo')
        self.assertEqual(store.catalog()[0]['target_stock'],20);self.assertEqual(store.catalog()[0]['stock'],23)
        cleared=self.change(None,1,'clear-target-save').json();self.assertIsNone(cleared['target_stock'])
        self.assertEqual(self.change().json(),saved)
        self.assertIsNone(Store(self.path).catalog()[0]['target_stock'])
        with store.connect() as db:
            rows=db.execute('SELECT * FROM medicine_target_changes ORDER BY from_version').fetchall()
            self.assertEqual(len(rows),2);self.assertIsNone(rows[0]['old_target']);self.assertEqual(rows[1]['old_target'],20)
            self.assertEqual(rows[0]['actor_id'],'staff-demo')

    def test_alert_target_invariant_and_cross_action_stale_edits(self):
        store=Store(self.path)
        self.assertEqual(self.change(5).status_code,200) # equal boundary allowed
        response=self.client.post('/medicines/demo-a/threshold',headers=self.staff,json=dict(low_stock_threshold=6,version=1,request_id='alert-above-target'))
        self.assertEqual(response.status_code,422)
        self.assertEqual(store.catalog()[0]['version'],1)
        self.assertEqual(self.change(30,1,'raise-target-first').status_code,200)
        self.assertEqual(store.set_medicine_threshold('demo-a',10,2,'raise-alert-after','staff-demo')['target_stock'],30)
        self.assertEqual(self.change(9,3,'target-below-alert').status_code,422)
        store.edit_medicine('demo-a','Target fixture name',600,3,'target-name-edit','staff-demo')
        self.assertEqual(self.change(40,3,'target-stale-name').status_code,409)
        self.assertEqual(self.client.post('/medicines/demo-b/status',headers=self.staff,json=dict(active=False,version=0,request_id='target-inactive-item')).status_code,200)
        self.assertEqual(self.change(99999,1,'inactive-target-save',medicine='demo-b').status_code,200)
        self.assertNotIn('demo-b',{m['id'] for m in store.inventory_summary('year',2000)['current_stock']['alerts']})
        self.assertEqual(store.set_medicine_threshold('demo-a',0,4,'zero-alert-test','staff-demo')['low_stock_threshold'],0)
        self.assertEqual(self.change(0,5,'zero-target-test').status_code,200)

    def test_concurrent_target_alert_and_retry_serialisation(self):
        def target():return self.change(10,key='concurrent-target').status_code
        def alert():return self.client.post('/medicines/demo-a/threshold',headers=self.staff,json=dict(low_stock_threshold=15,version=0,request_id='concurrent-alert')).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(target),pool.submit(alert)]
            self.assertEqual(sorted(f.result() for f in futures),[200,409])
        item=Store(self.path).catalog()[0]
        self.assertTrue(item['target_stock'] is None or item['target_stock']>=item['low_stock_threshold'])
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _:self.change(20,medicine='demo-b',key='concurrent-target-retry').status_code,range(2))),[200,200])

    def test_audit_failure_and_issued_records_unchanged(self):
        visit=self.prepare();rx=self.issue(visit).json();bill=self.client.post(f'/visits/{visit}/invoice',headers=self.staff).json()
        store=Store(self.path);before=store.catalog()
        with store.connect() as db:db.execute("CREATE TRIGGER fail_target_audit BEFORE INSERT ON medicine_target_changes BEGIN SELECT RAISE(ABORT,'test target audit'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.set_medicine_target('demo-a',20,0,'failed-target-audit','staff-demo')
        self.assertEqual(store.catalog(),before)
        with store.connect() as db:db.execute('DROP TRIGGER fail_target_audit')
        self.assertEqual(self.change().status_code,200)
        with store.connect() as db:
            self.assertEqual(store.prescription(db,visit),rx);self.assertEqual(store.invoice(db,visit),bill)

    def test_legacy_migration_creation_and_retry_snapshots(self):
        store=Store(self.path)
        with store.connect() as db:
            db.execute('DROP TABLE medicine_target_changes');db.execute('ALTER TABLE medicines DROP COLUMN target_stock')
            before=[dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]
        store=Store(self.path)
        with store.connect() as db:after=[dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]
        self.assertTrue(all(row['target_stock'] is None for row in after))
        self.assertEqual([{k:v for k,v in row.items() if k!='target_stock'} for row in after],before)
        new=store.add_medicine('Target fixture','Demo','Cream',100,'new-target-fixture')
        self.assertIsNone(new['target_stock']);self.assertEqual(store.add_medicine('Target fixture','Demo','Cream',100,'new-target-fixture'),new)
        edited=store.edit_medicine('demo-a','Historic fixture',600,0,'historic-target-edit','staff-demo')
        threshold=store.set_medicine_threshold('demo-a',8,1,'historic-target-alert','staff-demo')
        status=store.set_medicine_active('demo-a',False,2,'historic-target-status','staff-demo')
        with store.connect() as db:
            for table in ('medicine_edits','medicine_threshold_changes','medicine_status_changes'):db.execute(f"UPDATE {table} SET result_json=json_remove(result_json,'$.target_stock')")
        store.set_medicine_target('demo-a',25,3,'latest-target-fixture','staff-demo')
        self.assertEqual(store.edit_medicine('demo-a','Historic fixture',600,0,'historic-target-edit','staff-demo'),edited)
        self.assertEqual(store.set_medicine_threshold('demo-a',8,1,'historic-target-alert','staff-demo'),threshold)
        self.assertEqual(store.set_medicine_active('demo-a',False,2,'historic-target-status','staff-demo'),status)
        self.assertEqual(next(item for item in store.catalog() if item['id']=='demo-a')['target_stock'],25)
