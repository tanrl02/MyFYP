import unittest
from datetime import datetime,timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
from app.scheduling import MALAYSIA
import test_workflow as workflow


class UsableStockAlertTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def test_staff_scope_legacy_stock_and_no_writes(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.client.get('/stock/usable-alerts',headers={'X-Demo-Actor':actor}).status_code,403)
        response=self.client.get('/stock/usable-alerts',headers=self.staff);self.assertEqual(response.status_code,200)
        report=response.json();self.assertEqual((report['active_items'],report['no_usable_items'],report['low_usable_items'],report['untracked_review_items']),(2,2,0,2))
        self.assertTrue(all(row['stock']==20 and row['usable_units']==0 and row['untracked_units']==20 for row in report['alerts']))
        for private in ('patient','reason','actor_id','prescription_id'):self.assertNotIn(private,response.text)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_expired_held_union_today_boundary_and_item_specific_thresholds(self):
        store=Store(self.path);today=datetime.now(MALAYSIA).date()
        for key,quantity,days,held in [('expired',4,-1,False),('held',3,1,True),('both',2,-1,True),('today',5,0,False)]:
            receipt=store.receive_stock('demo-a',quantity,'Fixture','usable-alert-'+key,'staff-demo',key,(today+timedelta(days=days)).isoformat())
            if held:store.set_batch_hold('demo-a',receipt['id'],True,'Fixture',0,'usable-hold-'+key,'staff-demo')
        store.receive_stock('demo-b',6,'Fixture','usable-above-level','staff-demo','OK',(today+timedelta(days=2)).isoformat())
        report=store.usable_stock_alerts();self.assertEqual(len(report['alerts']),1)
        item=report['alerts'][0];self.assertEqual(item['medicine_id'],'demo-a')
        self.assertEqual((item['tracked_units'],item['usable_units'],item['blocked_tracked_units'],item['untracked_units'],item['stock']),(14,5,9,20,34))
        self.assertEqual(report['low_usable_items'],1);self.assertEqual(report['no_usable_items'],0)
        store.set_medicine_threshold('demo-a',4,0,'usable-lower-level','staff-demo')
        self.assertEqual(store.usable_stock_alerts()['alerts'],[])

    def test_zero_threshold_inactive_empty_and_reopen(self):
        store=Store(self.path);store.set_medicine_threshold('demo-a',0,0,'usable-zero-threshold','staff-demo')
        store.set_medicine_active('demo-b',False,0,'usable-inactive-b','staff-demo')
        report=store.usable_stock_alerts();self.assertEqual(report['active_items'],1);self.assertEqual(len(report['alerts']),1)
        self.assertEqual(report['alerts'][0]['low_stock_threshold'],0)
        with store.connect() as db:before=list(db.iterdump())
        reopened=TestClient(create_app(self.path)).get('/stock/usable-alerts',headers=self.staff).json()
        self.assertEqual(reopened,report)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)
        store.set_medicine_active('demo-a',False,1,'usable-inactive-a','staff-demo')
        empty=store.usable_stock_alerts();self.assertEqual(empty['active_items'],0);self.assertEqual(empty['alerts'],[])
        self.assertEqual((empty['no_usable_items'],empty['low_usable_items'],empty['untracked_review_items']),(0,0,0))

    def test_hold_release_depletion_and_malaysia_date(self):
        store=Store(self.path);today=datetime.now(MALAYSIA).date()
        receipt=store.receive_stock('demo-a',6,'Fixture','usable-changing-batch','staff-demo','LOT',today.isoformat())
        self.assertNotIn('demo-a',{row['medicine_id'] for row in store.usable_stock_alerts()['alerts']})
        store.set_batch_hold('demo-a',receipt['id'],True,'Fixture',0,'usable-change-hold','staff-demo')
        item=next(row for row in store.usable_stock_alerts()['alerts'] if row['medicine_id']=='demo-a');self.assertEqual(item['usable_units'],0)
        store.set_batch_hold('demo-a',receipt['id'],False,'Fixture',1,'usable-change-release','staff-demo')
        store.record_stock_loss('demo-a',6,'damaged','Fixture','usable-depleted-batch','staff-demo',receipt['id'])
        item=next(row for row in store.usable_stock_alerts()['alerts'] if row['medicine_id']=='demo-a');self.assertEqual((item['usable_units'],item['blocked_tracked_units']),(0,0))
        # Aggregation uses the same Malaysia calendar day as dispensing/overview.
        with patch('app.store.datetime') as clock:
            clock.now.return_value=datetime(2031,1,2,0,0,tzinfo=MALAYSIA)
            self.assertEqual(store.usable_stock_alerts()['as_of'],'2031-01-02')
