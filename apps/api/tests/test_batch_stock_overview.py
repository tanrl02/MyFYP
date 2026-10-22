import unittest
from datetime import datetime,timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
from app.scheduling import MALAYSIA
import test_workflow as workflow


class BatchStockOverviewTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def test_staff_scope_missing_item_and_empty_tracked_stock_read_only(self):
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.client.get('/stock/demo-a/batch-overview',headers={'X-Demo-Actor':actor}).status_code,403)
        self.assertEqual(self.client.get('/stock/missing/batch-overview',headers=self.staff).status_code,404)
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        response=self.client.get('/stock/demo-a/batch-overview',headers=self.staff)
        self.assertEqual(response.status_code,200);result=response.json()
        self.assertEqual((result['stock'],result['untracked_units'],result['batches']),(20,20,[]))
        self.assertEqual(result['medicine'],store.catalog()[0])
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_live_totals_expiry_order_depletion_inactive_and_reopening(self):
        store=Store(self.path);today=datetime.now(MALAYSIA).date()
        late=store.receive_stock('demo-a',7,'Fixture','overview-late-receipt','staff-demo','SAME-LOT',(today+timedelta(days=5)).isoformat())
        expired=store.receive_stock('demo-a',4,'Fixture','overview-expired-receipt','staff-demo','EXPIRED',(today-timedelta(days=1)).isoformat())
        current=store.receive_stock('demo-a',2,'Fixture','overview-today-receipt','staff-demo','SAME-LOT',today.isoformat())
        store.record_stock_loss('demo-a',2,'damaged','Fixture','overview-deplete-today','staff-demo',current['id'])
        store.receive_stock('demo-a',3,'Legacy','overview-untracked-receipt','staff-demo')
        store.set_medicine_active('demo-a',False,0,'overview-inactive','staff-demo')
        with store.connect() as db:before=list(db.iterdump())
        result=store.batch_stock_overview('demo-a')
        self.assertEqual([row['receipt_id'] for row in result['batches']],[expired['id'],current['id'],late['id']])
        self.assertEqual([row['remaining_units'] for row in result['batches']],[4,0,7])
        self.assertEqual([row['expired'] for row in result['batches']],[True,False,False])
        self.assertFalse(result['medicine']['active']);self.assertEqual(result['as_of'],today.isoformat())
        self.assertEqual(result['untracked_units'],23)
        self.assertEqual(result['stock'],result['untracked_units']+sum(row['remaining_units'] for row in result['batches']))
        self.assertEqual(TestClient(create_app(self.path)).get('/stock/demo-a/batch-overview',headers=self.staff).json(),result)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_historical_tagged_receipt_not_presented_as_live_batch(self):
        store=Store(self.path);receipt=store.receive_stock('demo-a',3,'Fixture','overview-historical-batch','staff-demo','OLD','2030-01-01')
        with store.connect() as db:db.execute('DELETE FROM receipt_balances WHERE receipt_id=?',(receipt['id'],))
        result=Store(self.path).batch_stock_overview('demo-a')
        self.assertEqual(result['batches'],[]);self.assertEqual(result['stock'],23);self.assertEqual(result['untracked_units'],23)
