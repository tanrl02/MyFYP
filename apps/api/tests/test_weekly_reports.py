from datetime import date,datetime,timedelta,timezone
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow


class WeeklyReportTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def report(self,day,actor=None):
        return self.client.get('/reports/weekly',headers=actor or self.staff,params={'week_of':day})

    def add(self,store,day,hour,key):
        slot=store.add_slot('doctor-lim',day,f'{hour:02d}:00',2,'weekly-slot-'+key)
        return store.book('patient-ava',slot['id'],'weekly-book-'+key)

    def test_week_totals_match_each_daily_report_and_preserve_data(self):
        store=Store(self.path)
        today=datetime.now(timezone(timedelta(hours=8))).date()
        monday=today-timedelta(days=today.weekday())+timedelta(days=14)
        sunday=monday+timedelta(days=6)
        records=[self.add(store,monday.isoformat(),10+i,str(i)) for i in range(6)]
        states=['waiting','waiting','called','completed','cancelled','missed']
        with store.connect() as db:
            for record,status in zip(records,states):db.execute('UPDATE bookings SET status=? WHERE id=?',(status,record['id']))
        self.add(store,sunday.isoformat(),9,'sunday')
        target=store.add_slot('doctor-lim',sunday.isoformat(),'16:00',2,'weekly-target')
        store.reschedule(records[0]['id'],'patient-ava',target['id'],'weekly-reschedule')
        self.add(store,(monday-timedelta(days=1)).isoformat(),9,'outside-before')
        self.add(store,(sunday+timedelta(days=1)).isoformat(),9,'outside-after')
        with store.connect() as db:before=list(db.iterdump())
        response=self.report((monday+timedelta(days=3)).isoformat())
        self.assertEqual(response.status_code,200)
        report=response.json()
        self.assertEqual((report['week_start'],report['week_end']),(monday.isoformat(),sunday.isoformat()))
        self.assertEqual(report['timezone'],'Asia/Kuala_Lumpur')
        self.assertEqual(report['visits'],dict(waiting=3,called=1,completed=1,cancelled=1,missed=1,rescheduled=1,total=8))
        self.assertEqual(len(report['days']),7)
        for index,row in enumerate(report['days']):
            self.assertEqual(row['clinic_date'],(monday+timedelta(days=index)).isoformat())
            self.assertEqual(row['visits'],store.daily_report(row['clinic_date'])['visits'])
            self.assertEqual(sum(v for k,v in row['visits'].items() if k!='total'),row['visits']['total'])
        for key,value in report['visits'].items():self.assertEqual(sum(row['visits'][key] for row in report['days']),value)
        self.assertEqual(set(report),{'week_start','week_end','timezone','generated_at','visits','days'})
        self.assertTrue(all(set(row)=={'clinic_date','visits'} for row in report['days']))
        self.assertNotIn('patient',response.text)
        reopened=TestClient(create_app(self.path)).get('/reports/weekly',headers=self.staff,params={'week_of':sunday.isoformat()}).json()
        self.assertEqual(reopened['days'],report['days'])
        self.assertEqual(reopened['visits'],report['visits'])
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_staff_only_and_invalid_inputs(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.report('2026-10-22',actor).status_code,403)
        for value in ('bad','2026-02-30','0000-01-01','9999-12-31'):
            self.assertEqual(self.report(value).status_code,422)
        self.assertEqual(self.client.get('/reports/weekly',headers=self.staff).status_code,422)

    def test_empty_week_includes_all_zero_days_and_cross_year_bounds(self):
        for chosen,start,end in [('2000-01-01','1999-12-27','2000-01-02'),('2024-02-29','2024-02-26','2024-03-03')]:
            report=self.report(chosen).json()
            self.assertEqual((report['week_start'],report['week_end']),(start,end))
            self.assertEqual(len(report['days']),7)
            self.assertTrue(all(value==0 for value in report['visits'].values()))
            self.assertTrue(all(row['visits']==report['visits'] for row in report['days']))
            self.assertEqual(self.report(start).json()['days'],report['days'])
            self.assertEqual(self.report(end).json()['days'],report['days'])
