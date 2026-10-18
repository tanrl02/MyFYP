import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone, date
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_unavailability as absences
from test_schedules import ScheduleClock


class AbsenceCancellationTests(unittest.TestCase):
    setUp=absences.UnavailabilityTests.setUp
    absent=absences.UnavailabilityTests.absent
    save=absences.UnavailabilityTests.save
    preview=absences.UnavailabilityTests.preview
    generate=absences.UnavailabilityTests.generate

    def cancel_url(self,item,doctor='doctor-lim'):
        return f"/staff/schedules/{doctor}/unavailability/{item['id']}/cancel"

    def test_restores_open_slots_preserves_closed_history_patterns_and_no_new_slots(self):
        self.save()
        open_slot=self.store.add_slot('doctor-lim',self.week,'12:00',2,'restore-open')
        closed=self.store.add_slot('doctor-lim',self.week,'13:00',2,'restore-closed')
        self.store.close_slot(closed['id'])
        saved=self.absent().json()
        self.assertNotIn(open_slot['id'],{slot['id'] for slot in self.store.slots()})
        before=self.store.schedule_patterns()
        response=self.client.post(self.cancel_url(saved),headers=self.staff)
        self.assertEqual(response.status_code,200)
        cancelled=response.json();self.assertIsNotNone(cancelled['cancelled_at'])
        self.assertEqual({k:v for k,v in cancelled.items() if k!='cancelled_at'},{k:v for k,v in saved.items() if k!='cancelled_at'})
        self.assertEqual(self.client.post(self.cancel_url(saved),headers=self.staff).json(),cancelled)
        public={slot['id'] for slot in self.client.get('/slots').json()}
        self.assertIn(open_slot['id'],public);self.assertNotIn(closed['id'],public)
        managed=next(slot for slot in self.store.managed_slots() if slot['id']==closed['id'])
        self.assertEqual((managed['closed'],managed['unavailable']),(1,False))
        self.assertEqual(self.store.schedule_patterns(),before)
        self.assertEqual(self.store.unavailability('doctor-lim'),[cancelled])
        self.assertEqual(self.store.mine('patient-ava'),[])
        self.assertEqual(TestClient(create_app(self.path)).get(self.url+'/unavailability',headers=self.staff).json(),[cancelled])
        booked=self.store.book('patient-ava',open_slot['id'],'book-restored')
        self.assertEqual(self.client.post(self.cancel_url(saved),headers=self.staff).json(),cancelled)
        self.assertEqual(self.store.mine('patient-ava'),[booked])
        own=self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':self.week}).json()
        self.assertEqual(own['unavailability'],[cancelled])

    def test_roles_scope_and_midnight_boundary_with_historical_retries(self):
        saved=self.absent().json();url=self.cancel_url(saved)
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.post(url,headers=actor).status_code,403)
        self.assertEqual(self.client.post(self.cancel_url(saved,'doctor-anita'),headers=self.staff).status_code,404)
        self.assertEqual(self.client.post(self.url+'/unavailability/missing/cancel',headers=self.staff).status_code,404)
        # 23:59:59 Malaysia on the prior day is allowed; retry is safe after midnight.
        ScheduleClock.instant=datetime.fromisoformat(self.week+'T00:00:00+08:00').astimezone(timezone.utc)-timedelta(seconds=1)
        first=self.client.post(url,headers=self.staff)
        self.assertEqual(first.status_code,200)
        ScheduleClock.instant+=timedelta(seconds=1)
        self.assertEqual(self.client.post(url,headers=self.staff).json(),first.json())
        next_day=(date.fromisoformat(self.week)+timedelta(days=1)).isoformat()
        fresh=self.absent(day=next_day,key='next-day-absence').json()
        ScheduleClock.instant+=timedelta(days=1)
        self.assertEqual(self.client.post(self.cancel_url(fresh),headers=self.staff).status_code,409)
        self.assertIsNone(next(item for item in self.store.unavailability('doctor-lim') if item['id']==fresh['id'])['cancelled_at'])

    def test_readding_date_preserves_history_and_old_retry_never_cancels_replacement(self):
        saved=self.absent().json();url=self.cancel_url(saved)
        cancelled=self.client.post(url,headers=self.staff).json()
        # Retrying creation with its old request returns history; it does not reactivate it.
        self.assertEqual(self.absent().json(),cancelled)
        replacement=self.absent(key='replacement-absence',reason='New fictional absence').json()
        self.assertNotEqual(replacement['id'],saved['id'])
        self.assertEqual(self.client.post(url,headers=self.staff).json(),cancelled)
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM doctor_unavailability').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM doctor_unavailability WHERE cancelled_at IS NULL').fetchone()[0],1)
        self.assertIsNone(replacement['cancelled_at'])

    def test_overlapping_next_day_absence_keeps_overnight_slot_blocked(self):
        overnight=self.store.add_slot('doctor-lim',self.week,'23:30',2,'overnight-cancellation',60)
        first=self.absent().json()
        next_day=(date.fromisoformat(self.week)+timedelta(days=1)).isoformat()
        second=self.absent(day=next_day,key='adjacent-absence').json()
        self.client.post(self.cancel_url(first),headers=self.staff)
        self.assertNotIn(overnight['id'],{slot['id'] for slot in self.store.slots()})
        self.client.post(self.cancel_url(second),headers=self.staff)
        self.assertIn(overnight['id'],{slot['id'] for slot in self.store.slots()})

    def test_stale_week_preview_after_cancellation_requires_review_then_generates_missing_slots(self):
        self.save();absence=self.absent().json();preview=self.preview().json()
        self.assertEqual(preview['unavailable_count'],2)
        self.client.post(self.cancel_url(absence),headers=self.staff)
        self.assertEqual(self.generate(preview).status_code,409)
        new=self.preview().json()
        self.assertEqual((new['new_count'],new['unavailable_count']),(4,0))
        self.assertEqual(self.generate(new,'generation-after-cancel').json()['created_count'],4)

    def test_concurrent_cancellation_has_one_timestamp_and_no_lost_new_absence(self):
        saved=self.absent().json()
        def cancel(_):return self.store.cancel_unavailability('doctor-lim',saved['id'])['cancelled_at']
        with ThreadPoolExecutor(max_workers=4) as pool:stamps=list(pool.map(cancel,range(4)))
        self.assertEqual(len(set(stamps)),1)
        replacement=self.absent(key='concurrent-replacement').json()
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(cancel,range(2)))
        self.assertIsNone(next(item for item in self.store.unavailability('doctor-lim') if item['id']==replacement['id'])['cancelled_at'])

    def test_old_schema_migration_preserves_ids_requests_and_allows_reuse_after_cancel(self):
        saved=self.absent().json()
        with self.store.connect() as db:
            db.execute('DROP TABLE doctor_unavailability')
            db.execute('''CREATE TABLE doctor_unavailability(id TEXT PRIMARY KEY,doctor_id TEXT NOT NULL,clinic_date TEXT NOT NULL,
                reason TEXT NOT NULL,created_at TEXT NOT NULL,request_id TEXT NOT NULL UNIQUE,UNIQUE(doctor_id,clinic_date))''')
            db.execute('INSERT INTO doctor_unavailability VALUES(?,?,?,?,?,?)',
                       (saved['id'],'doctor-lim',self.week,saved['reason'],saved['created_at'],'unavailable-request-one'))
        reopened=Store(self.path)
        self.assertEqual(reopened.unavailability('doctor-lim'),[saved])
        self.assertEqual(reopened.add_unavailability('doctor-lim',self.week,saved['reason'],'unavailable-request-one'),saved)
        reopened.cancel_unavailability('doctor-lim',saved['id'])
        new=reopened.add_unavailability('doctor-lim',self.week,'Replacement','after-migration')
        self.assertNotEqual(new['id'],saved['id'])
        self.assertEqual(len(reopened.unavailability('doctor-lim')),2)
