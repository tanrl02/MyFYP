import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_follow_up as follow_up


class FollowUpNotificationTests(unittest.TestCase):
    setUp=follow_up.FollowUpTests.setUp
    recommend=follow_up.FollowUpTests.recommend
    book_follow_up=follow_up.FollowUpTests.book_follow_up

    def items(self,actor=None):
        response=self.client.get('/notifications',headers=actor or self.patient)
        self.assertEqual(response.status_code,200)
        return [item for item in response.json()['items'] if item['kind']=='follow_up_recommended']

    def test_atomic_notification_target_copy_and_patient_role_privacy(self):
        self.assertEqual(self.items(),[])
        response=self.recommend(reason='Private fictional clinical reason not for notifications.')
        self.assertEqual(response.status_code,200)
        item=self.items()[0]
        self.assertEqual((item['source_id'],item['target_id']),(self.source['id'],self.source['id']))
        self.assertEqual(item['title'],'Follow-up visit recommended')
        self.assertIn(date.fromisoformat(self.due).strftime('%d %b %Y'),item['message'])
        self.assertIn('on or after',item['message'])
        self.assertIn('Malaysia',item['message'])
        self.assertIn('No appointment is booked',item['message'])
        self.assertNotIn('Private fictional clinical reason',str(item))
        self.assertIsNone(item['read_at'])
        self.assertEqual(len(self.client.get('/bookings',headers=self.patient).json()),1)
        self.assertEqual(self.items(self.other),[])
        self.assertEqual(self.client.get(f"/bookings/{item['target_id']}/details",headers=self.patient).json()['follow_up'],response.json())
        self.assertEqual(self.client.get(f"/bookings/{item['target_id']}/details",headers=self.other).status_code,404)
        for actor in (self.staff,self.lim,{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.client.get('/notifications',headers=actor).status_code,403)
            self.assertEqual(self.client.post(f"/notifications/{item['id']}/read",headers=actor).status_code,403)
        queue=self.client.get('/queue',headers=self.staff,params={'doctor_id':'doctor-lim','clinic_date':self.source['clinic_date']})
        self.assertNotIn('Private fictional clinical reason',queue.text)

    def test_retry_concurrency_read_reopen_and_booking_retains_history(self):
        def recommend(_):
            return self.store.recommend_follow_up(self.source['id'],'doctor-lim',self.due,'Fictional follow-up recommendation.')
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(recommend,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        self.assertEqual(len(self.items()),1)
        item=self.items()[0];url=f"/notifications/{item['id']}/read"
        self.assertEqual(self.client.post(url,headers=self.other).status_code,404)
        saved=self.client.post(url,headers=self.patient).json()
        self.assertIsNotNone(saved['read_at'])
        self.assertEqual(self.client.post(url,headers=self.patient).json(),saved)
        self.assertEqual(self.recommend().status_code,200)
        self.assertEqual(self.items(),[saved])
        self.assertEqual(self.recommend(reason='Changed').status_code,409)
        reopened=TestClient(create_app(self.path))
        self.assertEqual([n for n in reopened.get('/notifications',headers=self.patient).json()['items'] if n['kind']=='follow_up_recommended'],[saved])
        booked=self.book_follow_up().json()
        self.assertEqual(self.items(),[saved])
        self.store.cancel(booked['id'],'patient-ava')
        self.assertEqual(self.items(),[saved])
        self.assertEqual(self.client.get(f"/bookings/{saved['target_id']}/details",headers=self.patient).json()['follow_up']['booked_visit']['status'],'cancelled')

    def test_failed_notification_rolls_back_recommendation_and_retry_recovers(self):
        def fail(*args):raise RuntimeError('Injected notification failure')
        self.store.notify=fail
        with self.assertRaises(RuntimeError):
            self.store.recommend_follow_up(self.source['id'],'doctor-lim',self.due,'Fictional follow-up recommendation.')
        self.assertIsNone(self.store.visit_details(self.source['id'],'patient-ava')['follow_up'])
        self.assertEqual(self.items(),[])
        self.assertEqual(self.recommend().status_code,200)
        self.assertEqual(len(self.items()),1)

    def test_invalid_unauthorized_and_legacy_recommendations_do_not_notify(self):
        body={'recommended_date':self.due,'reason':'Fictional reason'}
        for actor in (self.patient,self.other,self.staff,{'X-Demo-Actor':'doctor-anita'}):
            self.assertIn(self.client.post(self.url,headers=actor,json=body).status_code,(403,404))
        self.assertEqual(self.recommend(recommended_date=self.source['clinic_date']).status_code,422)
        self.assertEqual(self.items(),[])
        # Existing recommendations remain history; opening the inbox or retrying does not backfill alerts.
        with self.store.connect() as db:
            db.execute('INSERT INTO follow_up_recommendations VALUES(?,?,?,?,?)',
                       (self.source['id'],'doctor-lim',self.due,'Fictional follow-up recommendation.','2026-10-01T00:00:00+00:00'))
        self.assertEqual(self.recommend().status_code,200)
        reopened=Store(self.path)
        self.assertFalse(any(item['kind']=='follow_up_recommended' for item in reopened.notifications('patient-ava')['items']))
