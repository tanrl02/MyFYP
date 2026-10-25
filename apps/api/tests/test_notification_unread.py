from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_notification_batch as batch


class NotificationUnreadTests(unittest.TestCase):
    setUp=batch.NotificationBatchTests.setUp
    seed=batch.NotificationBatchTests.seed

    def submit(self,id,actor=None):
        return self.client.post('/notifications/'+id+'/unread',headers=actor or self.patient,json={})

    def test_read_to_unread_persists_and_preserves_message_and_other_rows(self):
        ids=self.seed(2)
        read=self.client.post('/notifications/'+ids[0]+'/read',headers=self.patient).json()
        result=self.submit(ids[0])
        self.assertEqual(result.status_code,200)
        saved=result.json()
        self.assertIsNone(saved['item']['read_at'])
        self.assertEqual(saved['unread_count'],2)
        self.assertEqual({k:v for k,v in saved['item'].items() if k!='read_at'},{k:v for k,v in read.items() if k!='read_at'})
        reopened=TestClient(create_app(self.path)).get('/notifications',headers=self.patient).json()
        self.assertEqual(reopened['unread_count'],2)
        self.assertTrue(all(n['read_at'] is None for n in reopened['items']))
        stamp=self.client.post('/notifications/'+ids[0]+'/read',headers=self.patient).json()['read_at']
        self.assertIsNotNone(stamp)
        self.assertEqual(self.client.get('/notifications',headers=self.patient).json()['unread_count'],1)

    def test_ownership_roles_missing_and_hidden_notification(self):
        own=self.seed(1)[0];foreign=self.seed(1,'patient-noah')[0]
        hidden=self.seed(1,kind='appointment_reminder')[0]
        self.client.post('/notifications/'+own+'/read',headers=self.patient)
        for id in (foreign,hidden,'missing'):
            self.assertEqual(self.submit(id).status_code,404)
        self.assertEqual(self.submit(own,self.other).status_code,404)
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.submit(own,actor).status_code,403)
        self.assertEqual(self.client.post('/notifications/'+own+'/unread').status_code,422)
        saved=self.client.get('/notifications',headers=self.patient).json()
        self.assertEqual(saved['unread_count'],0)
        self.assertIsNotNone(saved['items'][0]['read_at'])

    def test_concurrent_retries_do_not_inflate_count(self):
        id=self.seed(1)[0];store=Store(self.path)
        store.read_notification(id,'patient-ava')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:store.unread_notification(id,'patient-ava'),range(4)))
        self.assertTrue(all(r['unread_count']==1 and r['item']['read_at'] is None for r in results))
        self.assertEqual(self.submit(id).json(),results[0])

    def test_unread_count_includes_older_pages(self):
        ids=self.seed(103);store=Store(self.path)
        # Windows clock resolution can give seeded rows identical timestamps.
        with store.connect() as db:
            db.execute("UPDATE patient_notifications SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?",(ids[0],))
        store.read_notification(ids[0],'patient-ava')
        inbox=self.client.get('/notifications',headers=self.patient).json()
        self.assertEqual(len(inbox['items']),100)
        self.assertNotIn(ids[0],[n['id'] for n in inbox['items']])
        saved=self.submit(ids[0]).json()
        self.assertEqual(saved['unread_count'],103)
        self.assertIsNone(saved['item']['read_at'])
