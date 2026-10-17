import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
from app.store import Store,RuleError
import test_workflow as workflow

class SlotDurationTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    def day(self,days=4):return (datetime.now(timezone(timedelta(hours=8)))+timedelta(days=days)).date().isoformat()
    def add(self,time='13:30',duration=30,doctor='doctor-lim',key=None,day=None):
        return self.client.post('/staff/slots',headers=self.staff,json={'doctor_id':doctor,'clinic_date':day or self.day(),
            'time':time,'capacity':2,'duration_minutes':duration,'request_id':key or f'duration-{doctor}-{time}-{duration}'})

    def test_overlap_containment_adjacency_and_other_doctor(self):
        first=self.add(duration=60).json()
        self.assertTrue(first['ends_at'].endswith('14:30:00+08:00'))
        for time,duration in [('13:45',30),('13:00',60),('13:15',90),('13:30',15)]:
            self.assertEqual(self.add(time,duration).status_code,409)
        self.assertEqual(self.add('14:30',30).status_code,201)
        self.assertEqual(self.add('13:00',30).status_code,201)
        self.assertEqual(self.add('13:45',30,'doctor-anita').status_code,201)
        public=next(s for s in self.client.get('/slots').json() if s['id']==first['id'])
        self.assertEqual((public['duration_minutes'],public['ends_at']),(60,first['ends_at']))
        booked=Store(self.path).book('patient-ava',first['id'],'duration-book')
        self.assertEqual((booked['duration_minutes'],booked['ends_at']),(60,first['ends_at']))

    def test_midnight_window_and_closed_slot_release(self):
        first=self.add('23:30',90).json()
        next_day=(datetime.fromisoformat(first['starts_at'])+timedelta(days=1)).date().isoformat()
        self.assertTrue(first['ends_at'].startswith(next_day+'T01:00'))
        self.assertEqual(self.add('00:30',30,day=next_day).status_code,409)
        self.assertEqual(self.add('01:00',30,day=next_day).status_code,201)
        Store(self.path).close_slot(first['id'])
        with Store(self.path).connect() as db:
            db.execute('UPDATE slots SET starts_at=? WHERE id=?',
                       (datetime.fromisoformat(first['starts_at']).astimezone(timezone.utc).isoformat(),first['id']))
        self.assertEqual(self.add('23:45',30).status_code,201)
        duplicate=self.add('23:30',90,key='closed-duplicate-start')
        self.assertEqual(duplicate.status_code,409)
        self.assertIn('including closed slots',duplicate.json()['detail'])

    def test_validation_retry_and_concurrent_overlap(self):
        saved=self.add(key='same-duration-request').json()
        self.assertEqual(self.add(key='same-duration-request').json(),saved)
        self.assertEqual(self.add(duration=45,key='same-duration-request').status_code,409)
        for duration in (0,14,16,121,True,30.5,'30'):
            self.assertEqual(self.add('16:00',duration).status_code,422)
        store=Store(self.path)
        def add(time):
            try:return store.add_slot('doctor-lim',self.day(),'16:'+time,2,'race-duration-'+time,60)['id']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(add,['00','30']))
        self.assertEqual(sum(isinstance(r,str) for r in results),1)
        self.assertIn(409,results)

    def test_existing_database_migration_keeps_bookings_and_start_times(self):
        path=self.path.with_name('legacy-duration.sqlite3')
        start=self.day()+'T13:30:00+08:00'
        with sqlite3.connect(path) as db:
            db.executescript('''CREATE TABLE slots(id TEXT PRIMARY KEY,doctor_id TEXT,starts_at TEXT,clinic_date TEXT,capacity INTEGER);
                CREATE TABLE bookings(id TEXT PRIMARY KEY,patient_id TEXT,slot_id TEXT,queue_number INTEGER,status TEXT,created_at TEXT,request_id TEXT);''')
            db.execute('INSERT INTO slots VALUES(?,?,?,?,?)',('legacy-slot','doctor-lim',start,self.day(),2))
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',('legacy-visit','patient-ava','legacy-slot',7,'waiting',start,'legacy-request'))
        store=Store(path)
        with store.connect() as db:
            visit=store.record(db,'legacy-visit')
            self.assertEqual((visit['starts_at'],visit['queue_number'],visit['duration_minutes']),(start,7,30))
            db.execute("UPDATE slots SET duration_minutes=90 WHERE id='legacy-slot'")
        reopened=Store(path)
        with reopened.connect() as db:self.assertEqual(reopened.record(db,'legacy-visit')['duration_minutes'],90)

    def test_seed_skips_staff_duration_windows_and_preserves_closed_slots(self):
        path=self.path.with_name('seed-duration.sqlite3')
        day=self.day(1)
        with sqlite3.connect(path) as db:
            db.execute('''CREATE TABLE slots(id TEXT PRIMARY KEY,doctor_id TEXT,starts_at TEXT,clinic_date TEXT,capacity INTEGER,duration_minutes INTEGER NOT NULL DEFAULT 30)''')
            db.execute('INSERT INTO slots VALUES(?,?,?,?,?,?)',('long-staff-slot','doctor-lim',day+'T09:30:00+08:00',day,2,120))
        store=Store(path)
        same_day=[s for s in store.slots() if s['doctor_id']=='doctor-lim' and s['clinic_date']==day]
        self.assertEqual([s['starts_at'][11:16] for s in same_day],['09:00','09:30'])
        Store(path)
        self.assertEqual([s['starts_at'][11:16] for s in store.slots() if s['doctor_id']=='doctor-lim' and s['clinic_date']==day],['09:00','09:30'])
        store.close_slot('long-staff-slot')
        reopened=Store(path)
        with reopened.connect() as db:self.assertEqual(reopened.managed_slot(db,'long-staff-slot')['closed'],1)
