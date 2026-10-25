import unittest
from app.store import Store
import test_notification_batch as batch


class NotificationPagingTests(unittest.TestCase):
    setUp=batch.NotificationBatchTests.setUp
    seed=batch.NotificationBatchTests.seed

    def page(self,cursor=None,actor=None):
        return self.client.get('/notifications',headers=actor or self.patient,params={} if cursor is None else {'cursor':cursor})

    def test_equal_time_pages_are_stable_with_new_arrivals_and_read_changes(self):
        ids=self.seed(205)
        with Store(self.path).connect() as db:
            db.execute("UPDATE patient_notifications SET created_at='2026-01-01T00:00:00+00:00'")
        first=self.page().json()
        self.assertEqual(len(first['items']),100)
        cursor=first['next_cursor']
        arrival=self.seed(1)[0]
        self.client.post('/notifications/'+cursor+'/read',headers=self.patient,json={})
        second=self.page(cursor).json()
        self.assertEqual(second,self.page(cursor).json())
        third=self.page(second['next_cursor']).json()
        self.assertEqual([len(p['items']) for p in (first,second,third)],[100,100,5])
        collected=[n['id'] for p in (first,second,third) for n in p['items']]
        self.assertEqual(collected,sorted(ids,reverse=True))
        self.assertNotIn(arrival,collected)
        self.assertEqual(len(set(collected)),205)
        self.assertIsNone(third['next_cursor'])
        self.assertEqual(third['unread_count'],205)
        last=self.page(third['items'][-1]['id']).json()
        self.assertEqual(last['items'],[])
        self.assertIsNone(last['next_cursor'])
        self.assertEqual(self.page().json()['items'][0]['id'],arrival)

    def test_cursor_validation_patient_scope_and_roles(self):
        own=self.seed(1)[0];foreign=self.seed(1,'patient-noah')[0]
        for cursor in ('missing',foreign,'','x'*101):
            self.assertEqual(self.page(cursor).status_code,422)
        self.assertEqual(self.page(own,self.other).status_code,422)
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.page(own,actor).status_code,403)
        self.assertEqual(self.client.get('/notifications',params={'cursor':own}).status_code,422)
        saved=self.page().json()
        self.assertEqual(saved['unread_count'],1)
        self.assertIsNone(saved['items'][0]['read_at'])

    def test_hidden_reminders_do_not_fill_pages_and_hidden_anchor_still_works(self):
        ids=self.seed(101)
        hidden=self.seed(1,kind='appointment_reminder')[0]
        with Store(self.path).connect() as db:
            db.execute("UPDATE patient_notifications SET created_at='2026-01-01T00:00:00+00:00'")
        first=self.page().json()
        last=self.page(first['next_cursor']).json()
        self.assertEqual(len(first['items']),100)
        self.assertEqual(len(last['items']),1)
        self.assertNotIn(hidden,[n['id'] for n in first['items']+last['items']])
        expected=sorted([i for i in ids if i<hidden],reverse=True)[:100]
        self.assertEqual([n['id'] for n in self.page(hidden).json()['items']],expected)
        self.assertEqual(last['unread_count'],101)
