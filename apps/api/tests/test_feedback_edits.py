import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store
import test_feedback as feedback


class FeedbackClock(datetime):
    instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
    @classmethod
    def now(cls,tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


class FeedbackEditTests(unittest.TestCase):
    book=feedback.FeedbackTests.book
    finish=feedback.FeedbackTests.finish
    submit=feedback.FeedbackTests.submit

    def setUp(self):
        FeedbackClock.instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
        clock=patch('app.store.datetime',FeedbackClock)
        clock.start();self.addCleanup(clock.stop)
        feedback.FeedbackTests.setUp(self)

    def fixture(self):
        visit=self.finish()
        saved=self.submit(visit).json()
        return visit,saved,f"/visits/{visit['id']}/feedback/edit"

    def test_edit_keeps_identity_submission_time_deadline_and_shared_latest_rating(self):
        visit,saved,url=self.fixture()
        FeedbackClock.instant+=timedelta(hours=1)
        response=self.client.post(url,headers=self.patient,json={'rating':5,'comment':'  Revised fictional feedback  ','version':0})
        self.assertEqual(response.status_code,200)
        updated=response.json()
        self.assertEqual((updated['id'],updated['created_at'],updated['edit_deadline']),(saved['id'],saved['created_at'],saved['edit_deadline']))
        self.assertEqual((updated['rating'],updated['comment'],updated['version']),(5,'Revised fictional feedback',1))
        self.assertEqual(updated['edited_at'],FeedbackClock.instant.isoformat())
        for actor in (self.patient,self.staff):
            self.assertEqual(self.client.get('/feedback',headers=actor).json(),[updated])
        detail=self.client.get(f"/bookings/{visit['id']}/details",headers=self.patient).json()['feedback']
        self.assertEqual(detail,{k:v for k,v in updated.items() if k!='visit'})
        report=Store(self.path).daily_report('2035-01-01')
        self.assertEqual(report['feedback'],{'count':1,'average_rating':5.0})
        self.assertEqual(TestClient(create_app(self.path)).get('/feedback',headers=self.patient).json(),[updated])
        self.assertEqual(self.client.get('/feedback',headers=self.other).json(),[])
        self.assertEqual(self.submit(visit).status_code,409)

    def test_exact_deadline_timezone_and_successful_retry_after_expiry(self):
        visit,saved,url=self.fixture()
        store=Store(self.path)
        # Equivalent offset timestamp: the server must compare instants rather than strings.
        original=datetime.fromisoformat(saved['created_at']).astimezone(timezone(timedelta(hours=8)))
        with store.connect() as db:db.execute('UPDATE visit_feedback SET created_at=? WHERE booking_id=?',(original.isoformat(),visit['id']))
        FeedbackClock.instant+=timedelta(hours=24,microseconds=-1)
        body={'rating':3,'comment':'Before deadline','version':0}
        updated=self.client.post(url,headers=self.patient,json=body)
        self.assertEqual(updated.status_code,200)
        FeedbackClock.instant+=timedelta(microseconds=1)
        self.assertEqual(self.client.post(url,headers=self.patient,json={'rating':2,'comment':'At deadline','version':1}).status_code,409)
        self.assertEqual(self.client.post(url,headers=self.patient,json=body).json(),updated.json())
        FeedbackClock.instant+=timedelta(days=1)
        self.assertEqual(self.client.post(url,headers=self.patient,json={'rating':1,'comment':'Late','version':1}).status_code,409)
        self.assertEqual(self.client.get('/feedback',headers=self.patient).json(),[updated.json()])

    def test_roles_ownership_status_missing_input_and_no_op(self):
        visit,saved,url=self.fixture();body={'rating':2,'comment':'Changed','version':0}
        for actor in (self.other,self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.client.post(url,headers=actor,json=body).status_code,403)
        for changes in ({'rating':0},{'rating':6},{'rating':True},{'rating':'2'},{'comment':'x'*1001},{'version':True},{'version':-1},{'version':'0'}):
            self.assertEqual(self.client.post(url,headers=self.patient,json=body|changes).status_code,422)
        self.assertEqual(self.client.post('/visits/missing/feedback/edit',headers=self.patient,json=body).status_code,404)
        self.assertEqual(self.client.post(url,headers=self.patient,json=body|{'rating':saved['rating'],'comment':saved['comment']}).json(),saved)
        with Store(self.path).connect() as db:
            for status in ('waiting','called','cancelled'):
                db.execute('UPDATE bookings SET status=? WHERE id=?',(status,visit['id']));db.commit()
                self.assertEqual(self.client.post(url,headers=self.patient,json=body).status_code,409)
            db.execute("UPDATE bookings SET status='completed' WHERE id=?",(visit['id'],))
            db.execute('DELETE FROM visit_feedback WHERE booking_id=?',(visit['id'],));db.commit()
        self.assertEqual(self.client.post(url,headers=self.patient,json=body).status_code,404)

    def test_concurrent_edits_and_lost_response_retry_never_overwrite_newer_content(self):
        visit,_,url=self.fixture();store=Store(self.path)
        def edit(comment):
            try:return store.edit_feedback(visit['id'],'patient-ava',5,comment,0)['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(edit,['First edit','Other edit'])),[1,409])
        saved=self.client.get('/feedback',headers=self.patient).json()[0]
        with ThreadPoolExecutor(max_workers=3) as pool:
            self.assertEqual(list(pool.map(edit,[saved['comment']]*3)),[1,1,1])
        store.edit_feedback(visit['id'],'patient-ava',4,'Newer edit',1)
        self.assertEqual(edit(saved['comment']),409)
        self.assertEqual(self.client.get('/feedback',headers=self.patient).json()[0]['comment'],'Newer edit')
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM visit_feedback').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='feedback-edited'").fetchone()[0],2)

    def test_failed_edit_rolls_back_and_migration_preserves_old_submission(self):
        visit,saved,_=self.fixture();store=Store(self.path)
        def fail(*args):raise RuntimeError('Injected edit event failure')
        store.event=fail
        with self.assertRaises(RuntimeError):store.edit_feedback(visit['id'],'patient-ava',5,'Failed edit',0)
        self.assertEqual(store.feedback('patient-ava'),[saved])
        with store.connect() as db:
            db.execute('ALTER TABLE visit_feedback DROP COLUMN version')
            db.execute('ALTER TABLE visit_feedback DROP COLUMN edited_at')
        reopened=Store(self.path)
        self.assertEqual(reopened.feedback('patient-ava'),[saved])
        self.assertEqual(reopened.edit_feedback(visit['id'],'patient-ava',5,'After migration',0)['version'],1)
