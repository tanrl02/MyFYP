import json
import sqlite3
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_care as care


class BatchHoldTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def receipt(self,medicine='demo-a',key='hold-receipt',expiry='2099-12-31'):
        return Store(self.path).receive_stock(medicine,5,'Fictional delivery',key,'staff-demo','HOLD-DEMO',expiry)

    def change(self,receipt,held=True,version=0,key='hold-change-one',medicine='demo-a',actor=None,**extra):
        return self.client.post(f'/stock/{medicine}/batches/{receipt}/hold',headers=actor or self.staff,json=dict(held=held,version=version,reason='Fictional packaging review',request_id=key)|extra)

    def test_roles_validation_missing_wrong_medicine_and_no_writes(self):
        receipt=self.receipt();store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.change(receipt['id'],actor={'X-Demo-Actor':actor}).status_code,403)
        for extra in ({'held':'true'},{'held':1},{'version':True},{'version':-1},{'reason':' '},{'reason':'x'*301},{'request_id':'x'},{'remaining_units':10}):self.assertEqual(self.change(receipt['id'],**extra).status_code,422,extra)
        self.assertEqual(self.change('missing').status_code,404)
        self.assertEqual(self.change(receipt['id'],medicine='demo-b').status_code,404)
        self.assertEqual(self.change(receipt['id'],held=False).status_code,422)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_persistence_audit_retries_stale_cycles_and_stock_unchanged(self):
        receipt=self.receipt();store=Store(self.path);before=store.catalog()
        held=self.change(receipt['id']).json();self.assertIs(held['held'],True);self.assertEqual(held['hold_version'],1)
        self.assertEqual(self.change(receipt['id']).json(),held)
        self.assertEqual(self.change(receipt['id'],reason='Other reason').status_code,409)
        self.assertEqual(self.change(receipt['id'],held=False,key='stale-release').status_code,409)
        released=self.change(receipt['id'],False,1,'release-hold-one',reason='Fictional inspection passed').json()
        self.assertFalse(released['held']);self.assertIsNone(released['hold_reason']);self.assertEqual(released['hold_version'],2)
        self.assertEqual(self.change(receipt['id']).json(),held) # replay cannot reapply old hold
        current=TestClient(create_app(self.path)).get('/stock/demo-a/batch-overview',headers=self.staff).json()['batches'][0]
        self.assertFalse(current['held']);self.assertEqual(current['hold_version'],2)
        self.assertEqual(store.catalog(),before)
        with store.connect() as db:
            rows=db.execute('SELECT * FROM batch_hold_changes ORDER BY from_version').fetchall()
            self.assertEqual(len(rows),2);self.assertEqual(rows[1]['reason'],'Fictional inspection passed');self.assertEqual(rows[0]['actor_id'],'staff-demo')
            self.assertEqual(db.execute('SELECT remaining_units FROM receipt_balances').fetchone()[0],5)
        # Fixture for visual QA, containing only isolated synthetic data.
        fixture=store.batch_stock_overview('demo-a');self.change(receipt['id'],True,2,'rehold-preview')
        fixture=store.batch_stock_overview('demo-a');target=Path(__file__).resolve().parents[3]/'tmp/batch-hold-fixture.json';target.write_text(json.dumps(fixture),encoding='utf-8')

    def test_held_batch_blocks_dispensing_and_cannot_be_untracked(self):
        receipt=self.receipt();store=Store(self.path)
        rx=self.issue(self.prepare()).json();self.change(receipt['id'])
        with self.assertRaises(RuleError):store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])
        self.assertEqual(store.dispensing_stock(rx['id'])['allocations'],[])
        store.record_stock_loss('demo-a',20,'lost','Fixture','hold-untracked-depleted','staff-demo')
        with self.assertRaises(RuleError):store.dispense(rx['id'],'staff-demo')
        self.assertEqual(store.catalog()[0]['stock'],5)
        self.change(receipt['id'],False,1,'hold-release-for-use')
        self.assertEqual(store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])['status'],'dispensed')
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],3)

    def test_release_retains_expiry_block_and_held_loss_allowed(self):
        receipt=self.receipt(expiry='2000-01-01');store=Store(self.path)
        self.change(receipt['id']);store.record_stock_loss('demo-a',2,'damaged','Fixture','held-damage-permitted','staff-demo',receipt['id'])
        source=store.batch_stock_overview('demo-a')['batches'][0]
        self.assertTrue(source['held']);self.assertEqual(source['remaining_units'],3)
        self.change(receipt['id'],False,1,'expired-hold-release')
        rx=self.issue(self.prepare()).json()
        with self.assertRaises(RuleError):store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])
        self.assertTrue(store.batch_stock_overview('demo-a')['batches'][0]['expired'])

    def test_concurrent_hold_changes_and_dispense_order_are_serialised(self):
        receipt=self.receipt();store=Store(self.path)
        def hold(index):
            try:return store.set_batch_hold('demo-a',receipt['id'],True,f'Reason{index}',0,f'competing-hold-{index}','staff-demo')
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(hold,range(2)))
        self.assertEqual(results.count(409),1)
        store.set_batch_hold('demo-a',receipt['id'],False,'Release',1,'race-release-first','staff-demo')
        rx=self.issue(self.prepare()).json()
        def operate(index):
            try:
                if index==0:return store.set_batch_hold('demo-a',receipt['id'],True,'Review again',2,'hold-dispense-race','staff-demo')
                return store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(operate,range(2)))
        source=store.batch_stock_overview('demo-a')['batches'][0];self.assertTrue(source['held'])
        self.assertEqual(source['remaining_units'],5 if 409 in results else 3)
        self.assertEqual(len(store.dispensing_stock(rx['id'])['allocations']),0 if 409 in results else 1)

    def test_multi_item_hold_failure_and_hold_audit_failure_rollback(self):
        first=self.receipt();second=self.receipt('demo-b','held-second-medicine')
        self.change(second['id'],medicine='demo-b')
        rx=self.issue(self.prepare(),items=[dict(medicine_id='demo-a',quantity=2,directions='Fixture'),dict(medicine_id='demo-b',quantity=2,directions='Fixture')]).json()
        store=Store(self.path)
        with self.assertRaises(RuleError):store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=first['id'],quantity=2),dict(medicine_id='demo-b',receipt_id=second['id'],quantity=2)])
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],5)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_hold_audit BEFORE INSERT ON batch_hold_changes BEGIN SELECT RAISE(ABORT,'test hold audit'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.set_batch_hold('demo-a',first['id'],True,'Fixture',0,'failed-hold-audit','staff-demo')
        source=store.batch_stock_overview('demo-a')['batches'][0];self.assertFalse(source['held']);self.assertEqual(source['hold_version'],0)

    def test_legacy_migration_defaults_and_identical_retries_once(self):
        receipt=self.receipt();store=Store(self.path)
        with store.connect() as db:
            db.execute('DROP TABLE batch_hold_changes')
            for column in ('held','hold_reason','hold_version','hold_updated_at'):db.execute('ALTER TABLE receipt_balances DROP COLUMN '+column)
            before=[dict(row) for row in db.execute('SELECT * FROM receipt_balances')]
        store=Store(self.path)
        source=store.batch_stock_overview('demo-a')['batches'][0];self.assertFalse(source['held']);self.assertEqual(source['hold_version'],0)
        with store.connect() as db:self.assertEqual([dict(receipt_id=row['receipt_id'],remaining_units=row['remaining_units']) for row in db.execute('SELECT * FROM receipt_balances')],before)
        def save(_):return store.set_batch_hold('demo-a',receipt['id'],True,'Fixture',0,'same-hold-request','staff-demo')
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(save,range(3)))
        self.assertTrue(all(row==results[0] for row in results))
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM batch_hold_changes').fetchone()[0],1)
