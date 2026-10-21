from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_workflow as workflow


class PatientOverlapTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def slot_at(self, doctor, time, duration=30):
        day=(datetime.now(timezone(timedelta(hours=8)))+timedelta(days=4)).date().isoformat()
        return Store(self.path).add_slot(doctor,day,time,2,f'overlap-{doctor}-{time}-{duration}',duration)

    def submit(self, slot, staff=False, key='overlap-attempt'):
        body={'slot_id':slot['id'],'request_id':key}
        if staff:body['patient_id']='patient-ava'
        return self.client.post('/counter-bookings' if staff else '/bookings',
                                headers=self.staff if staff else self.patient,json=body)

    def test_patient_counter_rejection_is_atomic_private_and_other_patient_can_book(self):
        first=self.slot_at('doctor-lim','13:30',60)
        target=self.slot_at('doctor-anita','14:00')
        saved=self.submit(first,key='overlap-original').json()
        store=Store(self.path)
        for staff in (False,True):
            response=self.submit(target,staff)
            self.assertEqual(response.status_code,409)
            self.assertIn('overlaps this time',response.json()['detail'])
            self.assertNotIn(saved['id'],response.text)
            self.assertEqual(store.mine('patient-ava'),[saved])
        self.assertEqual(self.submit(first,key='overlap-original').json()['id'],saved['id'])
        self.assertEqual(self.client.post('/bookings',headers=self.other,
            json={'slot_id':target['id'],'request_id':'other-patient-overlap'}).status_code,201)
        self.assertEqual(TestClient(create_app(self.path)).get('/bookings',headers=self.patient).json(),[saved])
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],2)

    def test_partial_contained_containing_and_equal_intervals_rejected(self):
        for time,duration in [('13:15',30),('14:15',30),('13:45',15),('13:00',120),('13:30',60)]:
            with self.subTest(time=time,duration=duration):
                self.setUp()
                first=self.slot_at('doctor-lim','13:30',60)
                target=self.slot_at('doctor-anita',time,duration)
                self.submit(first,key='overlap-shape-original')
                self.assertEqual(self.submit(target).status_code,409)

    def test_adjacent_intervals_and_different_date_allowed_with_timezone_normalisation(self):
        first=self.slot_at('doctor-lim','13:30',60)
        before=self.slot_at('doctor-anita','13:00')
        after=self.slot_at('doctor-anita','14:30')
        store=Store(self.path)
        # An equivalent UTC timestamp must compare the same as Malaysia time.
        with store.connect() as db:
            db.execute('UPDATE slots SET starts_at=? WHERE id=?',
                (datetime.fromisoformat(first['starts_at']).astimezone(timezone.utc).isoformat(),first['id']))
        for index,slot in enumerate((first,before,after)):
            self.assertEqual(self.submit(slot,key=f'adjacent-booking-{index}').status_code,201)
        target=self.slot_at('doctor-lim','15:00')
        with store.connect() as db:
            day=(datetime.fromisoformat(first['starts_at'])+timedelta(days=1))
            db.execute('UPDATE slots SET starts_at=?,clinic_date=? WHERE id=?',
                (day.isoformat(),day.date().isoformat(),target['id']))
        self.assertEqual(self.submit(target,key='different-day-booking').status_code,201)
        overlap=self.slot_at('doctor-anita','13:30',60)
        self.assertEqual(self.submit(overlap,key='utc-overlap-denied').status_code,409)

    def test_only_waiting_and_called_block(self):
        for status in ('waiting','called','completed','missed','cancelled'):
            with self.subTest(status=status):
                self.setUp()
                first=self.slot_at('doctor-lim','13:30',60)
                target=self.slot_at('doctor-anita','14:00')
                saved=self.submit(first,key='status-original').json()
                with Store(self.path).connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(status,saved['id']))
                self.assertEqual(self.submit(target).status_code,409 if status in ('waiting','called') else 201)

    def test_reschedule_rejects_other_visit_but_excludes_original_and_retries(self):
        store=Store(self.path)
        blocker=store.book('patient-ava',self.slot_at('doctor-lim','13:30',60)['id'],'reschedule-blocker')
        old=store.book('patient-ava',self.slot_at('doctor-lim','10:00',60)['id'],'reschedule-original')
        target=self.slot_at('doctor-anita','14:00')
        before=store.mine('patient-ava')
        for actor in (self.patient,self.staff):
            response=self.client.post(f"/bookings/{old['id']}/reschedule",headers=actor,
                json={'slot_id':target['id'],'request_id':'conflicting-move'})
            self.assertEqual(response.status_code,409)
            self.assertEqual(store.mine('patient-ava'),before)
        safe=self.slot_at('doctor-anita','10:30')
        moved=store.reschedule(old['id'],'patient-ava',safe['id'],'safe-overlapping-original')
        self.assertEqual(store.reschedule(old['id'],'patient-ava',safe['id'],'safe-overlapping-original')['id'],moved['id'])
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM reschedules').fetchone()[0],1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action LIKE 'rescheduled-%'").fetchone()[0],2)
        self.assertEqual(next(v for v in store.mine('patient-ava') if v['id']==blocker['id']),blocker)

    def test_concurrent_different_slot_bookings_only_one_succeeds(self):
        slots=[self.slot_at('doctor-lim','13:30',60),self.slot_at('doctor-anita','14:00')]
        store=Store(self.path)
        def book(index):
            try:return store.book('patient-ava',slots[index]['id'],f'competing-overlap-{index}')['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(book,range(2)))
        self.assertEqual(results.count(409),1)
        self.assertEqual(len(store.mine('patient-ava')),1)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)

    def test_concurrent_reschedule_and_booking_cannot_create_overlap(self):
        store=Store(self.path)
        old=store.book('patient-ava',self.slot_at('doctor-lim','10:00')['id'],'race-old-visit')
        targets=[self.slot_at('doctor-lim','13:30',60),self.slot_at('doctor-anita','14:00')]
        def attempt(index):
            try:
                if index==0:store.reschedule(old['id'],'staff-demo',targets[0]['id'],'race-overlap-move')
                else:store.book('patient-ava',targets[1]['id'],'race-overlap-counter',created_by='staff-demo')
                return 'saved'
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,range(2)))
        self.assertCountEqual(results,['saved',409])
        records=store.mine('patient-ava')
        self.assertEqual(sum(v['status']=='waiting' and v['slot_id'] in [s['id'] for s in targets] for v in records),1)
        self.assertEqual(next(v for v in records if v['id']==old['id'])['status'],'cancelled' if results[0]=='saved' else 'waiting')

    def test_restoring_missed_visit_cannot_reintroduce_conflict(self):
        store=Store(self.path)
        original=store.book('patient-ava',self.slot_at('doctor-lim','13:30',60)['id'],'restore-overlap-original')
        with patch('app.store.datetime',wraps=datetime) as clock:
            clock.now.return_value=datetime.fromisoformat(original['ends_at'])
            missed=store.mark_missed(original['id'],'staff-demo')
        replacement=store.book('patient-ava',self.slot_at('doctor-anita','14:00')['id'],'restore-overlap-blocker')
        with self.assertRaisesRegex(RuleError,'overlaps this time'):
            store.restore_waiting(missed['id'],missed['missed_event_id'],'staff-demo')
        with store.connect() as db:
            self.assertEqual(store.record(db,original['id'])['status'],'missed')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM missed_restorations').fetchone()[0],0)
        store.cancel(replacement['id'],'patient-ava')
        self.assertEqual(store.restore_waiting(missed['id'],missed['missed_event_id'],'staff-demo')['id'],original['id'])

    def test_follow_up_booking_uses_same_overlap_rule(self):
        store=Store(self.path)
        source=store.book('patient-ava',self.slot['id'],'overlap-follow-up-source')
        with store.connect() as db:db.execute("UPDATE bookings SET status='completed' WHERE id=?",(source['id'],))
        target=self.slot_at(source['doctor_id'],'14:00')
        other='doctor-anita' if source['doctor_id']=='doctor-lim' else 'doctor-lim'
        blocker=store.book('patient-ava',self.slot_at(other,'13:30',60)['id'],'overlap-follow-up-blocker')
        store.recommend_follow_up(source['id'],source['doctor_id'],target['clinic_date'],'Fictional follow-up.')
        response=self.client.post(f"/visits/{source['id']}/follow-up/book",headers=self.patient,
            json={'slot_id':target['id'],'request_id':'overlap-follow-up-request'})
        self.assertEqual(response.status_code,409)
        self.assertIn('overlaps this time',response.json()['detail'])
        store.cancel(blocker['id'],'patient-ava')
        saved=self.client.post(f"/visits/{source['id']}/follow-up/book",headers=self.patient,
            json={'slot_id':target['id'],'request_id':'overlap-follow-up-request'})
        self.assertEqual(saved.status_code,201)
        self.assertEqual(saved.json()['follow_up_source_id'],source['id'])
