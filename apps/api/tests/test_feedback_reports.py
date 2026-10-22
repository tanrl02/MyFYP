import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_feedback as feedback


class FeedbackReportTests(unittest.TestCase):
    setUp=feedback.FeedbackTests.setUp
    book=feedback.FeedbackTests.book
    finish=feedback.FeedbackTests.finish
    submit=feedback.FeedbackTests.submit

    def report(self, **filters):
        return self.client.get('/reports/feedback',headers=self.staff,
            params=filters or {'period':'month','year':2032,'month':2})

    def test_roles_validation_empty_and_read_only(self):
        store=Store(self.path)
        with store.connect() as db:before=list(db.iterdump())
        for actor in ('patient-ava','patient-noah','doctor-lim','doctor-anita'):
            self.assertEqual(self.client.get('/reports/feedback',headers={'X-Demo-Actor':actor},params={'period':'year','year':2032}).status_code,403)
        for params in ({'period':'week','year':2032},{'period':'month','year':2032},
                       {'period':'quarter','year':2032,'quarter':5},{'period':'year','year':2032,'month':1},
                       {'period':'month','year':2032,'month':2,'quarter':1},{'period':'year','year':9999}):
            self.assertEqual(self.report(**params).status_code,422)
        data=self.report().json()
        self.assertEqual((data['start_date'],data['end_date']),('2032-02-01','2032-02-29'))
        self.assertEqual(data['count'],0);self.assertIsNone(data['average_rating'])
        self.assertEqual(data['ratings'],[{'rating':n,'count':0} for n in range(1,6)])
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_malaysia_boundaries_current_rating_and_reopening(self):
        saved=self.submit(self.finish(),rating=2).json();store=Store(self.path)
        for timestamp,expected in [('2032-01-31T15:59:59+00:00',0),('2032-01-31T16:00:00+00:00',1),
                                   ('2032-02-29T15:59:59+00:00',1),('2032-02-29T16:00:00+00:00',0),
                                   ('2032-02-01T00:00:00+08:00',1)]:
            with store.connect() as db:db.execute('UPDATE visit_feedback SET created_at=?',(timestamp,))
            self.assertEqual(self.report().json()['count'],expected)
        with store.connect() as db:
            db.execute("UPDATE visit_feedback SET rating=5,edited_at='2032-03-01T00:00:00+00:00',version=1")
            before=list(db.iterdump())
        data=self.report().json();self.assertEqual((data['count'],data['average_rating']),(1,5))
        self.assertEqual(data['ratings'][-1],{'rating':5,'count':1})
        self.assertEqual(self.report(period='month',year=2032,month=3).json()['count'],0)
        reopened=TestClient(create_app(self.path)).get('/reports/feedback',headers=self.staff,params={'period':'month','year':2032,'month':2}).json()
        for key in ('count','average_rating','ratings','start_date','end_date'):self.assertEqual(data[key],reopened[key])
        for private in ('patient','comment','booking_id',saved['id']):self.assertNotIn(private,str(data))
        with store.connect() as db:self.assertEqual(list(db.iterdump()),before)

    def test_all_records_beyond_list_limit_and_calendar_filters(self):
        visit=self.finish();store=Store(self.path)
        with store.connect() as db:
            # Direct isolated historical fixtures retain the production schema and
            # one-submission-per-visit constraint, without 106 HTTP booking flows.
            for i in range(106):
                key='feedback-volume-'+str(i)
                db.execute('''INSERT INTO bookings(id,patient_id,slot_id,queue_number,status,created_at,request_id)
                    SELECT ?,patient_id,slot_id,?,'completed',created_at,? FROM bookings WHERE id=?''',
                    (key,i+10,key,visit['id']))
                db.execute('''INSERT INTO visit_feedback(id,booking_id,patient_id,rating,comment,created_at)
                    VALUES(?,?,?,?,?,?)''',(key,key,'patient-ava',1 if i<5 else 5 if i<105 else 3,'Private',
                    '2032-10-01T00:00:00+08:00' if i<105 else '2033-01-01T00:00:00+08:00'))
        for filters in ({'period':'month','year':2032,'month':10},{'period':'quarter','year':2032,'quarter':4},{'period':'year','year':2032}):
            data=self.report(**filters).json();self.assertEqual(data['count'],105)
            self.assertAlmostEqual(data['average_rating'],505/105)
            self.assertEqual([r['count'] for r in data['ratings']],[5,0,0,0,100])
        self.assertEqual(self.report(period='quarter',year=2032,quarter=3).json()['count'],0)
