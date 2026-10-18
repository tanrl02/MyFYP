import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_unavailability as absences


class PartialAbsenceTests(unittest.TestCase):
    setUp=absences.UnavailabilityTests.setUp
    save=absences.UnavailabilityTests.save
    preview=absences.UnavailabilityTests.preview
    generate=absences.UnavailabilityTests.generate

    def block(self,start="14:00",end="15:00",key="partial-absence-one",**changes):
        body=dict(clinic_date=self.week,reason="Private fictional meeting",request_id=key,start_time=start,end_time=end)
        return self.client.post(self.url+"/unavailability",headers=self.staff,json=body|changes)

    def test_validation_role_and_private_persistent_time_range(self):
        for start,end in ((None,"15:00"),("14:00",None),("15:00","14:00"),("14:00","14:00"),("24:00","25:00"),("14:00:01","15:00"),("9:00","10:00"),("1\u0661:00","15:00")):
            self.assertEqual(self.block(start,end).status_code,422,(start,end))
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.post(self.url+"/unavailability",headers=actor,json=dict(clinic_date=self.week,reason="Private",request_id="partial-denied",start_time="14:00",end_time="15:00")).status_code,403)
        saved=self.block().json()
        self.assertEqual((saved["start_time"],saved["end_time"]),("14:00","15:00"))
        self.assertEqual(self.block().json(),saved)
        self.assertEqual(self.block(end="15:30").status_code,409)
        restored=TestClient(create_app(self.path))
        self.assertEqual(restored.get(self.url+"/unavailability",headers=self.staff).json(),[saved])
        own=self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':self.week}).json()
        self.assertEqual(own['unavailability'],[saved])
        self.assertEqual(self.client.get('/doctor/schedule',headers=self.anita,params={'week_start':self.week}).json()['unavailability'],[])
        self.assertNotIn(saved['reason'],self.client.get('/slots').text)

    def test_half_open_overlap_filters_slots_and_allows_separate_periods(self):
        times=("13:30","14:00","14:30","15:00","16:00")
        slots={time:self.store.add_slot('doctor-lim',self.week,time,2,'partial-slot-'+time,30) for time in times}
        self.assertEqual(self.block().status_code,201)
        public={slot['id'] for slot in self.store.slots()}
        for time in times:
            self.assertEqual(slots[time]['id'] in public,time in ("13:30","15:00","16:00"),time)
        self.assertEqual(self.block("15:00","15:30",key="adjacent-period").status_code,201)
        self.assertEqual(self.block("16:00","17:00",key="separate-period").status_code,201)
        for start,end in (("13:59","14:01"),("14:30","16:30"),("13:00","18:00"),(None,None)):
            self.assertEqual(self.block(start,end,key="overlap-period").status_code,409)
        with self.assertRaises(RuleError):self.store.add_slot('doctor-lim',self.week,'14:15',2,'blocked-slot')
        self.store.add_slot('doctor-lim',self.week,'17:00',2,'outside-block')
        self.assertNotIn('Private fictional meeting',self.client.get('/slots').text)

    def test_booked_slot_protection_uses_entire_slot_and_keeps_outside_booking(self):
        before=self.store.add_slot('doctor-lim',self.week,'13:30',2,'booked-before')
        outside=self.store.book('patient-ava',before['id'],'book-outside')
        crossing=self.store.add_slot('doctor-lim',self.week,'14:45',2,'booked-crossing')
        visit=self.store.book('patient-noah',crossing['id'],'book-crossing')
        for state in ('waiting','called','completed'):
            with self.store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(state,visit['id']))
            self.assertEqual(self.block().status_code,409)
        with self.store.connect() as db:db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(visit['id'],))
        self.assertEqual(self.block().status_code,201)
        self.assertEqual(self.store.mine('patient-ava'),[outside])
        body={'slot_id':crossing['id'],'request_id':'blocked-partial-booking'}
        self.assertEqual(self.client.post('/bookings',headers=self.patient,json=body).status_code,409)
        self.assertEqual(self.client.post('/counter-bookings',headers=self.staff,json=body|{'patient_id':'patient-ava'}).status_code,409)
        self.assertEqual(len(self.store.mine('patient-ava')),1)

    def test_midnight_overnight_slot_and_full_day_guard(self):
        prior=(date.fromisoformat(self.week)-timedelta(days=1)).isoformat()
        slot=self.store.add_slot('doctor-lim',prior,'23:45',2,'prior-night',30)
        first=self.block('00:00','00:15').json()
        self.assertNotIn(slot['id'],{item['id'] for item in self.store.slots()})
        self.client.post(self.url+'/unavailability/'+first['id']+'/cancel',headers=self.staff)
        self.assertIn(slot['id'],{item['id'] for item in self.store.slots()})
        self.assertEqual(self.block(None,None,key='full-day-block').status_code,201)
        self.assertEqual(self.block(key='over-full-day').status_code,409)

    def test_cancel_one_period_retains_other_closed_slots_history_and_retry(self):
        slots=[self.store.add_slot('doctor-lim',self.week,time,2,'cancel-partial-'+time) for time in ('14:00','14:30','16:00')]
        self.store.close_slot(slots[1]['id'])
        first=self.block().json();second=self.block('16:00','17:00',key='second-period').json()
        result=self.client.post(self.url+'/unavailability/'+first['id']+'/cancel',headers=self.staff).json()
        self.assertIsNotNone(result['cancelled_at'])
        self.assertEqual((result['start_time'],result['end_time']),('14:00','15:00'))
        public={item['id'] for item in self.store.slots()}
        self.assertIn(slots[0]['id'],public)
        self.assertNotIn(slots[1]['id'],public);self.assertNotIn(slots[2]['id'],public)
        replacement=self.block(key='replacement-period').json()
        self.assertNotEqual(first['id'],replacement['id'])
        self.assertEqual(self.block().json(),result)
        self.client.post(self.url+'/unavailability/'+first['id']+'/cancel',headers=self.staff)
        active=[item['id'] for item in self.store.unavailability('doctor-lim') if not item['cancelled_at']]
        self.assertCountEqual(active,[second['id'],replacement['id']])

    def test_weekly_preview_only_skips_overlaps_and_stale_review_is_rejected(self):
        self.save(start_time='13:00',end_time='16:00')
        old=self.preview().json()
        block=self.block().json()
        self.assertEqual(self.generate(old).status_code,409)
        current=self.preview().json()
        self.assertEqual(current['unavailable_count'],2)
        self.assertEqual(current['new_count'],10)
        self.assertEqual(self.generate(current).status_code,201)
        self.client.post(self.url+'/unavailability/'+block['id']+'/cancel',headers=self.staff)
        fresh=self.preview().json()
        self.assertEqual(fresh['unavailable_count'],0)
        self.assertEqual(fresh['new_count'],2)

    def test_concurrent_overlapping_creation_and_disjoint_periods(self):
        def create(index):
            try:return self.store.add_unavailability('doctor-lim',self.week,'Meeting','partial-concurrent-'+str(index),'14:00','15:00')['id']
            except RuleError:return None
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(create,range(4)))
        self.assertEqual(len([value for value in results if value]),1)
        self.assertEqual(self.block('15:00','16:00',key='after-concurrent').status_code,201)

    def test_cancelled_schema_migration_retains_all_values_as_full_day(self):
        # Simulate the immediately preceding schema and its active-date unique index.
        with self.store.connect() as db:
            db.execute('DROP TABLE doctor_unavailability')
            db.execute('CREATE TABLE doctor_unavailability(id TEXT PRIMARY KEY,doctor_id TEXT NOT NULL,clinic_date TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,cancelled_at TEXT)')
            db.execute('CREATE UNIQUE INDEX active_doctor_unavailability ON doctor_unavailability(doctor_id,clinic_date) WHERE cancelled_at IS NULL')
            db.execute('INSERT INTO doctor_unavailability VALUES(?,?,?,?,?,?,?)',('legacy-active','doctor-lim',self.week,'Original reason','2035-01-01T00:00:00+00:00','legacy-request',None))
            db.execute('INSERT INTO doctor_unavailability VALUES(?,?,?,?,?,?,?)',('legacy-cancelled','doctor-lim',self.week,'Old reason','2034-12-01T00:00:00+00:00','legacy-cancelled-request','2034-12-02T00:00:00+00:00'))
        restored=Store(self.path)
        rows=restored.unavailability('doctor-lim')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(item['start_time'] is None and item['end_time'] is None for item in rows))
        self.assertEqual(next(item for item in rows if item['id']=='legacy-active')['reason'],'Original reason')
        restored.cancel_unavailability('doctor-lim','legacy-active')
        first=restored.add_unavailability('doctor-lim',self.week,'New period','migration-partial-one','14:00','15:00')
        second=restored.add_unavailability('doctor-lim',self.week,'Other period','migration-partial-two','16:00','17:00')
        self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(len(Store(self.path).unavailability('doctor-lim')),4)
