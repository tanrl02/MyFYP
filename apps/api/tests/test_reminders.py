import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews

class ReminderClock(datetime):
    instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
    @classmethod
    def now(cls,tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)

class ReminderTests(unittest.TestCase):
    def setUp(self):
        ReminderClock.instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
        clock=patch('app.store.datetime',ReminderClock)
        clock.start();self.addCleanup(clock.stop)
        reviews.ReviewTests.setUp(self)
        self.store=Store(self.path)

    def book_at(self,hours,request='reminder-book',doctor='doctor-lim'):
        start=ReminderClock.instant.astimezone(timezone(timedelta(hours=8)))+timedelta(hours=hours)
        slot=self.store.add_slot(doctor,start.date().isoformat(),start.strftime('%H:%M'),2,request+'-slot')
        return self.store.book('patient-ava',slot['id'],request)

    def inbox(self):return self.client.get('/notifications',headers=self.patient).json()

    def test_reminder_window_timezone_retry_read_and_restart(self):
        near=self.book_at(2)
        self.book_at(24,'boundary-book')
        self.book_at(25,'later-book')
        inbox=self.inbox()
        self.assertEqual(len(inbox['items']),2)
        self.assertEqual(inbox['unread_count'],2)
        item=next(n for n in inbox['items'] if n['target_id']==near['id'])
        self.assertEqual(item['kind'],'appointment_reminder')
        self.assertIn('01 Jan 2035, 02:00 PM (Malaysia time)',item['message'])
        self.assertEqual(self.inbox(),inbox)
        route=f"/notifications/{item['id']}/read"
        read=self.client.post(route,headers=self.patient).json()
        self.assertEqual(self.client.post(route,headers=self.patient).json(),read)
        reopened=TestClient(create_app(self.path))
        saved=reopened.get('/notifications',headers=self.patient).json()
        self.assertEqual(saved['unread_count'],1)
        self.assertEqual(next(n for n in saved['items'] if n['id']==item['id']),read)
        ReminderClock.instant+=timedelta(hours=1)
        self.assertEqual(len(self.inbox()['items']),3)  # 25-hour visit now enters window
        ReminderClock.instant+=timedelta(hours=1)
        current=self.inbox()
        self.assertNotIn(item['id'],[n['id'] for n in current['items']])
        self.assertEqual(current['unread_count'],2)
        self.assertEqual(self.client.post(route,headers=self.patient).status_code,404)

    def test_reminder_cancel_reschedule_call_and_completion(self):
        visit=self.book_at(2)
        old=self.inbox()['items'][0]
        target=self.book_at(3,'target-book','doctor-anita')
        # Release the target fixture, then move the first visit there.
        self.store.cancel(target['id'],'patient-ava')
        moved=self.store.reschedule(visit['id'],'patient-ava',target['slot_id'],'reminder-reschedule')
        inbox=self.inbox()
        self.assertEqual(len(inbox['items']),1)
        self.assertEqual(inbox['items'][0]['target_id'],moved['id'])
        self.assertEqual(self.client.post(f"/notifications/{old['id']}/read",headers=self.patient).status_code,404)
        self.store.call_next('doctor-anita',moved['clinic_date'],'staff-demo')
        self.assertEqual([n['kind'] for n in self.inbox()['items']],['queue_called'])
        self.store.complete(moved['id'],'staff-demo')
        self.assertEqual([n['kind'] for n in self.inbox()['items']],['queue_called'])
        cancelled=self.book_at(4,'cancel-book')
        self.inbox()
        self.store.cancel(cancelled['id'],'patient-ava')
        self.assertEqual(self.inbox()['unread_count'],1)  # historical queue call only

    def test_reminder_roles_and_concurrent_refresh(self):
        self.book_at(2)
        with ThreadPoolExecutor(max_workers=4) as pool:
            snapshots=list(pool.map(lambda _:self.store.notifications('patient-ava'),range(4)))
        self.assertTrue(all(s==snapshots[0] for s in snapshots))
        item=snapshots[0]['items'][0]
        self.assertEqual(len(snapshots[0]['items']),1)
        self.assertEqual(self.client.get('/notifications',headers=self.other).json(),{'items':[],'unread_count':0})
        self.assertEqual(self.client.post(f"/notifications/{item['id']}/read",headers=self.other).status_code,404)
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.client.get('/notifications',headers=actor).status_code,403)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM patient_notifications WHERE kind='appointment_reminder'").fetchone()[0],1)
