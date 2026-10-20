from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
from app.booking_migrations import allow_missed_bookings
import test_workflow as workflow


class MissedVisitTests(unittest.TestCase):
    setUp = workflow.WorkflowTests.setUp

    def post(self, visit, when=None, actor=None):
        with patch('app.store.datetime', wraps=datetime) as clock:
            clock.now.return_value = when or datetime.fromisoformat(visit['ends_at'])
            return self.client.post(f"/queue/{visit['id']}/missed", headers=actor or self.staff)

    def test_end_boundary_retry_persistence_patient_separation_and_reports(self):
        store=Store(self.path)
        visit=store.book('patient-ava',self.slot['id'],'missed-boundary')
        end=datetime.fromisoformat(visit['ends_at'])
        self.assertEqual(self.post(visit,end-timedelta(microseconds=1)).status_code,409)
        self.assertEqual(self.post(visit,end).json()['status'],'missed')
        self.assertEqual(self.post(visit,end+timedelta(hours=1)).json()['status'],'missed')
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE booking_id=? AND action='missed'",(visit['id'],)).fetchone()[0],1)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/bookings/{visit['id']}/details",headers=self.patient).json()['visit']['status'],'missed')
        self.assertEqual(reopened.get(f"/bookings/{visit['id']}/details",headers=self.other).status_code,404)
        report=store.daily_report(visit['clinic_date'])
        self.assertEqual((report['visits']['total'],report['visits']['waiting'],report['visits']['missed'],report['visits']['cancelled']),(1,0,1,0))
        doctor=next(row for row in report['visits_by_doctor'] if row['doctor_id']==visit['doctor_id'])
        self.assertEqual(doctor['visits']['missed'],1)
        for key,total in report['visits'].items():
            self.assertEqual(sum(row['visits'][key] for row in report['visits_by_doctor']),total)

    def test_staff_only_missing_and_nonwaiting_rejected(self):
        store=Store(self.path)
        visit=store.book('patient-ava',self.slot['id'],'missed-permissions')
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.post(visit,actor=actor).status_code,403)
        self.assertEqual(self.client.post('/queue/missing/missed',headers=self.staff).status_code,404)
        for status in ('called','completed','cancelled'):
            with store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(status,visit['id']))
            self.assertEqual(self.post(visit).status_code,409)
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='missed'").fetchone()[0],0)

    def test_missed_is_skipped_when_calling_next_and_another_visit_can_be_booked(self):
        store=Store(self.path)
        first=store.book('patient-ava',self.slot['id'],'missed-first')
        second=store.book('patient-noah',self.slot['id'],'still-waiting')
        self.assertEqual(self.post(first).status_code,200)
        called=store.call_next(self.slot['doctor_id'],self.slot['clinic_date'],'staff-demo')
        self.assertEqual(called['id'],second['id'])
        target=next(s for s in store.slots() if s['id']!=self.slot['id'])
        self.assertEqual(store.book('patient-ava',target['id'],'after-missed')['status'],'waiting')
        with self.assertRaises(RuleError):store.complete(first['id'],'staff-demo')

    def test_call_and_missed_race_has_one_winner(self):
        store=Store(self.path)
        visit=store.book('patient-ava',self.slot['id'],'missed-race')
        def run(fn):
            try:return fn()['status']
            except RuleError:return 'conflict'
        with patch('app.store.datetime', wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(visit['ends_at'])
            with ThreadPoolExecutor(max_workers=2) as pool:
                results=list(pool.map(run,[lambda:store.mark_missed(visit['id'],'staff-demo'),lambda:store.call_next(visit['doctor_id'],visit['clinic_date'],'staff-demo')]))
        self.assertEqual(results.count('conflict'),1)
        self.assertTrue('called' in results or 'missed' in results)

    def test_missed_revokes_only_appointment_assessment_link(self):
        store=Store(self.path)
        visit=store.book('patient-ava',self.slot['id'],'missed-linked')
        assessment=store.save_assessment('patient-ava','missed-photo','synthetic-hash',b'synthetic fixture',10,10)
        linked=store.link_assessment(assessment['id'],'patient-ava',visit['id'],'Fictional message','missed-link')
        direct=store.share_assessment(assessment['id'],'patient-ava',visit['doctor_id'],'Direct fictional share','direct-share')
        self.assertEqual(self.post(visit).status_code,200)
        self.assertNotIn(linked['id'],[row['id'] for row in store.shares(visit['doctor_id'])])
        self.assertIn(direct['id'],[row['id'] for row in store.shares(visit['doctor_id'])])
        with store.connect() as db:
            with self.assertRaises(RuleError):store.share_record(db,linked['id'],visit['doctor_id'])

    def test_missed_follow_up_can_be_booked_again(self):
        store=Store(self.path)
        source=store.book('patient-ava',self.slot['id'],'follow-up-origin')
        store.call_next(source['doctor_id'],source['clinic_date'],'staff-demo')
        targets=[s for s in store.slots() if s['doctor_id']==source['doctor_id'] and s['clinic_date']>source['clinic_date']]
        store.recommend_follow_up(source['id'],source['doctor_id'],targets[0]['clinic_date'],'Fictional follow-up')
        old=store.book('patient-ava',targets[0]['id'],'missed-follow-up',follow_up_source=source['id'])
        self.assertEqual(self.post(old).status_code,200)
        new=store.book('patient-ava',targets[1]['id'],'repeat-follow-up',follow_up_source=source['id'])
        self.assertEqual(new['status'],'waiting')
        self.assertEqual(new['follow_up_source_id'],source['id'])


class MissedBookingMigrationTests(unittest.TestCase):
    def legacy(self):
        db=sqlite3.connect(':memory:');db.row_factory=sqlite3.Row
        db.executescript("""PRAGMA foreign_keys=ON;
            CREATE TABLE slots(id TEXT PRIMARY KEY);
            CREATE TABLE bookings(id TEXT PRIMARY KEY,patient_id TEXT NOT NULL,slot_id TEXT NOT NULL REFERENCES slots(id),queue_number INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('waiting','called','completed','cancelled')),created_at TEXT NOT NULL,request_id TEXT NOT NULL,UNIQUE(patient_id,request_id));
            CREATE INDEX booking_slot ON bookings(slot_id,status);
            CREATE TABLE events(id TEXT PRIMARY KEY,booking_id TEXT REFERENCES bookings(id));
            INSERT INTO slots VALUES('s');
            INSERT INTO bookings VALUES('b','p','s',1,'waiting','time','request');
            INSERT INTO events VALUES('e','b');""")
        return db

    def test_legacy_rows_references_index_and_uniqueness_survive_repeated_upgrade(self):
        db=self.legacy()
        before=[tuple(row) for row in db.execute('SELECT * FROM bookings')]
        allow_missed_bookings(db);allow_missed_bookings(db)
        self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM bookings')],before)
        self.assertEqual(db.execute('SELECT booking_id FROM events').fetchone()[0],'b')
        self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertTrue(db.execute("SELECT 1 FROM sqlite_master WHERE name='booking_slot'").fetchone())
        db.execute("UPDATE bookings SET status='missed' WHERE id='b'")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("INSERT INTO bookings VALUES('other','p','s',2,'waiting','time','request')")
        with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE events SET booking_id='missing'")
        db.close()

    def test_invalid_reference_rolls_back_migration_and_restores_foreign_keys(self):
        db=self.legacy()
        db.execute('PRAGMA foreign_keys=OFF');db.execute("UPDATE events SET booking_id='missing'");db.commit();db.execute('PRAGMA foreign_keys=ON')
        with self.assertRaises(RuntimeError):allow_missed_bookings(db)
        self.assertNotIn("'missed'",db.execute("SELECT sql FROM sqlite_master WHERE name='bookings'").fetchone()[0])
        self.assertIsNone(db.execute("SELECT name FROM sqlite_master WHERE name='bookings_with_missed'").fetchone())
        self.assertEqual(db.execute('PRAGMA foreign_keys').fetchone()[0],1)
        self.assertEqual(db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0],1)
        db.close()
