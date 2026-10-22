import unittest
import sqlite3
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_workflow as workflow


class BatchLossTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def receipt(self,medicine='demo-a',quantity=5,key='batch-loss-receipt',batch='LOT-01'):
        return Store(self.path).receive_stock(medicine,quantity,'Fictional delivery',key,'staff-demo',batch,'2030-01-01')

    def loss(self,receipt=None,**changes):
        return self.client.post('/stock/losses',headers=self.staff,json=dict(medicine_id='demo-a',quantity=2,kind='damaged',reason='Fictional batch damage',request_id='batch-loss-one',receipt_id=receipt)|changes)

    def test_staff_validation_and_cross_medicine_receipts_no_writes(self):
        receipt=self.receipt();other=self.receipt('demo-b',key='other-batch-receipt')
        legacy=Store(self.path).receive_stock('demo-a',1,'Legacy','no-batch-receipt','staff-demo')
        with Store(self.path).connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.client.get('/stock/demo-a/batches',headers={'X-Demo-Actor':actor}).status_code,403)
            self.assertEqual(self.client.post('/stock/losses',headers={'X-Demo-Actor':actor},json=dict(medicine_id='demo-a',quantity=1,kind='lost',reason='Fixture',request_id='denied-batch-loss',receipt_id=receipt['id'])).status_code,403)
        for value,status in [('',422),(1,422),('missing',404),(other['id'],422),(legacy['id'],422)]:self.assertEqual(self.loss(value).status_code,status)
        self.assertEqual(self.client.get('/stock/missing/batches',headers=self.staff).status_code,404)
        with Store(self.path).connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_linked_loss_snapshot_retry_reopen_and_allowance(self):
        receipt=self.receipt();saved=self.loss(receipt['id']).json()
        self.assertEqual((saved['stock_before'],saved['stock_after']),(25,23));self.assertEqual(saved['receipt_id'],receipt['id'])
        self.assertEqual((saved['batch_number'],saved['expiry_date']),('LOT-01','2030-01-01'))
        self.assertEqual(self.loss(receipt['id']).json(),saved)
        self.assertEqual(self.loss(None).status_code,409)
        self.assertEqual(self.loss(receipt['id'],quantity=3).status_code,409)
        rows=TestClient(create_app(self.path)).get('/stock/demo-a/batches',headers=self.staff).json()
        self.assertEqual((rows[0]['quantity'],rows[0]['loss_units'],rows[0]['loss_allowance']),(5,2,3))
        self.assertEqual(self.loss(receipt['id'],quantity=4,request_id='over-batch-limit').status_code,409)
        self.assertEqual(self.loss(receipt['id'],quantity=3,kind='lost',request_id='exhaust-batch-allowance').status_code,201)
        self.assertEqual(Store(self.path).stock_batches('demo-a')[0]['loss_allowance'],0)
        self.assertEqual(self.loss(receipt['id'],quantity=1,request_id='batch-already-exhausted').status_code,409)
        self.assertEqual(self.loss(receipt['id']).json(),saved) # retry after allowance exhausted
        self.assertEqual(Store(self.path).stock()['losses'][-1],saved)

    def test_separate_receipts_global_stock_and_unassigned_are_not_batch_balances(self):
        first=self.receipt(quantity=4);second=self.receipt(quantity=6,key='second-same-lot')
        self.assertEqual(len(Store(self.path).stock_batches('demo-a')),2)
        self.loss(first['id'])
        unassigned=self.loss(None,quantity=1,request_id='unassigned-after-batch').json();self.assertIsNone(unassigned['receipt_id'])
        rows={row['receipt_id']:row for row in Store(self.path).stock_batches('demo-a')}
        self.assertEqual(rows[first['id']]['loss_allowance'],2);self.assertEqual(rows[second['id']]['loss_allowance'],6)
        with Store(self.path).connect() as db:db.execute("UPDATE medicines SET stock=1,active=0 WHERE id='demo-a'")
        self.assertEqual(self.loss(second['id'],quantity=2,request_id='batch-total-underflow').status_code,409)
        self.assertEqual(self.loss(second['id'],quantity=1,request_id='inactive-batch-loss').status_code,201)
        # Receipt expiry review still retains all records; allowance is not live stock.
        self.assertEqual(len(Store(self.path).stock_expiry(date(2030,1,2))['items']),2)

    def test_concurrent_losses_cap_receipt_and_retries_once(self):
        receipt=self.receipt(quantity=3)
        def deduct(index):
            try:return Store(self.path).record_stock_loss('demo-a',2,'damaged','Fixture',f'batch-race-{index}','staff-demo',receipt['id'])['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(deduct,range(2)))
        self.assertEqual(results.count(409),1);self.assertEqual(Store(self.path).catalog()[0]['stock'],21)
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:Store(self.path).record_stock_loss('demo-a',1,'lost','Fixture','batch-identical-race','staff-demo',receipt['id']),range(3)))
        self.assertTrue(all(row==results[0] for row in results));self.assertEqual(Store(self.path).stock_batches('demo-a')[0]['loss_units'],3)

    def test_failed_insert_rolls_back_and_invalid_link_rolls_back_stock(self):
        receipt=self.receipt();store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        self.assertEqual(self.loss('missing').status_code,404)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_linked_loss BEFORE INSERT ON stock_losses BEGIN SELECT RAISE(ABORT,'test linked loss'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.record_stock_loss('demo-a',2,'lost','Fixture','failed-linked-loss','staff-demo',receipt['id'])
        self.assertEqual(store.catalog()[0]['stock'],25);self.assertEqual(store.stock_batches('demo-a')[0]['loss_units'],0)

    def test_legacy_migration_retains_old_values_and_retry(self):
        store=Store(self.path);saved=store.record_stock_loss('demo-a',1,'lost','Legacy','legacy-linked-loss','staff-demo')
        with store.connect() as db:
            for column in ('receipt_id','batch_number','expiry_date'):db.execute('ALTER TABLE stock_losses DROP COLUMN '+column)
            before=[dict(row) for row in db.execute('SELECT * FROM stock_losses')]
        store=Store(self.path)
        with store.connect() as db:after=[dict(row) for row in db.execute('SELECT * FROM stock_losses')]
        self.assertEqual([{k:v for k,v in row.items() if k not in ('receipt_id','batch_number','expiry_date')} for row in after],before)
        self.assertEqual(store.record_stock_loss('demo-a',1,'lost','Legacy','legacy-linked-loss','staff-demo'),saved)
        self.assertEqual(store.stock_batches('demo-a'),[])
