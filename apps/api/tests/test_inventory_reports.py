import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow


class InventoryReportTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def report(self,actor=None,**filters):
        return self.client.get('/reports/inventory',headers=actor or self.staff,params=filters or {'period':'month','year':2032,'month':2})

    def prepare_visit(self,store,patient='patient-ava',key='inventory-report-visit'):
        visit=store.book(patient,self.slot['id'],key)
        store.call_next(self.slot['doctor_id'],self.slot['clinic_date'],'staff-demo')
        store.complete(visit['id'],'staff-demo')
        return visit

    def test_activity_boundaries_dispensing_losses_read_only_and_reopen(self):
        store=Store(self.path)
        receipts=[]
        for key,quantity in [('before',7),('start',10),('after',5)]:
            receipts.append(store.receive_stock('demo-a',quantity,'Fictional receipt','inventory-report-'+key,'staff-demo'))
        visit=self.prepare_visit(store)
        rx=store.issue_prescription(visit['id'],visit['doctor_id'],[{'medicine_id':'demo-a','quantity':4,'directions':'Private fictional directions'}])
        store.dispense(rx['id'],'staff-demo')
        second=self.prepare_visit(store,'patient-noah','inventory-report-undispensed')
        store.issue_prescription(second['id'],second['doctor_id'],[{'medicine_id':'demo-a','quantity':7,'directions':'Not dispensed'}])
        damaged=store.record_stock_loss('demo-a',2,'damaged','Private fictional reason','inventory-report-damaged','staff-demo')
        lost=store.record_stock_loss('demo-a',3,'lost','Private fictional reason','inventory-report-lost','staff-demo')
        with store.connect() as db:
            for receipt,when in zip(receipts,['2032-01-31T15:59:59Z','2032-01-31T16:00:00Z','2032-02-29T16:00:00Z']):
                db.execute('UPDATE stock_receipts SET created_at=? WHERE id=?',(when,receipt['id']))
            db.execute('UPDATE prescriptions SET dispensed_at=? WHERE id=?',('2032-02-15T04:00:00Z',rx['id']))
            db.execute('UPDATE stock_losses SET created_at=? WHERE id=?',('2032-02-29T15:59:59Z',damaged['id']))
            db.execute('UPDATE stock_losses SET created_at=? WHERE id=?',('2032-02-02T00:00:00+08:00',lost['id']))
            db.execute("UPDATE medicines SET name='Current fictional name',active=0 WHERE id='demo-a'")
            before=list(db.iterdump())
        response=self.report();self.assertEqual(response.status_code,200);report=response.json()
        self.assertEqual(report['units'],dict(received=10,dispensed=4,damaged=2,lost=3,net_change=1))
        self.assertEqual(len(report['buckets']),29)
        self.assertEqual(report['buckets'][0]['units']['received'],10)
        self.assertEqual(report['buckets'][-1]['units']['damaged'],2)
        for key,total in report['units'].items():self.assertEqual(sum(row['units'][key] for row in report['buckets']),total)
        self.assertEqual(report['top_dispensed'][0]['units'],4)
        self.assertEqual(report['top_dispensed'][0]['name'],'Current fictional name')
        self.assertFalse(report['top_dispensed'][0]['active'])
        self.assertFalse(any(row['medicine_id']=='demo-a' for row in report['current_stock']['alerts']))
        for row in report['buckets']:
            daily=store.daily_report(row['start_date'])['stock']
            self.assertEqual((daily['received_units'],daily['dispensed_units'],daily['lost_units']),
                (row['units']['received'],row['units']['dispensed'],row['units']['damaged']+row['units']['lost']))
        for private in ('patient','directions','reason','actor_id','booking_id'):self.assertNotIn(private,response.text)
        reopened=TestClient(create_app(self.path)).get('/reports/inventory',headers=self.staff,params={'period':'month','year':2032,'month':2}).json()
        for key in ('units','buckets','top_dispensed','current_stock'):self.assertEqual(reopened[key],report[key])
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_quarter_year_month_reconcile_and_boundary_exclusion(self):
        store=Store(self.path)
        for index,(day,quantity) in enumerate([('2032-01-31',2),('2032-02-01',3),('2032-03-31',4),('2032-04-01',5),('2032-12-31',6),('2033-01-01',7)]):
            receipt=store.receive_stock('demo-b',quantity,'Fixture',f'inventory-period-{index}','staff-demo')
            with store.connect() as db:db.execute('UPDATE stock_receipts SET created_at=? WHERE id=?',(day+'T00:00:00+08:00',receipt['id']))
        quarter=self.report(period='quarter',year=2032,quarter=1).json()
        self.assertEqual([row['units']['received'] for row in quarter['buckets']],[2,3,4])
        self.assertEqual(quarter['units']['received'],9)
        self.assertEqual((quarter['start_date'],quarter['end_date']),('2032-01-01','2032-03-31'))
        year=self.report(period='year',year=2032).json()
        self.assertEqual(year['units']['received'],20)
        self.assertEqual(len(year['buckets']),12)
        for row in year['buckets']:
            monthly=self.report(period='month',year=2032,month=int(row['start_date'][5:7])).json()
            self.assertEqual(monthly['units'],row['units'])
            self.assertEqual(monthly['current_stock'],year['current_stock'])
        self.assertEqual(self.report(period='month',year=2033,month=1).json()['units']['received'],7)

    def test_current_alerts_are_disjoint_active_only_and_independent_of_period(self):
        store=Store(self.path)
        item=store.add_medicine('Inactive synthetic item','','unit',100,'inventory-inactive-item')
        with store.connect() as db:
            db.execute("UPDATE medicines SET stock=5 WHERE id='demo-a'")
            db.execute("UPDATE medicines SET stock=0 WHERE id='demo-b'")
            db.execute('UPDATE medicines SET active=0 WHERE id=?',(item['id'],))
        empty=self.report(period='year',year=2000).json()
        current=empty['current_stock']
        self.assertEqual((current['active_items'],current['inactive_items'],current['active_units']),(2,1,5))
        self.assertEqual((current['low_stock_items'],current['out_of_stock_items']),(1,1))
        self.assertEqual([row['stock'] for row in current['alerts']],[0,5])
        self.assertEqual(current['low_stock_threshold'],store.stock()['low_stock_threshold'])
        self.assertTrue(all(value==0 for value in empty['units'].values()))
        self.assertTrue(all(row['units']==empty['units'] for row in empty['buckets']))
        self.assertEqual(empty['top_dispensed'],[])
        self.assertEqual(self.report().json()['current_stock'],current)

    def test_top_five_dispensed_items_and_ties_use_current_catalogue(self):
        store=Store(self.path)
        items=[]
        for index,(name,quantity) in enumerate([('Zed',5),('Beta',4),('Alpha',4),('Gamma',3),('Delta',2),('Epsilon',1)]):
            item=store.add_medicine(name,'','unit',100,f'inventory-rank-item-{index}')
            store.receive_stock(item['id'],10,'Fixture',f'inventory-rank-stock-{index}','staff-demo')
            items.append({'medicine_id':item['id'],'quantity':quantity,'directions':'Fictional'})
        visit=self.prepare_visit(store)
        rx=store.issue_prescription(visit['id'],visit['doctor_id'],items)
        store.dispense(rx['id'],'staff-demo')
        with store.connect() as db:db.execute('UPDATE prescriptions SET dispensed_at=? WHERE id=?',('2032-02-01T00:00:00+08:00',rx['id']))
        report=self.report().json()
        self.assertEqual([row['name'] for row in report['top_dispensed']],['Zed','Alpha','Beta','Gamma','Delta'])
        self.assertEqual([row['units'] for row in report['top_dispensed']],[5,4,4,3,2])
        self.assertEqual(report['units']['dispensed'],19)

    def test_roles_validation_and_empty_extreme_periods(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.report(actor).status_code,403)
        for filters in ({'period':'month','year':2032},{'period':'month','year':2032,'month':2,'quarter':1},{'period':'year','year':1},{'period':'year','year':9999},{'period':'quarter','year':2032,'quarter':0},{'period':'bad','year':2032}):
            self.assertEqual(self.report(**filters).status_code,422)
        self.assertEqual(self.client.get('/reports/inventory',headers=self.staff).status_code,422)
        for filters,length in [({'period':'month','year':1900,'month':2},28),({'period':'quarter','year':2,'quarter':1},3),({'period':'year','year':9998},12)]:
            response=self.report(**filters);self.assertEqual(response.status_code,200)
            self.assertEqual(len(response.json()['buckets']),length)
