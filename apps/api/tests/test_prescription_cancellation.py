from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_care as care


class PrescriptionCancellationTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def opened(self):
        visit=self.prepare(completed=False)
        self.rx=self.issue(visit).json()
        return visit

    def cancel(self,visit,body=None,actor=None):
        return self.client.post(f'/visits/{visit}/prescription/cancel',headers=actor or self.doctor,
            json=body if body is not None else {'version':1,'reason':'Fictional prescription no longer needed.'})

    def audit(self,visit,actor=None):
        return self.client.get(f'/visits/{visit}/prescription/cancellation',headers=actor or self.doctor)

    def test_cancellation_preserves_original_items_stock_and_private_audit_after_reopening(self):
        visit=self.opened();store=Store(self.path);stock=store.catalog()
        self.assertIsNone(self.audit(visit).json())
        saved=self.cancel(visit).json()
        self.assertEqual(saved['status'],'cancelled');self.assertTrue(saved['cancelled_at'])
        for key in self.rx:
            if key not in ('status','cancelled_at'):self.assertEqual(saved[key],self.rx[key])
        self.assertEqual(store.catalog(),stock)
        audit=self.audit(visit).json()
        self.assertEqual(audit['doctor_id'],self.slot['doctor_id']);self.assertEqual(audit['version'],1)
        self.assertEqual(audit['reason'],'Fictional prescription no longer needed.')
        for actor in (self.patient,self.staff):
            own=self.client.get('/care',headers=actor).json()[0]['prescription']
            self.assertEqual(own,saved);self.assertNotIn(audit['reason'],str(own));self.assertNotIn('reason',own)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/care',headers=self.patient).json()[0]['prescription'],saved)
        self.assertEqual(reopened.get(f'/visits/{visit}/prescription/cancellation',headers=self.doctor).json(),audit)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM prescriptions WHERE id=?',(saved['id'],)).fetchone()[0],'issued')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM dispensing_allocations').fetchone()[0],0)

    def test_roles_strict_input_and_missing_records(self):
        visit=self.opened();wrong={'X-Demo-Actor':'doctor-anita' if self.slot['doctor_id']=='doctor-lim' else 'doctor-lim'}
        for actor in (self.patient,self.other,self.staff,wrong):
            self.assertEqual(self.cancel(visit,actor=actor).status_code,403)
            self.assertEqual(self.audit(visit,actor).status_code,403)
        for body in ({},{'version':True,'reason':'x'},{'version':0,'reason':'x'},{'version':1,'reason':' '},
                     {'version':1,'reason':'x'*301},{'version':1,'reason':'x','quantity':2}):
            self.assertEqual(self.cancel(visit,body).status_code,422)
        self.assertEqual(self.cancel('missing').status_code,404)
        self.assertEqual(self.audit('missing').status_code,404)
        self.assertIsNone(self.audit(visit).json())

    def test_retry_is_idempotent_and_cancellation_cannot_be_replaced_or_reactivated(self):
        visit=self.opened();saved=self.cancel(visit).json()
        self.assertEqual(self.cancel(visit).json(),saved)
        self.assertEqual(self.cancel(visit,{'version':1,'reason':'Different'}).status_code,409)
        self.assertEqual(self.issue(visit).json(),saved)
        correction={'version':1,'reason':'Edit after cancellation','items':[{'medicine_id':'demo-a','directions':'New'}]}
        self.assertEqual(self.client.post(f'/visits/{visit}/prescription/directions',headers=self.doctor,json=correction).status_code,409)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM prescription_cancellations').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-cancelled'").fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='prescription_issued'").fetchone()[0],1)

    def test_handover_completion_dispensing_and_billing_lock_cancellation(self):
        for lock in ('handover','completed','dispensed','billed'):
            with self.subTest(lock=lock):
                self.setUp();visit=self.opened()
                if lock=='handover':
                    self.client.post(f'/visits/{visit}/consultation',headers=self.doctor,json={'findings':'Fictional','follow_up':'None'})
                    self.assertEqual(self.client.post(f'/visits/{visit}/consultation/finish',headers=self.doctor).status_code,200)
                elif lock=='dispensed':self.client.post(f'/prescriptions/{self.rx["id"]}/dispense',headers=self.staff)
                else:
                    self.client.post(f'/queue/{visit}/complete',headers=self.staff)
                    if lock=='billed':self.client.post(f'/visits/{visit}/invoice',headers=self.staff)
                self.assertEqual(self.cancel(visit).status_code,409);self.assertIsNone(self.audit(visit).json())

    def test_cancelled_prescription_cannot_dispense_and_bill_is_consultation_only(self):
        visit=self.opened();stock=Store(self.path).catalog();saved=self.cancel(visit).json()
        route=f'/prescriptions/{saved["id"]}/dispense'
        for body in ({},{'prescription_version':1}):self.assertEqual(self.client.post(route,headers=self.staff,json=body).status_code,409)
        sources=self.client.get(f'/prescriptions/{saved["id"]}/stock-sources',headers=self.staff).json()
        self.assertEqual(sources['status'],'cancelled');self.assertEqual(sources['allocations'],[])
        self.client.post(f'/visits/{visit}/consultation',headers=self.doctor,json={'findings':'Fictional','follow_up':'None'})
        self.client.post(f'/visits/{visit}/consultation/finish',headers=self.doctor)
        with Store(self.path).connect() as db:
            self.assertIsNone(db.execute('SELECT prescription_id FROM consultation_handoffs WHERE booking_id=?',(visit,)).fetchone()[0])
        self.client.post(f'/queue/{visit}/complete',headers=self.staff)
        self.assertEqual(self.cancel(visit).json(),saved)
        self.assertEqual(self.client.post(f'/visits/{visit}/invoice',headers=self.staff,json={'prescription_id':saved['id']}).status_code,409)
        invoice=self.client.post(f'/visits/{visit}/invoice',headers=self.staff,json={'prescription_id':None}).json()
        self.assertEqual(invoice['total_cents'],3000);self.assertEqual(len(invoice['lines']),1)
        self.assertEqual(self.client.post(f'/invoices/{invoice["id"]}/pay-simulated',headers=self.patient).status_code,200)
        self.assertEqual(Store(self.path).catalog(),stock)

    def test_correction_requires_reopening_cancellation_at_latest_revision(self):
        visit=self.opened()
        correction={'version':1,'reason':'Fictional correction','items':[{'medicine_id':'demo-a','directions':'New fictional directions'}]}
        self.client.post(f'/visits/{visit}/prescription/directions',headers=self.doctor,json=correction)
        self.assertEqual(self.cancel(visit).status_code,409)
        saved=self.cancel(visit,{'version':2,'reason':'No longer needed'}).json()
        self.assertEqual(saved['version'],2);self.assertEqual(saved['status'],'cancelled')
        self.assertEqual(self.audit(visit).json()['version'],2)
        history=self.client.get(f'/visits/{visit}/prescription/directions-history',headers=self.doctor).json()
        self.assertEqual(len(history['revisions']),1)

    def test_cancellation_rolls_back_if_audit_event_fails(self):
        visit=self.opened();store=Store(self.path)
        def fail(*args):raise RuntimeError('Injected failure')
        store.event=fail
        with self.assertRaises(RuntimeError):store.cancel_prescription(visit,self.slot['doctor_id'],1,'Fictional reason')
        self.assertIsNone(self.audit(visit).json())
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],self.rx)

    def attempt(self,fn):
        try:return fn()
        except RuleError as error:return error.status

    def test_concurrent_identical_retries_save_once(self):
        visit=self.opened();store=Store(self.path)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:store.cancel_prescription(visit,self.slot['doctor_id'],1,'Fictional reason'),range(2)))
        self.assertEqual(results[0],results[1])
        with store.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-cancelled'").fetchone()[0],1)

    def test_cancellation_and_dispensing_cannot_both_succeed(self):
        visit=self.opened();store=Store(self.path)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.attempt,lambda:store.cancel_prescription(visit,self.slot['doctor_id'],1,'Fictional reason'))
            b=pool.submit(self.attempt,lambda:store.dispense(self.rx['id'],'staff-demo',prescription_version=1))
            results=[a.result(),b.result()]
        self.assertEqual(sum(result==409 for result in results),1)
        current=self.client.get('/care',headers=self.patient).json()[0]['prescription']
        self.assertIn(current['status'],('cancelled','dispensed'))
        self.assertEqual(self.audit(visit).json() is not None,current['status']=='cancelled')

    def test_cancellation_and_handover_cannot_both_write_after_handover(self):
        visit=self.opened();store=Store(self.path)
        self.client.post(f'/visits/{visit}/consultation',headers=self.doctor,json={'findings':'Fictional','follow_up':'None'})
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(self.attempt,lambda:store.cancel_prescription(visit,self.slot['doctor_id'],1,'Fictional reason'))
            b=pool.submit(self.attempt,lambda:store.finish_consultation(visit,self.slot['doctor_id']))
            cancelled=a.result();self.assertIsInstance(b.result(),dict)
        with store.connect() as db:
            handoff=db.execute('SELECT prescription_id FROM consultation_handoffs WHERE booking_id=?',(visit,)).fetchone()[0]
        if cancelled==409:self.assertEqual(handoff,self.rx['id'])
        else:self.assertEqual(cancelled['status'],'cancelled');self.assertIsNone(handoff)
