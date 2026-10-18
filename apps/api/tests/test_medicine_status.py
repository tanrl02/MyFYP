import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_catalogue as catalogue


class MedicineStatusTests(unittest.TestCase):
    setUp=catalogue.CatalogueTests.setUp
    book=catalogue.CatalogueTests.book
    prepare=catalogue.CatalogueTests.prepare
    issue=catalogue.CatalogueTests.issue
    add=catalogue.CatalogueTests.add

    def status(self,item,active=False,key='medicine-status-one',**changes):
        return self.client.post('/medicines/'+item['id']+'/status',headers=self.staff,json=dict(active=active,version=item['version'],request_id=key)|changes)

    def test_staff_scope_strict_validation_and_catalogue_visibility(self):
        item=self.add().json();self.assertIs(item['active'],True)
        body=dict(active=False,version=0,request_id='status-denied-request')
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.client.post('/medicines/'+item['id']+'/status',headers=actor,json=body).status_code,403)
        for changes in ({'active':0},{'active':'false'},{'active':None},{'version':True},{'version':-1},{'stock':99},{'name':'Other'},{'request_id':'x'}):
            self.assertEqual(self.status(item,**changes).status_code,422,changes)
        self.assertEqual(self.status(item|{'id':'missing'}).status_code,404)
        self.assertEqual(self.status(item,active=True).status_code,422)
        inactive=self.status(item).json();self.assertIs(inactive['active'],False)
        self.assertEqual(inactive['version'],1)
        for actor in ('doctor-lim','doctor-anita'):
            self.assertNotIn(item['id'],{m['id'] for m in self.client.get('/medicines',headers={'X-Demo-Actor':actor}).json()})
        self.assertIn(inactive,self.client.get('/medicines',headers=self.staff).json())
        self.assertIn(inactive,self.client.get('/stock',headers=self.staff).json()['medicines'])
        self.assertIn(inactive,TestClient(create_app(self.path)).get('/medicines',headers=self.staff).json())
        # Inactive identity is retained rather than duplicated through Add.
        self.assertEqual(self.add(request_id='duplicate-inactive-item').status_code,409)

    def test_reactivation_historical_status_creation_and_edit_retries_never_revert(self):
        item=self.add().json();inactive=self.status(item).json()
        self.assertEqual(self.status(item).json(),inactive)
        self.assertEqual(self.status(item,active=True).status_code,409)
        self.assertEqual(self.status(item,key='stale-status-request',active=True).status_code,409)
        self.assertEqual(self.add().json(),inactive)
        active=self.status(inactive,active=True,key='reactivate-request').json()
        self.assertEqual(active['id'],item['id']);self.assertEqual(active['version'],2)
        self.assertEqual(self.status(item).json(),inactive)
        self.assertIn(active,Store(self.path).catalog(active_only=True))
        edited=self.client.post('/medicines/'+item['id']+'/edit',headers=self.staff,json=dict(name='Renamed after status',price_cents=500,version=2,request_id='edit-after-status')).json()
        again=self.status(edited,key='inactive-again').json()
        replay=self.client.post('/medicines/'+item['id']+'/edit',headers=self.staff,json=dict(name='Renamed after status',price_cents=500,version=2,request_id='edit-after-status')).json()
        self.assertIs(replay['active'],True)
        self.assertIn(again,Store(self.path).catalog())
        with Store(self.path).connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM medicine_status_changes').fetchone()[0],3)

    def test_inactive_new_prescription_rejected_atomically_but_issued_retry_dispense_and_bill_work(self):
        item=self.add().json();visit=self.prepare()
        body=[dict(medicine_id=item['id'],quantity=2,directions='Fictional instructions')]
        rx=self.issue(visit,items=body).json();inactive=self.status(item).json()
        self.assertEqual(self.issue(visit,items=body).json(),rx)
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],rx)
        store=Store(self.path)
        with self.assertRaises(RuleError):store.dispense(rx['id'],'staff-demo')
        store.receive_stock(item['id'],7,'Fictional delivery','inactive-receive-stock','staff-demo')
        dispensed=store.dispense(rx['id'],'staff-demo');self.assertEqual(dispensed['items'],rx['items'])
        bill=store.generate_invoice(visit,'staff-demo');self.assertEqual(bill['total_cents'],5500)
        paid=store.pay_simulated(bill['id'],'patient-ava')
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        next_visit=store.book('patient-noah',self.slot['id'],'new-inactive-rx')
        store.call_next(self.slot['doctor_id'],self.slot['clinic_date'],'staff-demo')
        response=self.issue(next_visit['id'],items=[dict(medicine_id='demo-a',quantity=1,directions='Demo'),*body])
        self.assertEqual(response.status_code,409)
        with store.connect() as db:
            self.assertIsNone(store.prescription(db,next_visit['id']))
            self.assertEqual(store.invoice(db,visit),paid)
        current=next(m for m in store.catalog() if m['id']==item['id']);self.assertEqual(current['stock'],5)
        restored=self.status(current,active=True,key='reactivate-for-prescribing').json()
        self.assertEqual(restored['stock'],5)
        self.assertEqual(self.issue(next_visit['id'],items=body).status_code,200)

    def test_concurrent_status_requests_and_edit_share_version_protection(self):
        item=self.add().json();store=Store(self.path)
        def same(_):return store.set_medicine_active(item['id'],False,0,'concurrent-inactive','staff-demo')
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(same,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        def change(index):
            try:
                if index==0:return store.set_medicine_active(item['id'],True,1,'competing-reactivation','staff-demo')['version']
                return store.edit_medicine(item['id'],'Competing edited name',600,1,'competing-name-edit','staff-demo')['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,range(2)))
        self.assertEqual(sorted(results),[2,409])

    def test_concurrent_issuance_and_deactivation_cannot_issue_after_status_commit(self):
        item=self.add().json();visit=self.prepare();store=Store(self.path)
        body=[dict(medicine_id=item['id'],quantity=1,directions='Fictional')]
        def operation(index):
            if index==0:return store.set_medicine_active(item['id'],False,0,'race-inactive','staff-demo')
            try:return store.issue_prescription(visit,self.slot['doctor_id'],body)
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(operation,range(2)))
        self.assertIs(results[0]['active'],False)
        with store.connect() as db:
            rx=store.prescription(db,visit)
            if results[1]==409:self.assertIsNone(rx)
            else:self.assertEqual(rx,results[1])
        self.assertNotIn(item['id'],{m['id'] for m in store.catalog(active_only=True)})

    def test_status_audit_failure_rolls_back_all_values(self):
        item=self.add().json();store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_status_audit BEFORE INSERT ON medicine_status_changes BEGIN SELECT RAISE(ABORT,'test status failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.set_medicine_active(item['id'],False,0,'status-audit-failure','staff-demo')
        self.assertIn(item,store.catalog())

    def test_migration_defaults_active_preserves_existing_history_and_old_edit_retry(self):
        item=self.add().json();visit=self.prepare();rx=self.issue(visit).json()
        store=Store(self.path);bill=store.generate_invoice(visit,'staff-demo')
        edited=store.edit_medicine(item['id'],'Before migration edit',500,0,'pre-status-edit','staff-demo')
        before=store.catalog()
        with store.connect() as db:
            row=db.execute('SELECT result_json FROM medicine_edits WHERE request_id=?',('pre-status-edit',)).fetchone()
            result=json.loads(row['result_json']);result.pop('active')
            db.execute('UPDATE medicine_edits SET result_json=? WHERE request_id=?',(json.dumps(result),'pre-status-edit'))
            db.execute('DROP TABLE medicine_status_changes')
            db.execute('ALTER TABLE medicines DROP COLUMN active')
        migrated=Store(self.path);self.assertEqual(migrated.catalog(),before)
        with migrated.connect() as db:
            self.assertEqual(migrated.prescription(db,visit),rx);self.assertEqual(migrated.invoice(db,visit),bill)
        migrated.set_medicine_active(item['id'],False,1,'post-migration-inactive','staff-demo')
        retry=migrated.edit_medicine(item['id'],'Before migration edit',500,0,'pre-status-edit','staff-demo')
        self.assertIs(retry['active'],True)
        self.assertFalse(next(m for m in Store(self.path).catalog() if m['id']==item['id'])['active'])
