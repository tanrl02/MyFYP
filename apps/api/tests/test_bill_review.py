import unittest
from app.store import Store
import test_care as care


class BillReviewTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def test_consultation_review_retry_and_legacy_requests(self):
        visit=self.prepare();url=f'/visits/{visit}/invoice'
        saved=self.client.post(url,headers=self.staff,json={'prescription_id':None}).json()
        self.assertEqual(saved['total_cents'],3000)
        self.assertEqual(saved['status'],'unpaid')
        self.assertEqual(self.client.post(url,headers=self.staff,json={'prescription_id':None}).json(),saved)
        self.assertEqual(self.client.post(url,headers=self.staff,json={}).json(),saved)
        self.assertEqual(self.client.post(url,headers=self.staff).json(),saved)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],1)

    def test_changed_prescription_rejected_then_saved_prices_and_retry_preserved(self):
        visit=self.prepare();url=f'/visits/{visit}/invoice'
        prescription=self.issue(visit).json()
        store=Store(self.path)
        before=store.stock()
        stale=self.client.post(url,headers=self.staff,json={'prescription_id':None})
        self.assertEqual(stale.status_code,409)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM invoices').fetchone()[0],0)
            db.execute("UPDATE medicines SET price_cents=9999,name='Changed catalogue label' WHERE id='demo-a'")
        saved=self.client.post(url,headers=self.staff,json={'prescription_id':prescription['id']}).json()
        self.assertEqual(saved['total_cents'],4000)
        self.assertEqual(saved['lines'][1]['unit_price_cents'],500)
        self.assertEqual(saved['lines'][1]['description'],'Demo item A (not medication)')
        self.assertEqual(self.client.post(url,headers=self.staff,json={'prescription_id':prescription['id']}).json(),saved)
        self.assertEqual(store.stock()['medicines'][0]['stock'],before['medicines'][0]['stock'])
        self.assertEqual(self.client.post(url,headers=self.staff,json={'prescription_id':'different-prescription'}).status_code,409)

    def test_review_roles_strict_payload_and_completed_visit_guard(self):
        visit=self.prepare(completed=False);url=f'/visits/{visit}/invoice'
        for actor in (self.patient,self.other,self.doctor):
            self.assertEqual(self.client.post(url,headers=actor,json={'prescription_id':None}).status_code,403)
        for payload in ({'prescription_id':1},{'prescription_id':'x'*101},{'prescription_id':None,'total_cents':0}):
            self.assertEqual(self.client.post(url,headers=self.staff,json=payload).status_code,422)
        self.assertEqual(self.client.post(url,headers=self.staff,json={'prescription_id':None}).status_code,409)
