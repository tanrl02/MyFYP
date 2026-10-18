import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store
import test_schedules as schedules


class UnavailabilityTests(unittest.TestCase):
    setUp=schedules.ScheduleTests.setUp
    save=schedules.ScheduleTests.save
    preview=schedules.ScheduleTests.preview
    generate=schedules.ScheduleTests.generate

    def absent(self,day=None,doctor='doctor-lim',reason='Fictional absence',key='unavailable-request-one'):
        return self.client.post(f'/staff/schedules/{doctor}/unavailability',headers=self.staff,json={'clinic_date':day or self.week,'reason':reason,'request_id':key})

    def test_roles_validation_retries_and_private_reason(self):
        route=self.url+'/unavailability'
        body={'clinic_date':self.week,'reason':'Private fictional absence reason','request_id':'private-absence-request'}
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.get(route,headers=actor).status_code,403)
            self.assertEqual(self.client.post(route,headers=actor,json=body).status_code,403)
        for changes in ({'clinic_date':'2035-01-01'},{'reason':' '},{'reason':'x'*301},{'request_id':'x'}):
            self.assertEqual(self.client.post(route,headers=self.staff,json=body|changes).status_code,422)
        result=self.client.post(route,headers=self.staff,json=body)
        self.assertEqual(result.status_code,201)
        saved=result.json()
        self.assertEqual(self.client.post(route,headers=self.staff,json=body).json(),saved)
        self.assertEqual(self.absent(key='another-absence-request').status_code,409)
        self.assertEqual(self.client.post(route,headers=self.staff,json=body|{'reason':'Changed'}).status_code,409)
        self.assertEqual(self.client.get(route,headers=self.staff).json(),[saved])
        self.assertEqual(TestClient(create_app(self.path)).get(route,headers=self.staff).json(),[saved])
        own=self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':self.week}).json()
        self.assertEqual(own['unavailability'],[saved])
        self.assertEqual(self.client.get('/doctor/schedule',headers=self.anita,params={'week_start':self.week}).json()['unavailability'],[])
        self.assertNotIn(body['reason'],self.client.get('/slots').text)

    def test_existing_empty_slots_hidden_and_all_booking_channels_denied(self):
        slot=self.store.add_slot('doctor-lim',self.week,'14:00',2,'empty-blocked-slot')
        other=self.store.add_slot('doctor-anita',self.week,'14:00',2,'other-doctor-slot')
        self.assertEqual(self.absent().status_code,201)
        self.assertNotIn(slot['id'],{item['id'] for item in self.client.get('/slots').json()})
        self.assertIn(other['id'],{item['id'] for item in self.client.get('/slots').json()})
        managed=next(item for item in self.store.managed_slots() if item['id']==slot['id'])
        self.assertTrue(managed['unavailable']);self.assertEqual(managed['closed'],0)
        body={'slot_id':slot['id'],'request_id':'blocked-patient-book'}
        self.assertEqual(self.client.post('/bookings',headers=self.patient,json=body).status_code,409)
        self.assertEqual(self.client.post('/counter-bookings',headers=self.staff,json=body|{'patient_id':'patient-ava'}).status_code,409)
        with self.assertRaises(RuleError):self.store.add_slot('doctor-lim',self.week,'16:00',2,'blocked-new-slot')
        self.assertEqual(self.store.mine('patient-ava'),[])

    def test_booked_dates_refused_cancelled_history_preserved_and_overnight_edges(self):
        slot=self.store.add_slot('doctor-lim',self.week,'14:00',2,'booked-block-slot')
        visit=self.store.book('patient-ava',slot['id'],'book-before-block')
        for state in ('waiting','called','completed'):
            with self.store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(state,visit['id']))
            self.assertEqual(self.absent().status_code,409)
        with self.store.connect() as db:db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(visit['id'],))
        self.assertEqual(self.absent().status_code,201)
        self.assertEqual(self.store.mine('patient-ava')[0]['status'],'cancelled')
        sunday=(date.fromisoformat(self.week)-timedelta(days=1)).isoformat()
        with self.assertRaises(RuleError):self.store.add_slot('doctor-lim',sunday,'23:45',2,'overnight-blocked',30)
        # A slot ending exactly at midnight is outside the unavailable day.
        edge=self.store.add_slot('doctor-lim',sunday,'23:30',2,'midnight-touch',30)
        self.assertIn(edge['id'],{item['id'] for item in self.store.slots()})
        next_day=(date.fromisoformat(self.week)+timedelta(days=1)).isoformat()
        self.assertIsNotNone(self.store.add_slot('doctor-lim',next_day,'00:00',2,'after-absence',30))

    def test_reschedule_denial_preserves_original_and_follow_up_booking_checks(self):
        blocked=self.store.add_slot('doctor-lim',self.week,'14:00',2,'target-blocked')
        source=self.store.book('patient-ava',self.slot['id'],'source-before-block')
        self.absent()
        for actor in ('patient-ava','staff-demo'):
            with self.assertRaises(RuleError):self.store.reschedule(source['id'],actor,blocked['id'],'reschedule-'+actor)
        self.assertEqual(self.store.mine('patient-ava')[0],source)
        # Follow-up booking reuses the same serialized availability check.
        lim_slot=next(item for item in self.store.slots() if item['doctor_id']=='doctor-lim')
        visit=self.store.book('patient-noah',lim_slot['id'],'follow-up-block-source')
        with self.store.connect() as db:db.execute("UPDATE bookings SET status='called' WHERE id=?",(visit['id'],))
        self.store.recommend_follow_up(visit['id'],'doctor-lim',self.week,'Fictional follow-up')
        with self.assertRaises(RuleError):self.store.book('patient-noah',blocked['id'],'blocked-follow-up',follow_up_source=visit['id'])

    def test_week_generation_skips_absent_days_and_stale_preview_is_rejected(self):
        self.save();before=self.preview().json()
        self.assertEqual(self.absent().status_code,201)
        self.assertEqual(self.generate(before).status_code,409)
        planned=self.preview().json()
        self.assertEqual((planned['new_count'],planned['unavailable_count'],planned['conflict_count']),(2,2,0))
        generated=self.generate(planned).json()
        self.assertEqual((generated['created_count'],generated['unavailable_count'],len(generated['slot_ids'])),(2,2,2))
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM slots WHERE doctor_id=? AND clinic_date=?',('doctor-lim',self.week)).fetchone()[0],0)

    def test_absence_racing_booking_serializes(self):
        slot=self.store.add_slot('doctor-lim',self.week,'14:00',2,'race-book-slot')
        def action(kind):
            try:
                if kind=='absence':self.store.add_unavailability('doctor-lim',self.week,'Race absence','race-absence-key')
                else:self.store.book('patient-ava',slot['id'],'racing-booking')
                return kind
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(action,['absence','booking']))
        self.assertEqual(results.count(409),1)
        if 'absence' in results:self.assertEqual(self.store.mine('patient-ava'),[])
        else:self.assertEqual(self.store.unavailability('doctor-lim'),[])

    def test_previous_day_overnight_booking_blocks_absence_until_cancelled(self):
        sunday=(date.fromisoformat(self.week)-timedelta(days=1)).isoformat()
        slot=self.store.add_slot('doctor-lim',sunday,'23:45',2,'overnight-before-absence',30)
        visit=self.store.book('patient-ava',slot['id'],'overnight-booked')
        self.assertEqual(self.absent().status_code,409)
        self.assertEqual(self.store.mine('patient-ava')[0],visit)
        self.store.cancel(visit['id'],'patient-ava')
        self.assertEqual(self.absent().status_code,201)
        self.assertNotIn(slot['id'],{item['id'] for item in self.store.slots()})

    def test_same_request_concurrency_and_seed_restart_respect_absence(self):
        tomorrow='2035-01-02'
        def save(_):return self.store.add_unavailability('doctor-lim',tomorrow,'Fictional day off','same-absence')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(len(set(pool.map(save,range(4)))),1)
        with self.store.connect() as db:
            db.execute('DELETE FROM slots WHERE doctor_id=? AND clinic_date=?',('doctor-lim',tomorrow))
        reopened=Store(self.path)
        self.assertFalse(any(slot['doctor_id']=='doctor-lim' and slot['clinic_date']==tomorrow for slot in reopened.managed_slots()))
