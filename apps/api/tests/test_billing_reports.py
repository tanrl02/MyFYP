import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow
import test_reports as reports


class BillingReportTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    completed=reports.ReportTests.completed

    def report(self,**filters):
        return self.client.get('/reports/billing',headers=self.staff,
            params=filters or {'period':'month','year':2032,'month':2})

    def fixtures(self,rows):
        store=Store(self.path)
        template=store.book('patient-ava',self.slot['id'],'billing-template')
        with store.connect() as db:
            for i,(when,cents,status) in enumerate(rows):
                key='billing-report-'+str(i)
                db.execute('''INSERT INTO bookings(id,patient_id,slot_id,queue_number,status,created_at,request_id)
                    SELECT ?,patient_id,slot_id,?,'completed',created_at,? FROM bookings WHERE id=?''',
                    (key,i+10,key,template['id']))
                db.execute('INSERT INTO invoices VALUES(?,?,?,?,?,?,?)',
                    (key,key,cents,status,when,'2035-01-01T00:00:00+00:00' if status=='paid' else None,'simulation' if status=='paid' else None))
                for line in range(2):
                    db.execute('INSERT INTO invoice_lines VALUES(?,?,?,?,?)',(key+str(line),key,'Private fictional item',1,0))
        return store

    def test_roles_filters_and_empty_leap_month(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.client.get('/reports/billing',headers={'X-Demo-Actor':actor},params={'period':'year','year':2032}).status_code,403)
        for params in ({'period':'week','year':2032},{'period':'month','year':2032},
                       {'period':'quarter','year':2032,'quarter':0},{'period':'year','year':2032,'month':1},
                       {'period':'month','year':2032,'month':2,'quarter':1},{'period':'year','year':1}):
            self.assertEqual(self.report(**params).status_code,422)
        data=self.report().json();self.assertEqual(data['end_date'],'2032-02-29')
        self.assertEqual(len(data['buckets']),29);self.assertTrue(all(v==0 for v in data['billing'].values()))
        self.assertTrue(all(all(v==0 for v in b['billing'].values()) for b in data['buckets']))
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_issue_cohort_boundaries_cents_reconciliation_privacy_and_persistence(self):
        store=self.fixtures([('2032-01-31T15:59:59+00:00',900,'paid'),
            ('2032-01-31T16:00:00+00:00',1001,'unpaid'),('2032-02-29T15:59:59+00:00',2002,'paid'),
            ('2032-02-29T16:00:00+00:00',700,'unpaid'),('2032-02-01T00:00:00+08:00',0,'paid')])
        with store.connect() as db:before=list(db.iterdump())
        data=self.report().json()
        self.assertEqual(data['billing'],{'invoice_count':3,'paid_invoice_count':2,'unpaid_invoice_count':1,
            'billed_cents':3003,'paid_cents':2002,'unpaid_cents':1001})
        self.assertEqual(data['buckets'][0]['billing']['invoice_count'],2)
        self.assertEqual(data['buckets'][-1]['billing']['paid_cents'],2002)
        for key,total in data['billing'].items():self.assertEqual(sum(b['billing'][key] for b in data['buckets']),total)
        for private in ('patient','booking_id','Private fictional item','billing-report-','payment_mode','paid_at'):
            self.assertNotIn(private,str(data))
        reopened=TestClient(create_app(self.path)).get('/reports/billing',headers=self.staff,params={'period':'month','year':2032,'month':2}).json()
        data.pop('generated_at');reopened.pop('generated_at');self.assertEqual(data,reopened)
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_quarter_year_buckets_and_boundaries(self):
        self.fixtures([('2031-12-31T15:59:59+00:00',11,'paid'),('2031-12-31T16:00:00+00:00',101,'unpaid'),
            ('2032-03-31T15:59:59+00:00',202,'paid'),('2032-03-31T16:00:00+00:00',303,'unpaid'),
            ('2032-12-31T15:59:59+00:00',404,'paid'),('2032-12-31T16:00:00+00:00',505,'paid')])
        quarter=self.report(period='quarter',year=2032,quarter=1).json()
        self.assertEqual(len(quarter['buckets']),3);self.assertEqual(quarter['billing']['billed_cents'],303)
        self.assertEqual(quarter['buckets'][1]['billing']['invoice_count'],0)
        year=self.report(period='year',year=2032).json()
        self.assertEqual(len(year['buckets']),12);self.assertEqual(year['billing']['billed_cents'],1010)
        self.assertEqual(year['billing']['paid_cents'],606);self.assertEqual(year['billing']['unpaid_cents'],404)
        for b in year['buckets']:
            t=b['billing'];self.assertEqual(t['billed_cents'],t['paid_cents']+t['unpaid_cents'])
            self.assertEqual(t['invoice_count'],t['paid_invoice_count']+t['unpaid_invoice_count'])

    def test_later_simulated_payment_updates_original_issue_period_once(self):
        store=Store(self.path)
        _,_,invoice=self.completed(store,'patient-ava',self.slot,'billing-payment')
        with store.connect() as db:db.execute("UPDATE invoices SET created_at='2032-02-01T00:00:00+08:00'")
        before=self.report().json()['billing'];self.assertEqual(before['unpaid_invoice_count'],1)
        store.pay_simulated(invoice['id'],'patient-ava');store.pay_simulated(invoice['id'],'patient-ava')
        after=self.report().json()['billing']
        self.assertEqual(after['invoice_count'],1);self.assertEqual(after['billed_cents'],before['billed_cents'])
        self.assertEqual(after['paid_cents'],before['billed_cents']);self.assertEqual(after['unpaid_cents'],0)
        self.assertEqual(self.report(period='year',year=2033).json()['billing']['invoice_count'],0)
