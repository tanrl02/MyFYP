import unittest
from pathlib import Path
import json
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class BatchHistoryTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def receipt(self,quantity=10,key='history-batch-receipt'):
        return Store(self.path).receive_stock('demo-a',quantity,'Fictional delivery',key,'staff-demo','HISTORY-LOT','2099-12-31')

    def get(self,receipt,medicine='demo-a',actor=None):
        return self.client.get(f'/stock/{medicine}/batches/{receipt}/history',headers=actor or self.staff)

    def test_scope_missing_wrong_item_and_historical_receipt_no_writes(self):
        receipt=self.receipt();store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.get(receipt['id'],actor={'X-Demo-Actor':actor}).status_code,403)
        for receipt_id,medicine in [('missing','demo-a'),(receipt['id'],'missing'),(receipt['id'],'demo-b')]:self.assertEqual(self.get(receipt_id,medicine).status_code,404)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        with store.connect() as db:db.execute('DELETE FROM receipt_balances WHERE receipt_id=?',(receipt['id'],))
        self.assertEqual(self.get(receipt['id']).status_code,404)

    def test_all_movements_reconcile_order_offsets_retries_and_reopening(self):
        receipt=self.receipt();store=Store(self.path)
        rx=self.issue(self.prepare()).json()
        store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])
        damaged=store.record_stock_loss('demo-a',1,'damaged','Fictional broken packaging','history-batch-damage','staff-demo',receipt['id'])
        lost=store.record_stock_loss('demo-a',3,'lost','Fictional missing units','history-batch-lost','staff-demo',receipt['id'])
        store.dispense(rx['id'],'staff-demo',[dict(medicine_id='demo-a',receipt_id=receipt['id'],quantity=2)])
        store.record_stock_loss('demo-a',1,'damaged','Fictional broken packaging','history-batch-damage','staff-demo',receipt['id'])
        with store.connect() as db:
            db.execute('UPDATE stock_receipts SET created_at=? WHERE id=?',('2026-10-22T00:00:00Z',receipt['id']))
            db.execute('UPDATE dispensing_allocations SET created_at=? WHERE receipt_id=?',('2026-10-22T10:00:00+08:00',receipt['id']))
            db.execute('UPDATE stock_losses SET created_at=? WHERE id=?',('2026-10-22T01:00:00Z',damaged['id']))
            db.execute('UPDATE stock_losses SET created_at=? WHERE id=?',('2026-10-22T03:00:00Z',lost['id']))
            before=list(db.iterdump())
        response=self.get(receipt['id']);self.assertEqual(response.status_code,200);history=response.json()
        self.assertEqual(history['totals'],dict(received=10,dispensed=2,damaged=1,lost=3))
        self.assertEqual([row['kind'] for row in history['movements']],['received','damaged','dispensed','lost'])
        self.assertEqual([row['balance_after'] for row in history['movements']],[10,9,7,4])
        self.assertEqual([row['change'] for row in history['movements']],[10,-1,-2,-3])
        self.assertEqual(history['remaining_units'],4);self.assertEqual(history['calculated_remaining'],4);self.assertTrue(history['reconciled'])
        self.assertTrue(all(row['actor_id']=='staff-demo' for row in history['movements']))
        for private in ('patient_id','patient_name','directions','prescription_id','booking_id'):self.assertNotIn(private,response.text)
        self.assertEqual(TestClient(create_app(self.path)).get(f"/stock/demo-a/batches/{receipt['id']}/history",headers=self.staff).json(),history)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        # Ignored artifact for visual QA of the actual history renderer; no normal demo records touched.
        target=Path(__file__).resolve().parents[3]/'tmp/batch-history-fixture.json'
        target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(history),encoding='utf-8')

    def test_same_lot_receipts_unassigned_losses_inactive_and_depleted(self):
        first=self.receipt(4);second=self.receipt(3,'history-second-same-lot');store=Store(self.path)
        store.record_stock_loss('demo-a',4,'lost','Fixture','history-deplete-first','staff-demo',first['id'])
        store.record_stock_loss('demo-a',1,'damaged','Fixture','history-damage-second','staff-demo',second['id'])
        store.record_stock_loss('demo-a',2,'lost','Unassigned','history-unassigned-loss','staff-demo')
        store.set_medicine_active('demo-a',False,0,'history-inactive','staff-demo')
        one=self.get(first['id']).json();two=self.get(second['id']).json()
        self.assertEqual(one['remaining_units'],0);self.assertEqual(one['totals']['lost'],4);self.assertTrue(one['reconciled'])
        self.assertEqual(two['remaining_units'],2);self.assertEqual(two['totals']['lost'],0);self.assertEqual(two['totals']['damaged'],1)
        self.assertEqual(one['batch_number'],two['batch_number']);self.assertNotEqual(one['receipt_id'],two['receipt_id'])

    def test_receipt_only_history_and_difference_exposed_not_repaired(self):
        receipt=self.receipt(5);history=self.get(receipt['id']).json()
        self.assertEqual(len(history['movements']),1);self.assertEqual(history['totals'],dict(received=5,dispensed=0,damaged=0,lost=0));self.assertTrue(history['reconciled'])
        store=Store(self.path)
        with store.connect() as db:
            db.execute('UPDATE receipt_balances SET remaining_units=4 WHERE receipt_id=?',(receipt['id'],))
            before=list(db.iterdump())
        history=self.get(receipt['id']).json();self.assertFalse(history['reconciled'])
        self.assertEqual((history['calculated_remaining'],history['remaining_units']),(5,4))
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
