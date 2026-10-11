from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care

class StockTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue
    def receive(self,actor=None,**changes):
        payload={'medicine_id':'demo-a','quantity':3,'reason':'Fictional delivery','request_id':'receipt-request-one'}|changes
        return self.client.post('/stock/receive',headers=actor or self.staff,json=payload)
    def test_receipt_retry_history_persistence_and_catalog(self):
        response=self.receive();self.assertEqual(response.status_code,201)
        saved=response.json();self.assertEqual((saved['stock_before'],saved['stock_after']),(20,23))
        self.assertEqual(self.receive().json()['id'],saved['id'])
        for changes in ({'quantity':4},{'reason':'Different delivery'},{'medicine_id':'demo-b'}):
            self.assertEqual(self.receive(**changes).status_code,409)
        stock=self.client.get('/stock',headers=self.staff).json()
        self.assertEqual(stock['medicines'][0]['stock'],23);self.assertEqual(len(stock['receipts']),1)
        self.assertEqual(stock['receipts'][0]['actor_id'],'staff-demo')
        self.assertEqual(stock['low_stock_threshold'],5)
        self.assertEqual(TestClient(create_app(self.path)).get('/stock',headers=self.staff).json(),stock)
        self.assertEqual(Store(self.path).catalog()[0]['price_cents'],500)
    def test_roles_inputs_and_limit_preserve_stock(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.receive(actor).status_code,403)
            self.assertEqual(self.client.get('/stock',headers=actor).status_code,403)
        for quantity in (0,-1,1001,True,1.5,'3'):
            self.assertEqual(self.receive(quantity=quantity).status_code,422)
        for reason in ('','   ','x'*301):self.assertEqual(self.receive(reason=reason).status_code,422)
        self.assertEqual(self.receive(request_id='short').status_code,422)
        self.assertEqual(self.receive(medicine_id='unknown').status_code,404)
        store=Store(self.path)
        self.assertEqual(store.stock()['receipts'],[])
        with store.connect() as db:db.execute("UPDATE medicines SET stock=99999 WHERE id='demo-a'")
        self.assertEqual(self.receive().status_code,409)
        self.assertEqual(store.catalog()[0]['stock'],99999)
        self.assertEqual(store.stock()['receipts'],[])
    def test_concurrent_receiving_dispensing_and_low_stock(self):
        visit=self.prepare();rx=self.issue(visit).json();store=Store(self.path)
        def receive(_):return store.receive_stock('demo-a',3,'Demo receipt','concurrent-receipt','staff-demo')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(len(set(pool.map(receive,range(4)))),1)
        def operate(receiving):
            if receiving:return store.receive_stock('demo-a',4,'Another delivery','another-receipt','staff-demo')
            return store.dispense(rx['id'],'staff-demo')
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(operate,[True,False]))
        self.assertEqual(store.catalog()[0]['stock'],25)
        store.dispense(rx['id'],'staff-demo');self.assertEqual(store.catalog()[0]['stock'],25)
        with store.connect() as db:db.execute("UPDATE medicines SET stock=4 WHERE id='demo-a'")
        overview=store.stock();self.assertLessEqual(overview['medicines'][0]['stock'],overview['low_stock_threshold'])
        # Receiving snapshots stay fixed after subsequent dispensing/adjustments.
        self.assertEqual(overview['receipts'][0]['stock_after'],27 if overview['receipts'][0]['stock_before']==23 else 25)
