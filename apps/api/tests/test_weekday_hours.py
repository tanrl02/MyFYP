import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_schedules as schedules


class WeekdayHoursTests(unittest.TestCase):
    setUp=schedules.ScheduleTests.setUp
    preview=schedules.ScheduleTests.preview
    generate=schedules.ScheduleTests.generate

    def save(self,**changes):
        body=self.body|dict(weekdays=[0,5],start_time='09:00',end_time='10:00',second_start_time='14:00',second_end_time='15:00',day_sessions=[dict(weekday=5,start_time='10:00',end_time='11:00')])
        return self.client.post(self.url,headers=self.staff,json=body|changes)

    def test_distinct_day_generation_gap_booking_privacy_and_reload(self):
        saved=self.save().json();self.assertEqual(saved['version'],1)
        self.assertEqual(saved['day_sessions'][0]['weekday'],5)
        self.assertIsNone(saved['day_sessions'][0]['second_start_time'])
        self.assertEqual(self.save().json(),saved)
        plan=self.preview().json();self.assertEqual(plan['new_count'],6)
        self.assertEqual([slot['starts_at'][11:16] for slot in plan['slots']],['09:00','09:30','14:00','14:30','10:00','10:30'])
        result=self.generate(plan).json();self.assertEqual(self.generate(plan).json(),result)
        slots=[slot for slot in self.store.slots() if slot['id'] in result['slot_ids']]
        saturday=(date.fromisoformat(self.week)+timedelta(days=5)).isoformat()
        self.assertTrue(all(slot['starts_at'][11:16] in ('10:00','10:30') for slot in slots if slot['clinic_date']==saturday))
        visit=self.store.book('patient-ava',slots[-1]['id'],'custom-saturday-book')
        self.assertEqual(Store(self.path).mine('patient-ava'),[visit]);self.assertEqual(Store(self.path).mine('patient-noah'),[])
        own=TestClient(create_app(self.path)).get('/doctor/schedule',headers=self.lim,params={'week_start':self.week}).json()
        self.assertEqual(own['pattern'],saved)
        self.assertEqual(self.client.get('/doctor/schedule',headers=self.anita,params={'week_start':self.week}).json()['pattern']['day_sessions'],[])

    def test_invalid_custom_day_sessions_and_role_boundaries(self):
        base=dict(weekday=5,start_time='10:00',end_time='11:00')
        bad=[{'weekday':2},{'weekday':True},{'weekday':7},{'start_time':'bad'},{'end_time':'10:00'},{'end_time':'10:10'},
             {'second_start_time':'14:00'},{'second_start_time':'10:30','second_end_time':'12:00'},
             {'second_start_time':'14:00','second_end_time':'13:00'},{'start_time':'1\u0660:00'}]
        for changes in bad:self.assertEqual(self.save(day_sessions=[base|changes]).status_code,422,changes)
        self.assertEqual(self.save(day_sessions=[base,base]).status_code,422)
        self.assertEqual(self.save(day_sessions=None).status_code,422)
        self.assertEqual(self.save(day_sessions=[base|{'capacity':3}]).status_code,422)
        body=self.body|{'day_sessions':[dict(weekday=0,start_time='09:00',end_time='10:00')]}
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.post(self.url,headers=actor,json=body).status_code,403)

    def test_effective_weekly_limit_counts_custom_hours_instead_of_shared_hours(self):
        # Shared hours alone would exceed200; shortened custom hours bring actual total below it.
        short=[dict(weekday=day,start_time='09:00',end_time='10:00') for day in range(7)]
        self.assertEqual(self.save(weekdays=list(range(7)),start_time='00:00',end_time='12:00',second_start_time=None,second_end_time=None,duration_minutes=15,day_sessions=short).status_code,200)
        self.assertEqual(self.preview().json()['new_count'],28)
        long=[dict(weekday=day,start_time='00:00',end_time='12:00') for day in range(7)]
        self.assertEqual(self.save(version=1,weekdays=list(range(7)),duration_minutes=15,day_sessions=long).status_code,422)

    def test_legacy_single_and_split_json_remain_unchanged_on_identical_retry(self):
        for second in (False,True):
            with self.subTest(second=second):
                legacy={key:value for key,value in self.body.items() if key!='version'}
                if second:legacy.update(second_start_time='16:00',second_end_time='17:00')
                with self.store.connect() as db:
                    db.execute('INSERT OR REPLACE INTO doctor_schedule_patterns VALUES(?,?,?,?,?)',('doctor-lim',json.dumps(legacy),7,'2034-12-31T00:00:00+00:00','staff-demo'))
                restored=Store(self.path);current=restored.schedule_patterns()[0]
                self.assertEqual(current['day_sessions'],[])
                self.assertEqual(restored.preview_schedule('doctor-lim',self.week,7)['new_count'],8 if second else 4)
                same=restored.save_schedule_pattern('doctor-lim',[0,2],'14:00','15:00',30,2,7,'16:00' if second else None,'17:00' if second else None)
                self.assertEqual(same,current)
                with restored.connect() as db:self.assertEqual(json.loads(db.execute('SELECT pattern_json FROM doctor_schedule_patterns').fetchone()[0]),legacy)

    def test_custom_day_absences_conflicts_and_stale_preview_protect_entire_batch(self):
        self.save();old=self.preview().json()
        saturday=(date.fromisoformat(self.week)+timedelta(days=5)).isoformat()
        self.store.add_unavailability('doctor-lim',saturday,'Saturday meeting','day-hours-absence','10:00','10:30')
        self.assertEqual(self.generate(old).status_code,409)
        current=self.preview().json();self.assertEqual((current['new_count'],current['unavailable_count']),(5,1))
        slot=self.store.add_slot('doctor-lim',saturday,'10:30',3,'custom-conflict')
        visit=self.store.book('patient-ava',slot['id'],'custom-conflict-book')
        plan=self.preview().json();self.assertEqual(plan['conflict_count'],1)
        before=self.store.managed_slots()
        self.assertEqual(self.generate(plan).status_code,409)
        self.assertEqual(self.store.managed_slots(),before);self.assertEqual(self.store.mine('patient-ava'),[visit])

    def test_changing_or_removing_custom_hours_keeps_old_slots_and_bookings(self):
        self.save();plan=self.preview().json();result=self.generate(plan).json()
        visit=self.store.book('patient-ava',result['slot_ids'][-1],'old-custom-booking')
        before=self.store.managed_slots()
        saved=self.save(version=1,day_sessions=[]).json();self.assertEqual(saved['version'],2)
        self.assertEqual(self.store.managed_slots(),before);self.assertEqual(self.store.mine('patient-ava'),[visit])
        self.assertEqual(self.generate(plan,'stale-custom-plan').status_code,409)
        self.assertEqual(self.generate(plan).json(),result)
        saved=self.save(version=2,weekdays=[0],day_sessions=[]).json();self.assertEqual(saved['version'],3)
        self.assertEqual(self.store.managed_slots(),before)

    def test_canonical_day_order_retry_and_concurrent_changes(self):
        days=[dict(weekday=5,start_time='10:00',end_time='11:00'),dict(weekday=0,start_time='08:00',end_time='09:00')]
        first=self.save(day_sessions=days).json()
        self.assertEqual([item['weekday'] for item in first['day_sessions']],[0,5])
        self.assertEqual(self.save(day_sessions=list(reversed(days))).json(),first)
        def edit(hour):
            try:return self.store.save_schedule_pattern('doctor-lim',[0,5],'09:00','10:00',30,2,1,'14:00','15:00',[dict(weekday=5,start_time=hour,end_time='12:00')])['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,['10:00','11:00']))
        self.assertEqual(sorted(results),[2,409])
