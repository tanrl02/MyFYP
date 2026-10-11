from datetime import datetime,timedelta,timezone
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow

class ReportTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    def report(self,date=None,actor=None):
        return self.client.get('/reports/daily',headers=actor or self.staff,params={'clinic_date':date or self.slot['clinic_date']})
    def completed(self,store,patient,slot,key,paid=False):
        visit=store.book(patient,slot['id'],key)
        store.call_next(slot['doctor_id'],slot['clinic_date'],'staff-demo')
        rx=store.issue_prescription(visit['id'],slot['doctor_id'],[{'medicine_id':'demo-a','quantity':2,'directions':'Fictional directions'}]) if paid else None
        store.complete(visit['id'],'staff-demo');invoice=store.generate_invoice(visit['id'],'staff-demo')
        if rx:
            store.dispense(rx['id'],'staff-demo');store.pay_simulated(invoice['id'],patient)
        return visit,rx,invoice
    def test_totals_reschedule_without_double_count_and_no_clinical_data(self):
        store=Store(self.path);first,rx,invoice=self.completed(store,'patient-ava',self.slot,'completed-request',True)
        other=next(s for s in store.slots() if s['clinic_date']==self.slot['clinic_date'] and s['doctor_id']!=self.slot['doctor_id'])
        second,_,_=self.completed(store,'patient-noah',other,'other-completed')
        cancelled=store.book('patient-noah',self.slot['id'],'cancelled-request');store.cancel(cancelled['id'],'patient-noah')
        times=[s for s in store.slots() if s['clinic_date']==self.slot['clinic_date'] and s['doctor_id']==self.slot['doctor_id'] and s['id']!=self.slot['id']]
        old=store.book('patient-ava',times[0]['id'],'move-old-request');store.reschedule(old['id'],'patient-ava',times[1]['id'],'move-report-request')
        store.receive_stock('demo-a',3,'Fictional receipt','report-receipt-key','staff-demo')
        store.submit_feedback(first['id'],'patient-ava',4,'Private fictional comment')
        store.submit_feedback(second['id'],'patient-noah',2,'Another fictional comment')
        start=datetime.fromisoformat(self.slot['clinic_date']).replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
        with store.connect() as db:
            db.execute('UPDATE stock_receipts SET created_at=?',(start.isoformat(),))
            db.execute('UPDATE prescriptions SET dispensed_at=?',(start.isoformat(),))
            db.execute('UPDATE visit_feedback SET created_at=?',(start.isoformat(),))
            # Current paid invoice balance belongs to appointment date even when payment occurred elsewhere.
            db.execute('UPDATE invoices SET paid_at=? WHERE id=?',((start-timedelta(days=2)).isoformat(),invoice['id']))
        response=self.report();self.assertEqual(response.status_code,200);report=response.json()
        self.assertEqual(report['visits'],{'waiting':1,'called':0,'completed':2,'cancelled':1,'rescheduled':1,'total':5})
        self.assertEqual(report['billing'],{'invoice_count':2,'billed_cents':7000,'paid_cents':4000,'unpaid_cents':3000})
        self.assertEqual((report['stock']['received_units'],report['stock']['dispensed_units']),(3,2))
        self.assertEqual(report['feedback'],{'count':2,'average_rating':3.0})
        for secret in ('patient-ava','patient-noah','Private fictional comment','directions','photo','findings'):
            self.assertNotIn(secret,str(report))
        reopened=TestClient(create_app(self.path)).get('/reports/daily',headers=self.staff,params={'clinic_date':self.slot['clinic_date']}).json()
        report.pop('generated_at');reopened.pop('generated_at');self.assertEqual(report,reopened)
    def test_malaysia_midnight_boundaries_and_activity_date(self):
        store=Store(self.path);visit,rx,_=self.completed(store,'patient-ava',self.slot,'boundary-visit',True)
        store.submit_feedback(visit['id'],'patient-ava',5,'Fictional boundary comment')
        start=datetime.fromisoformat(self.slot['clinic_date']).replace(tzinfo=timezone(timedelta(hours=8))).astimezone(timezone.utc)
        receipts=[(start-timedelta(seconds=1),1),(start,2),(start+timedelta(days=1)-timedelta(seconds=1),3),(start+timedelta(days=1),4)]
        for index,(when,quantity) in enumerate(receipts):
            saved=store.receive_stock('demo-a',quantity,'Boundary fixture',f'boundary-key-{index}','staff-demo')
            with store.connect() as db:db.execute('UPDATE stock_receipts SET created_at=? WHERE id=?',(when.isoformat(),saved['id']))
        with store.connect() as db:
            db.execute('UPDATE prescriptions SET dispensed_at=?',((start+timedelta(days=1)).isoformat(),))
            db.execute('UPDATE visit_feedback SET created_at=?',((start-timedelta(seconds=1)).isoformat(),))
        current=self.report().json();self.assertEqual(current['stock']['received_units'],5)
        self.assertEqual(current['stock']['dispensed_units'],0);self.assertEqual(current['feedback'],{'count':0,'average_rating':None})
        next_day=self.report((start.astimezone(timezone(timedelta(hours=8)))+timedelta(days=1)).date().isoformat()).json()
        self.assertEqual(next_day['stock']['received_units'],4);self.assertEqual(next_day['stock']['dispensed_units'],2)
        self.assertEqual(next_day['visits']['total'],0);self.assertEqual(next_day['billing']['invoice_count'],0)
    def test_staff_only_validation_and_empty_date(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'}):self.assertEqual(self.report(actor=actor).status_code,403)
        self.assertEqual(self.report('2026-02-30').status_code,422)
        self.assertEqual(self.report('not-a-date').status_code,422)
        empty=self.report('2000-01-01').json()
        self.assertEqual(empty['visits']['total'],0);self.assertEqual(empty['billing']['billed_cents'],0)
        self.assertEqual(empty['stock']['received_units'],0);self.assertIsNone(empty['feedback']['average_rating'])
