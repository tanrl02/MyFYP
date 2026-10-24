from concurrent.futures import ThreadPoolExecutor
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews


class NotificationBatchTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp

    def seed(self,count=3,patient='patient-ava',kind='queue_called'):
        store=Store(self.path)
        source=str(uuid4())
        with store.connect() as db:
            for i in range(count):
                store.notify(db,patient,kind,f'{source}-{i}','fictional-visit','Fictional batch notification','Synthetic test only.')
            return [row['id'] for row in db.execute('SELECT id FROM patient_notifications WHERE source_id LIKE ? ORDER BY rowid',(source+'-%',))]

    def submit(self,ids,actor=None):
        return self.client.post('/notifications/read-displayed',headers=actor or self.patient,json={'notification_ids':ids})

    def test_exact_subset_new_arrivals_and_duplicate_ids(self):
        ids=self.seed()
        new=self.seed(1)
        result=self.submit([ids[1],ids[0],ids[1]])
        self.assertEqual(result.status_code,200)
        saved=result.json()
        self.assertEqual([n['id'] for n in saved['items']],[ids[1],ids[0]])
        self.assertEqual(saved['marked_count'],2)
        self.assertEqual(saved['unread_count'],2)
        self.assertEqual(len({n['read_at'] for n in saved['items']}),1)
        current={n['id']:n for n in self.client.get('/notifications',headers=self.patient).json()['items']}
        self.assertIsNone(current[ids[2]]['read_at'])
        self.assertIsNone(current[new[0]]['read_at'])

    def test_ownership_role_checks_and_atomic_rejection(self):
        own=self.seed(2);foreign=self.seed(1,'patient-noah')
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.submit(own,actor).status_code,403)
        self.assertEqual(self.client.post('/notifications/read-displayed',json={'notification_ids':own}).status_code,422)
        for bad in (foreign[0],'missing-id'):
            self.assertEqual(self.submit([own[0],bad]).status_code,404)
        self.assertEqual(self.submit(own,self.other).status_code,404)
        inbox=self.client.get('/notifications',headers=self.patient).json()
        self.assertEqual(inbox['unread_count'],2)
        self.assertTrue(all(n['read_at'] is None for n in inbox['items']))

    def test_hidden_reminder_rejects_whole_batch(self):
        own=self.seed(1);hidden=self.seed(1,kind='appointment_reminder')
        self.assertEqual(self.submit(own+hidden).status_code,404)
        inbox=self.client.get('/notifications',headers=self.patient).json()
        self.assertEqual(inbox['unread_count'],1)
        self.assertEqual([n['id'] for n in inbox['items']],own)
        self.assertIsNone(inbox['items'][0]['read_at'])

    def test_request_limits_and_unknown_fields(self):
        ids=self.seed(1)
        for body in ({'notification_ids':[]},{'notification_ids':['x']*101},{'notification_ids':['']},{'notification_ids':ids,'patient_id':'patient-noah'}):
            self.assertEqual(self.client.post('/notifications/read-displayed',headers=self.patient,json=body).status_code,422)
        self.assertEqual(self.client.get('/notifications',headers=self.patient).json()['unread_count'],1)

    def test_concurrent_retry_is_idempotent_and_persists(self):
        ids=self.seed(2);store=Store(self.path)
        with ThreadPoolExecutor(max_workers=3) as pool:
            results=list(pool.map(lambda _:store.read_notifications(ids,'patient-ava'),range(3)))
        self.assertEqual(sorted(r['marked_count'] for r in results),[0,0,2])
        self.assertEqual(len({n['read_at'] for r in results for n in r['items']}),1)
        reopened=TestClient(create_app(self.path))
        saved=reopened.get('/notifications',headers=self.patient).json()
        self.assertEqual(saved['unread_count'],0)
        self.assertEqual({n['id']:n['read_at'] for n in saved['items']},{n['id']:n['read_at'] for n in results[0]['items']})

    def test_total_unread_count_is_not_limited_to_loaded_hundred(self):
        ids=self.seed(103)
        self.assertEqual(len(self.client.get('/notifications',headers=self.patient).json()['items']),100)
        saved=self.submit(ids[:2]).json()
        self.assertEqual(saved['marked_count'],2)
        self.assertEqual(saved['unread_count'],101)
