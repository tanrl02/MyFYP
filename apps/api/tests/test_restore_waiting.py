from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_workflow as workflow


class RestoreWaitingTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def missed(self,store,visit):
        with patch('app.store.datetime',wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(visit['ends_at'])
            return store.mark_missed(visit['id'],'staff-demo')

    def restore(self,visit,actor=None,event=None):
        return self.client.post(f"/queue/{visit['id']}/restore-waiting",headers=actor or self.staff,
            json={'missed_event_id':event or visit['missed_event_id']})

    def test_correction_preserves_visit_queue_and_updates_reports_and_patient(self):
        store=Store(self.path)
        original=store.book('patient-ava',self.slot['id'],'restore-original')
        other=store.book('patient-noah',self.slot['id'],'restore-other')
        missed=self.missed(store,original)
        self.assertEqual(store.daily_report(original['clinic_date'])['visits']['missed'],1)
        response=self.restore(missed);self.assertEqual(response.status_code,200)
        saved=response.json()
        for key in ('id','patient_id','slot_id','queue_number','doctor_id','starts_at','ends_at','created_at'):
            self.assertEqual(saved[key],original[key])
        self.assertEqual(saved['status'],'waiting')
        report=store.daily_report(original['clinic_date'])
        self.assertEqual((report['visits']['total'],report['visits']['waiting'],report['visits']['missed']),(2,2,0))
        doctor=next(row for row in report['visits_by_doctor'] if row['doctor_id']==original['doctor_id'])
        self.assertEqual(doctor['visits'],report['visits'])
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/bookings/{saved['id']}/details",headers=self.patient).json()['visit']['status'],'waiting')
        self.assertEqual(reopened.get(f"/bookings/{saved['id']}/details",headers=self.other).status_code,404)
        self.assertEqual(store.call_next(saved['doctor_id'],saved['clinic_date'],'staff-demo')['id'],saved['id'])
        self.assertEqual(other['queue_number'],2)

    def test_replay_audit_and_staff_only_payload_validation(self):
        store=Store(self.path)
        visit=self.missed(store,store.book('patient-ava',self.slot['id'],'restore-roles'))
        for actor in (self.patient,self.other,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'doctor-anita'}):
            self.assertEqual(self.restore(visit,actor=actor).status_code,403)
        url=f"/queue/{visit['id']}/restore-waiting"
        for payload in ({},{'missed_event_id':''},{'missed_event_id':'x'*101},{'missed_event_id':visit['missed_event_id'],'extra':True}):
            self.assertEqual(self.client.post(url,headers=self.staff,json=payload).status_code,422)
        self.assertEqual(self.restore(visit).status_code,200)
        self.assertEqual(self.restore(visit).status_code,200)
        with store.connect() as db:
            rows=db.execute("SELECT * FROM events WHERE booking_id=? AND action='missed-restored'",(visit['id'],)).fetchall()
            self.assertEqual(len(rows),1);self.assertEqual(rows[0]['actor_id'],'staff-demo')
            link=db.execute('SELECT * FROM missed_restorations WHERE missed_event_id=?',(visit['missed_event_id'],)).fetchone()
            self.assertEqual(link['restored_event_id'],rows[0]['id'])
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_stale_episode_cannot_restore_a_later_missed_decision(self):
        store=Store(self.path)
        first=self.missed(store,store.book('patient-ava',self.slot['id'],'restore-stale'))
        self.assertEqual(self.restore(first).status_code,200)
        second=self.missed(store,first)
        self.assertNotEqual(first['missed_event_id'],second['missed_event_id'])
        self.assertEqual(self.restore(first).status_code,409)
        self.assertEqual(self.restore(second).status_code,200)
        self.assertEqual(self.restore(first).status_code,409)

    def test_wrong_booking_event_and_nonmissed_states_rejected(self):
        store=Store(self.path)
        missed=self.missed(store,store.book('patient-ava',self.slot['id'],'restore-missed'))
        waiting=store.book('patient-noah',self.slot['id'],'restore-waiting')
        self.assertEqual(self.restore(waiting,event=missed['missed_event_id']).status_code,409)
        self.assertEqual(self.restore(missed,event='unknown-event').status_code,409)
        for status in ('waiting','called','completed','cancelled'):
            with store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(status,missed['id']))
            self.assertEqual(self.restore(missed).status_code,409)
        self.assertEqual(self.client.post('/queue/missing/restore-waiting',headers=self.staff,json={'missed_event_id':missed['missed_event_id']}).status_code,404)

    def test_concurrent_duplicate_restores_create_one_event(self):
        store=Store(self.path)
        visit=self.missed(store,store.book('patient-ava',self.slot['id'],'restore-race'))
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:store.restore_waiting(visit['id'],visit['missed_event_id'],'staff-demo'),range(2)))
        self.assertTrue(all(row['status']=='waiting' for row in results))
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='missed-restored'").fetchone()[0],1)

    def test_revoked_assessment_access_stays_revoked(self):
        store=Store(self.path)
        visit=store.book('patient-ava',self.slot['id'],'restore-photo')
        photo=store.save_assessment('patient-ava','restore-photo-key','synthetic-hash',b'synthetic',10,10)
        linked=store.link_assessment(photo['id'],'patient-ava',visit['id'],'Fictional message','restore-link')
        missed=self.missed(store,visit)
        with store.connect() as db:revoked=db.execute('SELECT revoked_at FROM assessment_shares WHERE id=?',(linked['id'],)).fetchone()[0]
        self.assertIsNotNone(revoked)
        self.assertEqual(self.restore(missed).status_code,200)
        self.assertEqual(store.shares(visit['doctor_id']),[])
        with store.connect() as db:self.assertEqual(db.execute('SELECT revoked_at FROM assessment_shares WHERE id=?',(linked['id'],)).fetchone()[0],revoked)

    def test_replacement_follow_up_blocks_restoring_old_follow_up(self):
        store=Store(self.path)
        source=store.book('patient-ava',self.slot['id'],'restore-follow-source')
        store.call_next(source['doctor_id'],source['clinic_date'],'staff-demo')
        slots=[s for s in store.slots() if s['doctor_id']==source['doctor_id'] and s['clinic_date']>source['clinic_date']]
        store.recommend_follow_up(source['id'],source['doctor_id'],slots[0]['clinic_date'],'Fictional follow-up')
        old=self.missed(store,store.book('patient-ava',slots[0]['id'],'restore-follow-old',follow_up_source=source['id']))
        new=store.book('patient-ava',slots[1]['id'],'restore-follow-new',follow_up_source=source['id'])
        self.assertEqual(self.restore(old).status_code,409)
        store.cancel(new['id'],'patient-ava')
        self.assertEqual(self.restore(old).status_code,200)
        with store.connect() as db:
            active=store.follow_up_record(db,source['id'])
            self.assertEqual(active['booked_visit']['id'],old['id'])
        with self.assertRaises(RuleError):
            store.book('patient-ava',slots[2]['id'],'restore-follow-duplicate',follow_up_source=source['id'])
