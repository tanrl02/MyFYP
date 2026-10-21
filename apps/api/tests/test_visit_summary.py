from datetime import date,timedelta
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow


class VisitSummaryTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def report(self,actor=None,**filters):
        return self.client.get('/reports/summary',headers=actor or self.staff,params=filters)

    def add(self,store,day,hour,key,status='waiting'):
        slot=store.add_slot('doctor-lim',day,f'{hour:02d}:00',2,'summary-slot-'+key)
        visit=store.book('patient-ava',slot['id'],'summary-book-'+key)
        if status!='waiting':
            with store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(status,visit['id']))
        return visit

    def test_month_daily_totals_statuses_leap_day_previous_and_no_writes(self):
        store=Store(self.path)
        for index,status in enumerate(('waiting','called','completed','cancelled','missed')):
            self.add(store,'2032-02-01',10+index,str(index),status)
        old=self.add(store,'2032-02-02',10,'old')
        target=store.add_slot('doctor-lim','2032-02-29','15:00',2,'summary-reschedule-target')
        store.reschedule(old['id'],'patient-ava',target['id'],'summary-reschedule')
        self.add(store,'2032-01-31',10,'previous')
        self.add(store,'2032-03-01',10,'outside')
        with store.connect() as db:before=list(db.iterdump())
        report=self.report(period='month',year=2032,month=2).json()
        self.assertEqual((report['start_date'],report['end_date']),('2032-02-01','2032-02-29'))
        self.assertEqual((report['previous']['start_date'],report['previous']['end_date']),('2032-01-01','2032-01-31'))
        self.assertEqual(report['previous']['visits']['total'],1)
        self.assertEqual(report['visits'],dict(waiting=2,called=1,completed=1,cancelled=1,missed=1,rescheduled=1,total=7))
        self.assertEqual(len(report['buckets']),29)
        self.assertEqual(report['granularity'],'day')
        self.assertEqual(report['timezone'],'Asia/Kuala_Lumpur')
        for index,row in enumerate(report['buckets']):
            self.assertEqual(row['start_date'],(date(2032,2,1)+timedelta(days=index)).isoformat())
            self.assertEqual(row['start_date'],row['end_date'])
            self.assertEqual(row['visits'],store.daily_report(row['start_date'])['visits'])
        for key,total in report['visits'].items():self.assertEqual(sum(row['visits'][key] for row in report['buckets']),total)
        self.assertNotIn('patient',str(report))
        self.assertNotIn('doctor',str(report))
        reopened=TestClient(create_app(self.path)).get('/reports/summary',headers=self.staff,params={'period':'month','year':2032,'month':2}).json()
        for key in ('visits','previous','buckets'):self.assertEqual(reopened[key],report[key])
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_quarters_year_and_previous_calendar_boundaries(self):
        store=Store(self.path)
        for index,day in enumerate(('2031-10-01','2031-12-31','2032-01-01','2032-03-31','2032-04-01','2032-12-31','2033-01-01')):
            self.add(store,day,10,str(index))
        quarter=self.report(period='quarter',year=2032,quarter=1).json()
        self.assertEqual((quarter['start_date'],quarter['end_date']),('2032-01-01','2032-03-31'))
        self.assertEqual((quarter['previous']['start_date'],quarter['previous']['end_date']),('2031-10-01','2031-12-31'))
        self.assertEqual((quarter['visits']['total'],quarter['previous']['visits']['total']),(2,2))
        self.assertEqual([row['visits']['total'] for row in quarter['buckets']],[1,0,1])
        self.assertEqual([row['end_date'] for row in quarter['buckets']],['2032-01-31','2032-02-29','2032-03-31'])
        self.assertEqual(quarter['granularity'],'month')
        year=self.report(period='year',year=2032).json()
        self.assertEqual((year['start_date'],year['end_date']),('2032-01-01','2032-12-31'))
        self.assertEqual((year['previous']['start_date'],year['previous']['end_date']),('2031-01-01','2031-12-31'))
        self.assertEqual((year['visits']['total'],year['previous']['visits']['total']),(4,2))
        self.assertEqual(len(year['buckets']),12)
        for row in year['buckets']:
            month=store.visit_summary('month',2032,int(row['start_date'][5:7]))
            self.assertEqual(row['visits'],month['visits'])
        for q in range(1,5):
            result=self.report(period='quarter',year=2032,quarter=q).json()
            self.assertEqual(len(result['buckets']),3)
            for key,value in result['visits'].items():self.assertEqual(value,sum(row['visits'][key] for row in result['buckets']))
        december=self.report(period='month',year=2032,month=12).json()
        january=self.report(period='month',year=2033,month=1).json()
        self.assertEqual(january['previous']['visits'],december['visits'])

    def test_empty_periods_zero_previous_and_valid_year_extremes(self):
        for filters,length in [({'period':'month','year':2000,'month':2},29),({'period':'month','year':1900,'month':2},28),({'period':'quarter','year':2,'quarter':1},3),({'period':'year','year':9998},12)]:
            result=self.report(**filters)
            self.assertEqual(result.status_code,200)
            report=result.json()
            self.assertEqual(len(report['buckets']),length)
            self.assertTrue(all(value==0 for value in report['visits'].values()))
            self.assertTrue(all(value==0 for value in report['previous']['visits'].values()))
            self.assertTrue(all(row['visits']==report['visits'] for row in report['buckets']))

    def test_staff_only_and_filter_validation(self):
        valid={'period':'month','year':2032,'month':2}
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.report(actor,**valid).status_code,403)
        for filters in ({},{'period':'week','year':2032},{'period':'month','year':2032},valid|{'year':1},valid|{'year':9999},valid|{'year':'bad'},valid|{'month':0},valid|{'month':13},valid|{'quarter':1},{'period':'year','year':2032,'month':1},{'period':'quarter','year':2032,'quarter':5},{'period':'quarter','year':2032}):
            with self.subTest(filters=filters):self.assertEqual(self.report(**filters).status_code,422)
