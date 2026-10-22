import unittest
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from app.scheduling import MALAYSIA
from app.store import Store,RuleError
from app.main import create_app
from fastapi.testclient import TestClient
import test_care as care


class BatchDispensingTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def receive(self,quantity=5,days=30,medicine='demo-a',key='dispensing-batch-receipt'):
        return Store(self.path).receive_stock(medicine,quantity,'Fixture',key,'staff-demo','LOT-FICTIONAL',(datetime.now(MALAYSIA).date()+timedelta(days=days)).isoformat())

    def prescription(self,items=None):
        return self.issue(self.prepare(),items=items).json()

    def dispense(self,rx,parts=None,actor=None):
        return self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=actor or self.staff,json={} if parts is None else {'allocations':parts})

    def part(self,receipt=None,quantity=2,medicine='demo-a'):
        return dict(medicine_id=medicine,receipt_id=receipt,quantity=quantity)

    def test_split_sources_saved_snapshot_retry_reopen_and_no_patient_leak(self):
        receipt=self.receive();rx=self.prescription();store=Store(self.path)
        parts=[self.part(receipt['id'],1),self.part(None,1)]
        response=self.dispense(rx,parts);self.assertEqual(response.status_code,200)
        self.assertEqual(self.dispense(rx,list(reversed(parts))).json(),response.json())
        self.assertEqual(self.dispense(rx,[self.part(None,2)]).status_code,409)
        self.assertEqual(store.catalog()[0]['stock'],23)
        state=store.dispensing_stock(rx['id']);self.assertEqual(state['items'][0]['untracked_units'],19)
        self.assertEqual(state['items'][0]['batches'][0]['remaining_units'],4)
        self.assertEqual(sum(row['quantity'] for row in state['allocations']),2)
        tagged=next(row for row in state['allocations'] if row['receipt_id']);self.assertEqual(tagged['batch_number'],'LOT-FICTIONAL')
        self.assertEqual(tagged['actor_id'],'staff-demo')
        self.assertEqual(TestClient(create_app(self.path)).get(f"/prescriptions/{rx['id']}/stock-sources",headers=self.staff).json(),state)
        self.assertNotIn('receipt_id',self.client.get('/care',headers=self.patient).text)

    def test_roles_validation_exact_sums_and_cross_medicine_receipts_rollback(self):
        receipt=self.receive();other=self.receive(medicine='demo-b',key='other-dispensing-batch');rx=self.prescription()
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.dispense(rx,[self.part(receipt['id'])],{'X-Demo-Actor':actor}).status_code,403)
            self.assertEqual(self.client.get(f"/prescriptions/{rx['id']}/stock-sources",headers={'X-Demo-Actor':actor}).status_code,403)
        for parts in ([],[self.part(quantity=True)],[self.part(quantity=1)],[self.part(quantity=3)],[self.part(quantity=1),self.part(quantity=1)],[self.part(medicine='missing')]):
            self.assertEqual(self.dispense(rx,parts).status_code,422,parts)
        for source in ('missing',other['id']):self.assertEqual(self.dispense(rx,[self.part(source)]).status_code,409)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_expired_cannot_be_disguised_as_untracked_and_today_allowed(self):
        expired=self.receive(quantity=22,days=-1)
        store=Store(self.path);rx=self.prescription([dict(medicine_id='demo-a',quantity=20,directions='Fixture')])
        # Consume the genuine20 untracked units first.
        self.assertEqual(self.dispense(rx).status_code,200)
        second=store.book('patient-noah',self.slot['id'],'expired-second-visit')
        store.call_next(self.slot['doctor_id'],self.slot['clinic_date'],'staff-demo');store.complete(second['id'],'staff-demo')
        rx2=store.issue_prescription(second['id'],self.slot['doctor_id'],[dict(medicine_id='demo-a',quantity=2,directions='Fixture')])
        self.assertEqual(self.dispense(rx2,[self.part(expired['id'])]).status_code,409)
        self.assertEqual(self.dispense(rx2).status_code,409) # cannot use expired22 as untracked
        today=self.receive(quantity=2,days=0,key='today-dispensing-batch')
        self.assertEqual(self.dispense(rx2,[self.part(today['id'])]).status_code,200)
        self.assertEqual(next(b for b in store.dispensing_stock(rx2['id'])['items'][0]['batches'] if b['receipt_id']==today['id'])['remaining_units'],0)

    def test_loss_dispensing_concurrency_and_zero_batch_expiry_suppression(self):
        receipt=self.receive(quantity=3,days=0);rx=self.prescription();store=Store(self.path)
        def operate(index):
            try:
                if index==0:return store.dispense(rx['id'],'staff-demo',[self.part(receipt['id'],2)])
                return store.record_stock_loss('demo-a',2,'damaged','Fixture','race-dispensing-loss','staff-demo',receipt['id'])
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(operate,range(2)))
        self.assertEqual(results.count(409),1)
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],1)
        store.record_stock_loss('demo-a',1,'lost','Fixture','deplete-dispensing-batch','staff-demo',receipt['id'])
        self.assertEqual(store.stock_expiry()['items'],[])
        self.assertEqual(store.catalog()[0]['stock'],20)

    def test_multi_item_failure_and_allocation_audit_rollback_preserves_invoice(self):
        receipt=self.receive();expired=self.receive(days=-1,medicine='demo-b',key='multi-expired-batch')
        rx=self.prescription([dict(medicine_id='demo-a',quantity=2,directions='Fixture'),dict(medicine_id='demo-b',quantity=2,directions='Fixture')])
        store=Store(self.path);bill=store.generate_invoice(rx['booking_id'],'staff-demo')
        parts=[self.part(receipt['id']),self.part(expired['id'],medicine='demo-b')]
        self.assertEqual(self.dispense(rx,parts).status_code,409)
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],5)
        self.assertEqual(store.dispensing_stock(rx['id'])['allocations'],[])
        with store.connect() as db:db.execute("CREATE TRIGGER fail_allocation BEFORE INSERT ON dispensing_allocations BEGIN SELECT RAISE(ABORT,'test allocation failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.dispense(rx['id'],'staff-demo',[self.part(receipt['id']),self.part(None,medicine='demo-b')])
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],5)
        self.assertEqual(store.catalog()[0]['stock'],25)
        with store.connect() as db:self.assertEqual(store.invoice(db,rx['booking_id']),bill)

    def test_unassigned_loss_respects_tracked_reserve_and_historical_receipts_stay_untracked(self):
        receipt=self.receive();store=Store(self.path)
        store.record_stock_loss('demo-a',20,'lost','Fixture','consume-untracked-stock','staff-demo')
        with self.assertRaises(RuleError):store.record_stock_loss('demo-a',1,'lost','Fixture','unassigned-cannot-use-tracked','staff-demo')
        self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],5)
        # Simulate a pre-feature receipt: no reliable remaining batch quantity can be inferred.
        with store.connect() as db:db.execute('DELETE FROM receipt_balances WHERE receipt_id=?',(receipt['id'],))
        reopened=Store(self.path);self.assertIsNone(reopened.stock_batches('demo-a')[0]['remaining_units'])
        rx=self.prescription();self.assertEqual(reopened.dispensing_stock(rx['id'])['items'][0]['untracked_units'],5)
        self.assertEqual(self.dispense(rx).status_code,200)
        self.assertIsNone(reopened.stock_batches('demo-a')[0]['remaining_units'])

    def test_identical_concurrent_dispensing_deducts_once_and_missing_prescription(self):
        receipt=self.receive();rx=self.prescription();store=Store(self.path)
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:store.dispense(rx['id'],'staff-demo',[self.part(receipt['id'])]),range(3)))
        self.assertTrue(all(row==results[0] for row in results));self.assertEqual(store.stock_batches('demo-a')[0]['remaining_units'],3)
        self.assertEqual(len(store.dispensing_stock(rx['id'])['allocations']),1)
        self.assertEqual(self.client.get('/prescriptions/missing/stock-sources',headers=self.staff).status_code,404)
