import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_catalogue as catalogue


class MedicineEditingTests(unittest.TestCase):
    setUp=catalogue.CatalogueTests.setUp
    book=catalogue.CatalogueTests.book
    prepare=catalogue.CatalogueTests.prepare
    issue=catalogue.CatalogueTests.issue
    add=catalogue.CatalogueTests.add

    def edit(self,item,**changes):
        return self.client.post('/medicines/'+item['id']+'/edit',headers=self.staff,json=dict(name='Updated fictional cream',price_cents=1500,version=item['version'],request_id='medicine-edit-request')|changes)

    def test_staff_only_validation_scope_duplicate_and_immutable_identity(self):
        item=self.add().json();body=dict(name='New name',price_cents=200,version=0,request_id='denied-edit-request')
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.client.post('/medicines/'+item['id']+'/edit',headers=actor,json=body).status_code,403)
        self.assertEqual(self.edit(item|{'id':'missing'}).status_code,404)
        for changes in ({'name':' '},{'name':'x'*101},{'price_cents':True},{'price_cents':1.5},{'price_cents':-1},{'price_cents':1000001},{'version':True},{'version':-1},{'stock':99},{'strength':'Other'},{'form':'Other'},{'request_id':'x'}):
            self.assertEqual(self.edit(item,**changes).status_code,422,changes)
        self.assertEqual(self.edit(item,name=item['name'],price_cents=item['price_cents']).status_code,422)
        other=self.add(name='Other cream',request_id='other-cream-request').json()
        self.assertEqual(self.edit(item,name=other['name'].upper()).status_code,409)
        saved=self.edit(item,price_cents=0).json()
        self.assertEqual((saved['strength'],saved['form'],saved['stock'],saved['version']),('1% demo','Cream',0,1))
        self.assertNotIn('creation_json',self.client.get('/stock',headers=self.staff).text)
        self.assertNotIn('creation_json',self.client.get('/medicines',headers={'X-Demo-Actor':'doctor-lim'}).text)

    def test_retry_stale_conflict_creation_retry_and_persistence_never_restore_old_details(self):
        item=self.add().json();saved=self.edit(item).json()
        self.assertEqual(self.edit(item).json(),saved)
        self.assertEqual(self.edit(item,name='Different',request_id='stale-new-request').status_code,409)
        self.assertEqual(self.edit(item,price_cents=1).status_code,409)
        second=self.edit(saved,name='Latest fictional cream',price_cents=2000,request_id='second-edit-request').json()
        self.assertEqual(second['version'],2)
        self.assertEqual(self.edit(item).json(),saved)
        self.assertEqual(self.add().json(),second)
        self.assertEqual(self.add(price_cents=2000).status_code,409)
        reopened=TestClient(create_app(self.path))
        self.assertIn(second,reopened.get('/medicines',headers=self.staff).json())
        with Store(self.path).connect() as db:
            audit=db.execute('SELECT * FROM medicine_edits ORDER BY from_version').fetchall()
            self.assertEqual(len(audit),2)
            self.assertEqual((audit[0]['old_name'],audit[0]['old_price_cents'],audit[0]['actor_id']),(item['name'],1250,'staff-demo'))

    def test_issued_prescription_delayed_bill_and_paid_bill_keep_original_snapshot(self):
        item=self.add().json();visit=self.prepare()
        rx=self.issue(visit,items=[dict(medicine_id=item['id'],quantity=2,directions='Fictional directions')]).json()
        saved=self.edit(item).json()
        bill=self.client.post('/visits/'+visit+'/invoice',headers=self.staff).json()
        self.assertEqual((bill['total_cents'],bill['lines'][1]['description'],bill['lines'][1]['unit_price_cents']),(5500,'Fictional cream · 1% demo · Cream',1250))
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],rx)
        store=Store(self.path)
        store.receive_stock(item['id'],10,'Demo receipt','edit-dispense-stock','staff-demo')
        store.dispense(rx['id'],'staff-demo')
        paid=store.pay_simulated(bill['id'],'patient-ava')
        self.edit(saved,name='Another name',price_cents=3000,request_id='after-paid-edit')
        with store.connect() as db:self.assertEqual(store.invoice(db,visit),paid)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        # A prescription issued later uses the newly saved catalogue snapshot.
        next_visit=store.book('patient-noah',self.slot['id'],'later-prescription')
        store.call_next(self.slot['doctor_id'],self.slot['clinic_date'],'staff-demo')
        new_rx=store.issue_prescription(next_visit['id'],self.slot['doctor_id'],[dict(medicine_id=item['id'],quantity=1,directions='Fictional new directions')])
        self.assertEqual((new_rx['items'][0]['name'],new_rx['items'][0]['price_cents']),('Another name',3000))
        self.assertEqual(next(m for m in store.catalog() if m['id']==item['id'])['stock'],8)

    def test_concurrent_same_request_and_different_stale_edits(self):
        item=self.add().json();store=Store(self.path)
        def same(_):return store.edit_medicine(item['id'],'Concurrent name',500,0,'same-edit-concurrent','staff-demo')
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(same,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        def different(index):
            try:return store.edit_medicine(item['id'],'Next name '+str(index),600,1,'competing-edit-'+str(index),'staff-demo')['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(different,range(2)))
        self.assertEqual(sorted(results),[2,409])
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM medicine_edits').fetchone()[0],2)

    def test_receiving_during_edit_preserves_stock_and_duplicate_renames_serialize(self):
        item=self.add().json();store=Store(self.path)
        def operation(index):
            if index==0:return store.edit_medicine(item['id'],'Renamed cream',900,0,'stock-edit-concurrent','staff-demo')
            return store.receive_stock(item['id'],7,'Demo delivery','stock-receive-concurrent','staff-demo')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(operation,range(2)))
        current=next(m for m in store.catalog() if m['id']==item['id']);self.assertEqual((current['stock'],current['version']),(7,1))
        store.edit_medicine(item['id'],'Renamed cream',900,0,'stock-edit-concurrent','staff-demo')
        self.assertEqual(next(m for m in store.catalog() if m['id']==item['id'])['stock'],7)
        other=self.add(name='Second cream',request_id='rename-other-item').json()
        def rename(value):
            try:return store.edit_medicine(value['id'],'Same target name',999,value['version'],'rename-'+value['id'],'staff-demo')['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(rename,[current,other]))
        self.assertEqual(len([value for value in results if value==409]),1)

    def test_audit_failure_rolls_back_name_price_version_and_stock(self):
        item=self.add().json();store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_catalogue_audit BEFORE INSERT ON medicine_edits BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.edit_medicine(item['id'],'Failed change',2,0,'failed-audit-request','staff-demo')
        self.assertEqual(next(m for m in store.catalog() if m['id']==item['id']),item)

    def test_legacy_medicine_migration_preserves_values_creation_retry_and_snapshots(self):
        item=self.add().json();visit=self.prepare();rx=self.issue(visit).json()
        bill=self.client.post('/visits/'+visit+'/invoice',headers=self.staff).json();store=Store(self.path)
        before=store.catalog()
        with store.connect() as db:
            db.execute('DROP TABLE medicine_edits')
            for column in ('version','updated_at','creation_json'):db.execute('ALTER TABLE medicines DROP COLUMN '+column)
        restored=Store(self.path)
        self.assertEqual(restored.catalog(),before)
        with restored.connect() as db:
            self.assertEqual(restored.prescription(db,visit),rx);self.assertEqual(restored.invoice(db,visit),bill)
        saved=restored.edit_medicine(item['id'],'Migrated edited cream',500,0,'legacy-medicine-edit','staff-demo')
        self.assertEqual(restored.add_medicine('Fictional cream','1% demo','Cream',1250,'catalogue-request-one'),saved)
        self.assertEqual(next(m for m in Store(self.path).catalog() if m['id']==item['id']),saved)
