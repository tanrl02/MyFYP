import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews

class NotificationTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    publish=reviews.ReviewTests.publish
    lim=reviews.ReviewTests.lim

    def book(self):
        slot=self.client.get('/slots').json()[0]
        visit=self.client.post('/bookings',headers=self.patient,json={'slot_id':slot['id'],'request_id':'notification-book'}).json()
        return visit,slot

    def inbox(self,actor=None):return self.client.get('/notifications',headers=actor or self.patient)

    def test_queue_call_and_review_notifications_retry_and_reopen(self):
        self.assertEqual(self.inbox().json(),{'items':[],'unread_count':0})
        visit,slot=self.book();payload={'doctor_id':slot['doctor_id'],'clinic_date':slot['clinic_date']}
        self.assertEqual(self.client.post('/queue/call-next',headers=self.staff,json=payload).status_code,200)
        self.assertEqual(self.client.post('/queue/call-next',headers=self.staff,json=payload).status_code,409)
        photo=self.upload().json();share=self.share(photo['id']).json()
        self.publish(share['id']);self.publish(share['id'])
        inbox=self.inbox().json();self.assertEqual(len(inbox['items']),2);self.assertEqual(inbox['unread_count'],2)
        targets={item['kind']:item['target_id'] for item in inbox['items']}
        self.assertEqual(targets,{'queue_called':visit['id'],'review_published':photo['id']})
        self.assertNotIn('Fictional review only.',str(inbox));self.assertNotIn('photo_uri',str(inbox))
        self.assertEqual(self.inbox(self.other).json()['items'],[])
        self.assertEqual(TestClient(create_app(self.path)).get('/notifications',headers=self.patient).json(),inbox)
        # Retained notifications describe historical events, not current queue/grant state.
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.client.post(f"/assessment-shares/{share['id']}/revoke",headers=self.patient)
        self.assertEqual(self.inbox().json(),inbox)

    def test_read_ownership_idempotency_concurrency_and_persistence(self):
        photo=self.upload().json();grant=self.share(photo['id']).json();self.publish(grant['id'])
        item=self.inbox().json()['items'][0];route=f"/notifications/{item['id']}/read"
        self.assertEqual(self.client.post(route,headers=self.other).status_code,404)
        for actor in (self.staff,self.lim):
            self.assertEqual(self.inbox(actor).status_code,403)
            self.assertEqual(self.client.post(route,headers=actor).status_code,403)
        store=Store(self.path)
        with ThreadPoolExecutor(max_workers=4) as pool:
            stamps=list(pool.map(lambda _:store.read_notification(item['id'],'patient-ava')['read_at'],range(4)))
        self.assertEqual(len(set(stamps)),1)
        self.assertEqual(self.client.post(route,headers=self.patient).json()['read_at'],stamps[0])
        self.assertEqual(self.inbox().json()['unread_count'],0)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/notifications',headers=self.patient).json()['items'][0]['read_at'],stamps[0])

    def test_notification_failure_rolls_back_source_actions(self):
        visit,slot=self.book();photo=self.upload().json();grant=self.share(photo['id']).json();store=Store(self.path)
        def fail(*args):raise RuntimeError('Injected notification failure')
        store.notify=fail
        with self.assertRaises(RuntimeError):store.call_next(slot['doctor_id'],slot['clinic_date'],'staff-demo')
        with self.assertRaises(RuntimeError):store.publish_review(grant['id'],'doctor-lim','Fictional note','Demo follow-up')
        self.assertEqual(self.client.get('/bookings',headers=self.patient).json()[0]['status'],'waiting')
        self.assertIsNone(self.client.get("/assessment-shares",headers=self.patient).json()[0]["review"])
        self.assertEqual(self.inbox().json()['items'],[])
