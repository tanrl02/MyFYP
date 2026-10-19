import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_care as care


class StockLossTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def loss(self,actor=None,**changes):
        return self.client.post('/stock/losses',headers=actor or self.staff,json=dict(medicine_id='demo-a',quantity=3,kind='damaged',reason='Fictional damaged packaging',request_id='stock-loss-request')|changes)

    def test_roles_strict_validation_and_underflow_preserve_stock(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.loss(actor).status_code,403)
        for changes in ({'quantity':0},{'quantity':-1},{'quantity':1001},{'quantity':True},{'quantity':1.5},{'quantity':'3'},{'reason':' '},{'reason':'x'*301},{'kind':'expired'},{'kind':None},{'request_id':'short'},{'stock_after':99}):
            self.assertEqual(self.loss(**changes).status_code,422,changes)
        self.assertEqual(self.loss(medicine_id='missing').status_code,404)
        self.assertEqual(self.loss(quantity=21).status_code,409)
        store=Store(self.path);self.assertEqual(store.catalog()[0]['stock'],20)
        self.assertEqual(store.stock()['losses'],[])
        with self.assertRaises(RuleError):store.record_stock_loss('demo-a',3,'lost','Demo','denied-direct-call','doctor-lim')

    def test_record_retry_reopen_and_retained_label_without_stock_or_catalogue_rewrites(self):
        store=Store(self.path);before=store.catalog()[0]
        result=self.loss();self.assertEqual(result.status_code,201);saved=result.json()
        self.assertEqual((saved['quantity'],saved['stock_before'],saved['stock_after']),(3,20,17))
        self.assertEqual(saved['actor_id'],'staff-demo')
        self.assertEqual(self.loss().json(),saved)
        for changes in ({'quantity':2},{'kind':'lost'},{'reason':'Other'},{'medicine_id':'demo-b'}):
            self.assertEqual(self.loss(**changes).status_code,409)
        self.assertEqual(store.stock()['receipts'],[])
        self.assertEqual({k:v for k,v in store.catalog()[0].items() if k!='stock'},{k:v for k,v in before.items() if k!='stock'})
        store.edit_medicine('demo-a','Changed current label',900,0,'loss-history-rename','staff-demo')
        restored=TestClient(create_app(self.path)).get('/stock',headers=self.staff).json()
        self.assertEqual(restored['losses'],[saved]);self.assertEqual(saved['item_label'],'Demo item A (not medication)')
        # Retry after later deduction exhausts stock still returns the first saved result.
        self.loss(quantity=17,kind='lost',request_id='exhaust-loss-stock')
        self.assertEqual(self.loss().json(),saved);self.assertEqual(store.catalog()[0]['stock'],0)

    def test_issued_prescriptions_bills_unchanged_and_dispensing_checks_reduced_stock(self):
        visit=self.prepare();rx=self.issue(visit,items=[dict(medicine_id='demo-a',quantity=20,directions='Fictional')]).json()
        store=Store(self.path);bill=store.generate_invoice(visit,'staff-demo')
        before=self.client.get('/care',headers=self.patient).json()
        self.assertEqual(self.loss().status_code,201)
        self.assertEqual(self.client.get('/care',headers=self.patient).json(),before)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        self.assertEqual(self.client.post('/prescriptions/'+rx['id']+'/dispense',headers=self.staff).status_code,409)
        with store.connect() as db:
            self.assertEqual(store.prescription(db,visit),rx);self.assertEqual(store.invoice(db,visit),bill)
        self.assertEqual(store.catalog()[0]['stock'],17)

    def test_inactive_item_can_record_loss_receiving_and_concurrent_requests_are_safe(self):
        store=Store(self.path);store.set_medicine_active('demo-a',False,0,'inactive-loss-item','staff-demo')
        def same(_):return store.record_stock_loss('demo-a',3,'lost','Fictional missing units','concurrent-loss','staff-demo')
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(same,range(4)))
        self.assertTrue(all(result==results[0] for result in results));self.assertEqual(store.catalog()[0]['stock'],17)
        def movement(index):
            if index==0:return store.receive_stock('demo-a',4,'Fictional delivery','loss-receive-race','staff-demo')
            return store.record_stock_loss('demo-a',2,'damaged','Fictional breakage','loss-receive-race-loss','staff-demo')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(movement,range(2)))
        self.assertEqual(store.catalog()[0]['stock'],19);self.assertFalse(store.catalog()[0]['active'])
        self.assertEqual(len(store.stock()['losses']),2)

    def test_competing_losses_and_dispensing_never_overdraw(self):
        store=Store(self.path)
        def loss(index):
            try:return store.record_stock_loss('demo-a',7,'lost','Fictional loss','competing-loss-'+str(index),'staff-demo')['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(loss,range(3)))
        self.assertEqual(results.count(409),1);self.assertEqual(store.catalog()[0]['stock'],6)
        # A different medicine races dispensing against a deduction.
        visit=self.prepare();rx=self.issue(visit,items=[dict(medicine_id='demo-b',quantity=8,directions='Fictional')]).json()
        def operate(index):
            try:
                if index==0:return store.record_stock_loss('demo-b',15,'damaged','Fictional','loss-dispense-race','staff-demo')
                return store.dispense(rx['id'],'staff-demo')
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(operate,range(2)))
        self.assertEqual(results.count(409),1)
        self.assertIn(next(m for m in store.catalog() if m['id']=='demo-b')['stock'],(5,12))

    def test_audit_failure_rolls_back_and_legacy_initialization_preserves_existing_data(self):
        store=Store(self.path);before=store.stock()
        with store.connect() as db:db.execute('DROP TABLE stock_losses')
        restored=Store(self.path);self.assertEqual(restored.stock(),before)
        with restored.connect() as db:db.execute("CREATE TRIGGER fail_loss_audit BEFORE INSERT ON stock_losses BEGIN SELECT RAISE(ABORT,'test loss audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):restored.record_stock_loss('demo-a',2,'lost','Fictional','rollback-loss-request','staff-demo')
        self.assertEqual(restored.stock(),before)

    def test_daily_report_counts_losses_on_malaysia_activity_date_only(self):
        store=Store(self.path);day=self.slot['clinic_date']
        before=store.daily_report(day)
        start=datetime.fromisoformat(day+'T00:00:00+08:00').astimezone(timezone.utc)
        values=[(start-timedelta(seconds=1),1),(start,2),(start+timedelta(days=1)-timedelta(seconds=1),3),(start+timedelta(days=1),4)]
        for index,(at,quantity) in enumerate(values):
            loss=store.record_stock_loss('demo-a',quantity,'damaged','Fictional date boundary','loss-boundary-'+str(index),'staff-demo')
            with store.connect() as db:db.execute('UPDATE stock_losses SET created_at=? WHERE id=?',(at.isoformat(),loss['id']))
        report=store.daily_report(day)
        self.assertEqual(report['stock']['lost_units'],5)
        self.assertEqual(next(m for m in report['stock']['items'] if m['medicine_id']=='demo-a')['lost'],5)
        self.assertEqual(report['stock']['received_units'],before['stock']['received_units'])
        self.assertEqual(report['stock']['dispensed_units'],before['stock']['dispensed_units'])
        self.assertEqual(report['visits'],before['visits']);self.assertEqual(report['billing'],before['billing'])
        self.assertEqual(report['feedback'],before['feedback'])
        self.assertEqual(self.client.get('/reports/daily',headers=self.patient,params={'clinic_date':day}).status_code,403)
