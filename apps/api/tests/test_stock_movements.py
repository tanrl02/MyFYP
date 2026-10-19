import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_care as care


class StockMovementTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def history(self,item='demo-a',actor=None):
        return self.client.get(f'/stock/{item}/movements',headers=actor or self.staff)

    def test_roles_empty_unknown_and_read_only(self):
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.history(actor=actor).status_code,403)
        self.assertEqual(self.history('missing').status_code,404)
        before=Store(self.path).stock()
        result=self.history().json()
        self.assertEqual(result['medicine']['stock'],20)
        self.assertNotIn('creation_json',result['medicine'])
        self.assertNotIn('request_id',result['medicine'])
        self.assertEqual(result['movements'],[])
        self.assertFalse(result['has_more'])
        self.assertEqual(Store(self.path).stock(),before)

    def test_receiving_dispensing_losses_and_reopen(self):
        store=Store(self.path)
        store.receive_stock('demo-a',4,'Fictional delivery','movement-receipt','staff-demo')
        visit=self.prepare();rx=self.issue(visit).json()
        self.assertEqual(len(self.history().json()['movements']),1)  # Issued is not a stock movement.
        self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff)
        self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff)
        store.record_stock_loss('demo-a',3,'damaged','Fictional damaged units','movement-loss','staff-demo')
        store.record_stock_loss('demo-b',1,'lost','Other item','other-item-loss','staff-demo')
        saved=self.history().json()
        self.assertEqual(saved['medicine']['stock'],19)
        self.assertEqual([m['kind'] for m in saved['movements']],['damaged','dispensed','received'])
        self.assertEqual([m['change'] for m in saved['movements']],[-3,-2,4])
        self.assertEqual((saved['movements'][0]['stock_before'],saved['movements'][0]['stock_after']),(22,19))
        dispensed=saved['movements'][1]
        self.assertIsNone(dispensed['stock_before']);self.assertIsNone(dispensed['stock_after'])
        self.assertEqual(dispensed['source_id'],rx['id'])
        self.assertNotIn('patient_id',dispensed);self.assertNotIn('directions',dispensed)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/stock/demo-a/movements',headers=self.staff).json(),saved)

    def test_inactive_and_saved_labels_survive_catalogue_changes(self):
        store=Store(self.path);original=store.catalog()[0]['name']
        visit=self.prepare();rx=self.issue(visit).json()
        self.client.post(f"/prescriptions/{rx['id']}/dispense",headers=self.staff)
        store.record_stock_loss('demo-a',1,'lost','Fictional loss','label-loss-key','staff-demo')
        with store.connect() as db:
            db.execute("UPDATE medicines SET name='Renamed fictional item',active=0 WHERE id='demo-a'")
        saved=self.history().json()
        self.assertFalse(saved['medicine']['active'])
        self.assertEqual(saved['medicine']['name'],'Renamed fictional item')
        self.assertTrue(all(m['item_label']==original for m in saved['movements']))

    def test_per_item_limit_and_timestamp_order_without_global_truncation(self):
        store=Store(self.path)
        with store.connect() as db:
            for n in range(103):
                db.execute('INSERT INTO stock_receipts VALUES(?,?,?,?,?,?,?,?,?)',
                    (f'a-{n:03}','demo-a',1,'Fixture',0,1,'staff-demo',f'request-a-{n}','2026-10-19T00:00:00+00:00'))
            db.execute('INSERT INTO stock_receipts VALUES(?,?,?,?,?,?,?,?,?)',
                ('b-old','demo-b',1,'Other fixture',0,1,'staff-demo','request-b-old','2020-01-01T00:00:00+00:00'))
            # Same calendar text, but this offset makes a-000 newer than the +00 rows.
            db.execute("UPDATE stock_receipts SET created_at='2026-10-19T00:00:00-01:00' WHERE id='a-000'")
        saved=self.history().json()
        self.assertTrue(saved['has_more']);self.assertEqual(len(saved['movements']),100)
        self.assertEqual(saved['movements'][0]['source_id'],'a-000')
        self.assertEqual(saved['movements'][1]['source_id'],'a-102')
        other=self.history('demo-b').json()
        self.assertFalse(other['has_more']);self.assertEqual(other['movements'][0]['source_id'],'b-old')
