import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow
import test_care as care


class StockThresholdTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def change(self,level=10,version=0,key='threshold-change-one',medicine='demo-a',actor=None,**extra):
        return self.client.post(f'/medicines/{medicine}/threshold',headers=actor or self.staff,
            json=dict(low_stock_threshold=level,version=version,request_id=key)|extra)

    def test_scope_validation_and_no_side_effects(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.change(actor=actor).status_code,403)
        for level in (-1,100000,True,1.5,'10',None):self.assertEqual(self.change(level).status_code,422)
        for extra in ({'stock':90},{'version':True},{'version':-1},{'request_id':'x'}):self.assertEqual(self.change(**extra).status_code,422)
        self.assertEqual(self.change(medicine='missing').status_code,404)
        self.assertEqual(self.change(5).status_code,422)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_persistence_retry_audit_and_stale_catalogue(self):
        store=Store(self.path);before=store.catalog()[0]
        saved=self.change(10).json()
        self.assertEqual(saved['low_stock_threshold'],10);self.assertEqual(saved['version'],1)
        for field in ('stock','name','strength','form','price_cents','active'):self.assertEqual(saved[field],before[field])
        self.assertEqual(self.change().json(),saved)
        self.assertEqual(self.change(11).status_code,409)
        self.assertEqual(self.change(12,key='stale-threshold').status_code,409)
        self.assertEqual(self.client.post('/medicines/demo-a/edit',headers=self.staff,json=dict(name='Stale',price_cents=600,version=0,request_id='stale-name-change')).status_code,409)
        self.assertEqual(self.client.post('/medicines/demo-a/status',headers=self.staff,json=dict(active=False,version=0,request_id='stale-status-change')).status_code,409)
        self.assertIn(saved,TestClient(create_app(self.path)).get('/stock',headers=self.staff).json()['medicines'])
        self.assertEqual(self.change(0,1,'threshold-zero-save').status_code,200)
        self.assertEqual(self.change().json(),saved) # original retry after a later edit
        with store.connect() as db:
            rows=db.execute('SELECT * FROM medicine_threshold_changes ORDER BY from_version').fetchall()
            self.assertEqual(len(rows),2);self.assertEqual(rows[0]['old_threshold'],5);self.assertEqual(rows[0]['actor_id'],'staff-demo')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM stock_receipts').fetchone()[0],0)
        # Another catalogue action also blocks an obsolete threshold edit.
        latest=next(m for m in store.catalog() if m['id']=='demo-a')
        store.edit_medicine('demo-a','Updated',600,latest['version'],'threshold-name-change','staff-demo')
        self.assertEqual(self.change(9,latest['version'],'threshold-after-name').status_code,409)

    def test_item_specific_report_boundaries_zero_inactive_and_history(self):
        store=Store(self.path)
        with store.connect() as db:db.execute('UPDATE medicines SET stock=10')
        self.assertEqual(self.change(10).status_code,200)
        def snapshot():return store.inventory_summary('year',2000)['current_stock']
        report=snapshot();self.assertEqual(report['low_stock_items'],1);self.assertEqual(report['out_of_stock_items'],0)
        self.assertEqual([(a['medicine_id'],a['low_stock_threshold']) for a in report['alerts']],[('demo-a',10)])
        self.assertEqual(self.change(0,1,'zero-alert-level').status_code,200)
        self.assertEqual(snapshot()['low_stock_items'],0)
        with store.connect() as db:db.execute("UPDATE medicines SET stock=0 WHERE id='demo-a'")
        report=snapshot();self.assertEqual(report['low_stock_items'],0);self.assertEqual(report['out_of_stock_items'],1)
        self.assertEqual(report['alerts'][0]['low_stock_threshold'],0)
        with store.connect() as db:db.execute("UPDATE medicines SET active=0 WHERE id='demo-a'")
        self.assertEqual(snapshot()['alerts'],[])
        self.assertEqual(store.inventory_summary('month',2030,1)['units'],dict(received=0,dispensed=0,damaged=0,lost=0,net_change=0))

    def test_concurrent_edits_and_identical_retries(self):
        def save(pair):
            level,key=pair
            return self.change(level,key=key).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,[(10,'threshold-race-one'),(12,'threshold-race-two')])),[200,409])
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(lambda _:self.change(99999,0,'threshold-retry-max',medicine='demo-b').status_code,range(2))),[200,200])
        with Store(self.path).connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM medicine_threshold_changes').fetchone()[0],2)

    def test_legacy_migration_preserves_columns_and_defaults_new_items(self):
        store=Store(self.path)
        with store.connect() as db:
            db.execute('DROP TABLE medicine_threshold_changes')
            db.execute('ALTER TABLE medicines DROP COLUMN low_stock_threshold')
            before=[dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]
        migrated=Store(self.path)
        with migrated.connect() as db:
            after=[dict(r) for r in db.execute('SELECT * FROM medicines ORDER BY id')]
        self.assertEqual([{k:v for k,v in row.items() if k!='low_stock_threshold'} for row in after],before)
        self.assertTrue(all(row['low_stock_threshold']==5 for row in after))
        new=migrated.add_medicine('New fictional item','Demo','Cream',100,'threshold-new-item')
        self.assertEqual(new['low_stock_threshold'],5)
        self.assertEqual(migrated.add_medicine('New fictional item','Demo','Cream',100,'threshold-new-item'),new)

    def test_audit_failure_rolls_back_and_prescriptions_bills_unchanged(self):
        visit=self.prepare();rx=self.issue(visit).json()
        bill=self.client.post(f'/visits/{visit}/invoice',headers=self.staff).json()
        store=Store(self.path);before=store.catalog()
        with store.connect() as db:
            db.execute("CREATE TRIGGER threshold_audit_failure BEFORE INSERT ON medicine_threshold_changes BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.set_medicine_threshold('demo-a',10,0,'threshold-failed-audit','staff-demo')
        self.assertEqual(store.catalog(),before)
        with store.connect() as db:db.execute('DROP TRIGGER threshold_audit_failure')
        self.assertEqual(self.change(10).status_code,200)
        with store.connect() as db:
            self.assertEqual(store.prescription(db,visit),rx);self.assertEqual(store.invoice(db,visit),bill)

    def test_legacy_edit_status_retry_defaults_do_not_revert_latest_level(self):
        store=Store(self.path)
        edited=store.edit_medicine('demo-a','Legacy name',600,0,'legacy-alert-edit','staff-demo')
        status=store.set_medicine_active('demo-a',False,1,'legacy-alert-status','staff-demo')
        with store.connect() as db:
            for table in ('medicine_edits','medicine_status_changes'):
                db.execute(f"UPDATE {table} SET result_json=json_remove(result_json,'$.low_stock_threshold')")
        store.set_medicine_threshold('demo-a',20,2,'latest-alert-level','staff-demo')
        self.assertEqual(store.edit_medicine('demo-a','Legacy name',600,0,'legacy-alert-edit','staff-demo'),edited)
        self.assertEqual(store.set_medicine_active('demo-a',False,1,'legacy-alert-status','staff-demo'),status)
        self.assertEqual(store.catalog()[0]['low_stock_threshold'],20)

if __name__=='__main__':unittest.main()
