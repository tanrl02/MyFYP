import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_care as care

class CatalogueTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def add(self,actor=None,**changes):
        payload={'name':' Fictional cream ','strength':'1% demo','form':'Cream','price_cents':1250,'request_id':'catalogue-request-one'}|changes
        return self.client.post('/medicines',headers=actor or self.staff,json=payload)

    def test_creation_retry_duplicates_roles_and_reopen(self):
        saved=self.add();self.assertEqual(saved.status_code,201);item=saved.json()
        self.assertEqual(item['stock'],0);self.assertEqual(item['name'],'Fictional cream')
        self.assertEqual(self.add().json(),item)
        self.assertEqual(self.add(price_cents=999).status_code,409)
        self.assertEqual(self.add(name='fictional CREAM',request_id='different-request').status_code,409)
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.add(actor).status_code,403)
        for changes in ({'name':' '},{'strength':''},{'form':'x'*61},{'price_cents':True},{'price_cents':1.5},{'price_cents':-1},{'price_cents':1000001}):
            self.assertEqual(self.add(**changes).status_code,422)
        reopened=TestClient(create_app(self.path))
        self.assertIn(item,reopened.get('/medicines',headers=self.staff).json())
        self.client.post('/stock/receive',headers=self.staff,json={'medicine_id':item['id'],'quantity':5,'reason':'Fictional delivery','request_id':'catalogue-stock-request'})
        self.assertEqual(self.add().json()['stock'],5)

    def test_prescription_snapshot_and_invoice_use_issued_price(self):
        item=self.add().json();visit=self.prepare()
        route=f"/visits/{visit}/prescription"
        body={'items':[{'medicine_id':item['id'],'quantity':2,'directions':'Fictional directions only.'}]}
        rx=self.client.post(route,headers=self.doctor,json=body).json()
        self.assertEqual(rx['items'][0]['strength'],'1% demo')
        self.assertEqual(self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff).status_code,409)
        self.client.post('/stock/receive',headers=self.staff,json={'medicine_id':item['id'],'quantity':5,'reason':'Demo','request_id':'catalogue-receipt-test'})
        self.assertEqual(self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff).status_code,200)
        store=Store(self.path)
        with store.connect() as db:
            db.execute("UPDATE medicines SET name='Changed name',strength='Changed strength',form='Changed form',price_cents=9999 WHERE id=?",(item['id'],))
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/care',headers=self.patient).json()[0]['prescription']['items'],rx['items'])
        self.client.post(f"/queue/{visit}/complete",headers=self.staff)
        bill=self.client.post(f"/visits/{visit}/invoice",headers=self.staff).json()
        self.assertEqual(bill['total_cents'],5500)
        self.assertEqual(bill['lines'][1]['description'],'Fictional cream · 1% demo · Cream')
        self.assertEqual(self.client.post(f"/visits/{visit}/invoice",headers=self.staff).json(),bill)
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])

    def test_concurrent_duplicate_and_retry_create_one_item(self):
        store=Store(self.path)
        def add(index):
            try:return store.add_medicine('Fictional tablet','5mg demo','Tablet',100,f'catalogue-{index}')['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=3) as pool:
            values=list(pool.map(add,[1,1,2]))
        ids=[v for v in values if isinstance(v,str)]
        self.assertEqual(len(set(ids)),1)
        self.assertEqual(len([m for m in store.catalog() if m['name']=='Fictional tablet']),1)

    def test_legacy_migration_preserves_prescription_and_bill(self):
        visit=self.prepare();rx=self.issue(visit).json()
        self.client.post(f"/queue/{visit}/complete",headers=self.staff)
        bill=self.client.post(f"/visits/{visit}/invoice",headers=self.staff).json()
        store=Store(self.path)
        with store.connect() as db:
            for column in ('name','price_cents','strength','form'):
                db.execute(f'ALTER TABLE prescription_items DROP COLUMN {column}')
            db.execute('DROP INDEX medicine_request')
            for column in ('strength','form','request_id'):
                db.execute(f'ALTER TABLE medicines DROP COLUMN {column}')
        migrated=Store(self.path)
        with migrated.connect() as db:
            self.assertEqual(migrated.prescription(db,visit),rx)
            self.assertEqual(migrated.invoice(db,visit),bill)
        # Once frozen, subsequent startup never overwrites an issued snapshot.
        with migrated.connect() as db:db.execute("UPDATE medicines SET price_cents=999 WHERE id='demo-a'")
        reopened=Store(self.path)
        with reopened.connect() as db:self.assertEqual(reopened.prescription(db,visit),rx)
