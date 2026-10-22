import sqlite3
import unittest
from datetime import date,datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow


class BatchExpiryTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def receive(self,actor=None,**changes):
        return self.client.post('/stock/receive',headers=actor or self.staff,json=dict(medicine_id='demo-a',quantity=3,reason='Fictional batch delivery',request_id='batch-receipt-one',batch_number='LOT-DEMO-01',expiry_date='2030-02-28')|changes)

    def test_roles_strict_pair_dates_and_no_write_failures(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.receive(actor).status_code,403)
            self.assertEqual(self.client.get('/stock/expiry',headers=actor).status_code,403)
        for changes in ({'batch_number':None},{'expiry_date':None},{'batch_number':''},{'batch_number':'   '},{'batch_number':'x'*61},{'batch_number':12},{'expiry_date':'2030-02-29'},{'expiry_date':'2030-2-28'},{'expiry_date':'2030-02-28T00:00:00Z'},{'expiry_date':20300228},{'expiry_date':'0000-01-01'},{'unexpected':True}):
            self.assertEqual(self.receive(**changes).status_code,422,changes)
        self.assertEqual(self.receive(medicine_id='missing').status_code,404)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_save_reopen_retry_metadata_conflicts_and_legacy_receipts(self):
        response=self.receive(batch_number=' LOT-DEMO-01 ');self.assertEqual(response.status_code,201)
        saved=response.json();self.assertEqual(saved['batch_number'],'LOT-DEMO-01');self.assertEqual(saved['expiry_date'],'2030-02-28')
        self.assertEqual(self.receive().json(),saved)
        for changes in ({'batch_number':'OTHER'},{'expiry_date':'2030-03-01'},{'batch_number':None,'expiry_date':None}):self.assertEqual(self.receive(**changes).status_code,409)
        legacy=self.receive(batch_number=None,expiry_date=None,request_id='batch-legacy-receipt').json()
        self.assertIsNone(legacy['batch_number']);self.assertIsNone(legacy['expiry_date'])
        with Store(self.path).connect() as db:db.execute("UPDATE medicines SET name='Renamed demo',active=0 WHERE id='demo-a'")
        receipts=TestClient(create_app(self.path)).get('/stock',headers=self.staff).json()['receipts']
        batch=next(r for r in receipts if r['id']==saved['id']);self.assertEqual(batch['batch_number'],'LOT-DEMO-01')
        self.assertEqual(batch['expiry_date'],saved['expiry_date']);self.assertEqual(batch['quantity'],3)
        self.assertEqual(Store(self.path).catalog()[0]['stock'],26)

    def test_window_boundaries_receipt_semantics_inactive_and_read_only(self):
        store=Store(self.path);today=date(2032,2,29)
        for offset in (-1,0,1,30,31):
            store.receive_stock('demo-a',1,'Fixture',f'batch-offset-{offset}','staff-demo','SAME-LOT',(today+timedelta(days=offset)).isoformat())
        store.receive_stock('demo-b',1,'Legacy','untracked-expiry','staff-demo')
        with store.connect() as db:
            db.execute("UPDATE medicines SET active=0,stock=0 WHERE id='demo-a'")
            before=list(db.iterdump())
        result=store.stock_expiry(today)
        self.assertEqual((result['expired_receipts'],result['due_soon_receipts'],result['untracked_receipts']),(1,3,1))
        self.assertEqual([r['days_to_expiry'] for r in result['items']],[-1,0,1,30])
        self.assertEqual(result['through_date'],'2032-03-30');self.assertFalse(result['has_more'])
        self.assertTrue(all(not row['active'] and row['quantity']==1 for row in result['items']))
        self.assertEqual(len({row['id'] for row in result['items']}),4) # same lot, distinct receipts
        self.assertEqual(Store(self.path).stock_expiry(today),result)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        # At 16:00 UTC the as-of date advances in Malaysia.
        with patch('app.store.datetime') as clock:
            clock.now.return_value=datetime(2032,2,28,16,tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8)))
            response=self.client.get('/stock/expiry',headers=self.staff)
        self.assertEqual(response.status_code,200);self.assertEqual(response.json(),result)

    def test_counts_and_deterministic_cap_include_older_records(self):
        store=Store(self.path)
        with store.connect() as db:
            db.executemany('INSERT INTO stock_receipts(id,medicine_id,quantity,reason,stock_before,stock_after,actor_id,request_id,created_at,batch_number,expiry_date) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                [(f'expiry-{i:03}','demo-a',1,'Fixture',20,21,'staff-demo',f'expiry-key-{i}','2000-01-01T00:00:00Z','LOT','2030-01-01') for i in range(205)])
        report=store.stock_expiry(date(2030,1,2));self.assertEqual(report['expired_receipts'],205)
        self.assertEqual(len(report['items']),200);self.assertTrue(report['has_more'])
        self.assertEqual([r['id'] for r in report['items']],[f'expiry-{i:03}' for i in range(200)])

    def test_concurrent_receipt_retry_and_audit_insert_failure_rollback(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:self.receive().json(),range(3)))
        self.assertTrue(all(r==results[0] for r in results))
        store=Store(self.path);self.assertEqual(store.catalog()[0]['stock'],23)
        with store.connect() as db:
            db.execute("CREATE TRIGGER fail_batch_insert BEFORE INSERT ON stock_receipts BEGIN SELECT RAISE(ABORT,'test receipt failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.receive_stock('demo-a',2,'Fixture','fail-batch-receipt','staff-demo','LOT2','2030-01-01')
        self.assertEqual(store.catalog()[0]['stock'],23)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM stock_receipts').fetchone()[0],1)

    def test_additive_migration_preserves_old_values_and_retry(self):
        store=Store(self.path);old=store.receive_stock('demo-a',2,'Old delivery','legacy-expiry-retry','staff-demo')
        with store.connect() as db:
            db.execute('ALTER TABLE stock_receipts DROP COLUMN batch_number');db.execute('ALTER TABLE stock_receipts DROP COLUMN expiry_date')
            before=[dict(r) for r in db.execute('SELECT * FROM stock_receipts')]
        store=Store(self.path)
        with store.connect() as db:after=[dict(r) for r in db.execute('SELECT * FROM stock_receipts')]
        self.assertEqual([{k:v for k,v in row.items() if k not in ('batch_number','expiry_date')} for row in after],before)
        self.assertEqual(store.receive_stock('demo-a',2,'Old delivery','legacy-expiry-retry','staff-demo'),old)
        self.assertIsNone(after[0]['batch_number']);self.assertIsNone(after[0]['expiry_date'])
        report=store.stock_expiry(date(2030,1,1));self.assertEqual(report['untracked_receipts'],1);self.assertEqual(report['items'],[])
