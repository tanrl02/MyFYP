from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import unittest
import test_workflow as workflow

class RescheduleTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book
    def move(self,old,target,actor=None,key='reschedule-request'):
        return self.client.post(f"/bookings/{old['id']}/reschedule",headers=actor or self.patient,
            json={'slot_id':target['id'],'request_id':key})
    def target(self,same=True):
        return next(s for s in self.client.get('/slots').json() if s['id']!=self.slot['id'] and (s['doctor_id']==self.slot['doctor_id'])==same)

    def test_atomic_shared_history_retry_reopen_and_queue(self):
        old=self.book().json();target=self.target()
        response=self.move(old,target,self.staff);self.assertEqual(response.status_code,200)
        new=response.json();self.assertNotEqual(new['id'],old['id'])
        self.assertGreater(new['queue_number'],old['queue_number'])
        self.assertEqual(self.move(old,target,self.staff).json()['id'],new['id'])
        self.assertEqual(self.move(old,self.target(False),self.staff).status_code,409)
        records=self.client.get('/bookings',headers=self.patient).json()
        prior=next(b for b in records if b['id']==old['id'])
        self.assertEqual(prior['status'],'cancelled');self.assertEqual(prior['rescheduled_to_id'],new['id'])
        self.assertEqual(self.client.get('/bookings',headers=self.other).json(),[])
        self.assertEqual(TestClient(create_app(self.path)).get('/bookings',headers=self.patient).json(),records)
        availability={s['id']:s['available'] for s in self.client.get('/slots').json()}
        self.assertEqual(availability[old['slot_id']],2);self.assertEqual(availability[target['id']],1)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action LIKE 'rescheduled-%'").fetchone()[0],2)

    def test_denials_and_failed_moves_preserve_original(self):
        old=self.book().json();target=self.target()
        self.assertEqual(self.move(old,target,self.other).status_code,403)
        self.assertEqual(self.move(old,target,{'X-Demo-Actor':'doctor-lim'}).status_code,403)
        self.assertEqual(self.move(old,target,key='short').status_code,422)
        self.assertEqual(self.move(old,{'id':old['slot_id']}).status_code,409)
        self.assertEqual(self.move(old,{'id':'missing'}).status_code,404)
        store=Store(self.path)
        store.book('patient-ava',target['id'],'other-booking')
        self.assertEqual(self.move(old,target).status_code,409)
        other=self.target(False)
        with store.connect() as db:db.execute('UPDATE slots SET capacity=1 WHERE id=?',(other['id'],))
        store.book('patient-noah',other['id'],'fill-target')
        self.assertEqual(self.move(old,other).status_code,409)
        with store.connect() as db:
            self.assertEqual(store.record(db,old['id'])['status'],'waiting')
            db.execute("UPDATE bookings SET status='called' WHERE id=?",(old['id'],))
        self.assertEqual(self.move(old,target).status_code,409)
        with store.connect() as db:
            db.execute("UPDATE bookings SET status='waiting' WHERE id=?",(old['id'],))
            db.execute('UPDATE slots SET starts_at=? WHERE id=?',((datetime.now(timezone.utc)-timedelta(days=1)).isoformat(),old['slot_id']))
        self.assertEqual(self.move(old,target).status_code,409)

    def test_consent_follows_same_doctor_revokes_changed_doctor_only(self):
        store=Store(self.path);old=self.book().json()
        image=store.save_assessment('patient-ava','assessment-key','hash',b'photo',32,32)
        linked=store.link_assessment(image['id'],'patient-ava',old['id'],'fictional','linked-request')
        direct=store.share_assessment(image['id'],'patient-ava',old['doctor_id'],'fictional','direct-request')
        moved=self.move(old,self.target()).json()
        self.assertEqual(store.shared_assessment(linked['id'],old['doctor_id'])['booking_id'],moved['id'])
        changed=self.move(moved,self.target(False),key='change-doctor-key').json()
        self.assertNotEqual(changed['doctor_id'],old['doctor_id'])
        with self.assertRaises(RuleError):store.shared_assessment(linked['id'],old['doctor_id'])
        self.assertIsNone(store.shared_assessment(direct['id'],old['doctor_id'])['revoked_at'])
        self.assertTrue(next(s for s in store.shares('patient-ava') if s['id']==linked['id'])['revoked_at'])
        self.assertEqual(store.shares(changed['doctor_id']),[])

    def test_concurrent_retries_and_competing_move_keep_capacity(self):
        store=Store(self.path);old=self.book().json();target=self.target()
        def move(_):return store.reschedule(old['id'],'patient-ava',target['id'],'same-move-key')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(len(set(pool.map(move,range(4)))),1)
        replacement=next(b for b in store.mine('patient-ava') if b['status']=='waiting')
        next_target=self.target(False)
        with store.connect() as db:db.execute('UPDATE slots SET capacity=1 WHERE id=?',(next_target['id'],))
        def compete(patient):
            try:
                if patient=='patient-ava':store.reschedule(replacement['id'],patient,next_target['id'],'another-move')
                else:store.book(patient,next_target['id'],'competing-book')
                return 'saved'
            except RuleError:return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertCountEqual(list(pool.map(compete,['patient-ava','patient-noah'])),['saved','rejected'])
        self.assertEqual(next(s for s in store.slots() if s['id']==next_target['id'])['available'],0)
