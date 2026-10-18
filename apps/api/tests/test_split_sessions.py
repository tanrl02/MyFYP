import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_schedules as schedules


class SplitSessionTests(unittest.TestCase):
    setUp=schedules.ScheduleTests.setUp
    preview=schedules.ScheduleTests.preview
    generate=schedules.ScheduleTests.generate

    def save(self,**changes):
        body=self.body|dict(start_time='09:00',end_time='10:00',second_start_time='14:00',second_end_time='15:00')
        return self.client.post(self.url,headers=self.staff,json=body|changes)

    def test_both_sessions_generated_no_lunch_slots_booking_and_reload(self):
        saved=self.save().json()
        self.assertEqual((saved['version'],saved['second_start_time'],saved['second_end_time']),(1,'14:00','15:00'))
        self.assertEqual(self.save().json(),saved)
        plan=self.preview().json()
        self.assertEqual(plan['new_count'],8)
        self.assertEqual([slot['starts_at'][11:16] for slot in plan['slots']],['09:00','09:30','14:00','14:30']*2)
        result=self.generate(plan).json()
        self.assertEqual(result['created_count'],8)
        self.assertEqual(self.generate(plan).json(),result)
        public=[item for item in self.store.slots() if item['id'] in result['slot_ids']]
        morning=next(item for item in public if item['starts_at'][11:16]=='09:00')
        afternoon=next(item for item in public if item['starts_at'][11:16]=='14:00')
        ava=self.store.book('patient-ava',morning['id'],'morning-booking')
        noah=self.store.book('patient-noah',afternoon['id'],'afternoon-booking')
        reopened=Store(self.path)
        self.assertEqual(reopened.mine('patient-ava'),[ava]);self.assertEqual(reopened.mine('patient-noah'),[noah])
        own=self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':self.week}).json()
        self.assertEqual(own['pattern'],saved)
        self.assertEqual(len(own['slots']),8)
        other=self.client.get('/doctor/schedule',headers=self.anita,params={'week_start':self.week}).json()
        self.assertEqual(other['slots'],[])
        self.assertIsNone(other['pattern']['second_start_time'])
        self.assertEqual(self.preview().json()['existing_count'],8)

    def test_validation_both_bounds_order_whole_slots_total_limit_and_roles(self):
        for changes in ({'second_start_time':None},{'second_end_time':None},{'second_start_time':'08:00'},
                        {'second_start_time':'09:30'},{'second_end_time':'14:00'},{'second_end_time':'13:00'},
                        {'second_end_time':'15:10'},{'second_start_time':'25:00'},
                        {'second_start_time':'1\u0664:00'},{'second_start_time':''},
                        {'weekdays':list(range(7)),'start_time':'00:00','end_time':'08:00','second_start_time':'09:00','second_end_time':'17:00','duration_minutes':15}):
            self.assertEqual(self.save(**changes).status_code,422,changes)
        body=self.body|{'second_start_time':'16:00','second_end_time':'17:00'}
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.post(self.url,headers=actor,json=body).status_code,403)
        # Adjacent sessions are valid; the boundary must not duplicate a slot.
        self.assertEqual(self.save(second_start_time='10:00',second_end_time='11:00').status_code,200)
        plan=self.preview().json()
        self.assertEqual(len({item['starts_at'] for item in plan['slots']}),8)

    def test_existing_legacy_pattern_json_version_and_preview_are_preserved(self):
        legacy={key:value for key,value in self.body.items() if key!='version'}
        with self.store.connect() as db:
            db.execute('INSERT INTO doctor_schedule_patterns VALUES(?,?,?,?,?)',('doctor-lim',json.dumps(legacy),7,'2034-12-31T00:00:00+00:00','staff-demo'))
        reloaded=Store(self.path)
        current=reloaded.schedule_patterns()[0]
        self.assertEqual(current['version'],7);self.assertIsNone(current['second_start_time']);self.assertIsNone(current['second_end_time'])
        plan=reloaded.preview_schedule('doctor-lim',self.week,7)
        self.assertEqual(plan['new_count'],4)
        # A legacy retry does not rewrite the stored pattern or change its version.
        self.assertEqual(reloaded.save_schedule_pattern('doctor-lim',[0,2],'14:00','15:00',30,2,7),current)
        with reloaded.connect() as db:self.assertEqual(json.loads(db.execute('SELECT pattern_json FROM doctor_schedule_patterns').fetchone()[0]),legacy)
        self.assertEqual(TestClient(create_app(self.path)).get('/staff/schedules',headers=self.staff).json()[0],current)

    def test_second_session_conflict_blocks_whole_batch_and_preserves_bookings(self):
        self.save()
        slot=self.store.add_slot('doctor-lim',self.week,'14:00',3,'split-conflict')
        visit=self.store.book('patient-ava',slot['id'],'existing-afternoon')
        before=self.store.managed_slots()
        plan=self.preview().json();self.assertEqual(plan['conflict_count'],1)
        self.assertEqual(self.generate(plan).status_code,409)
        self.assertEqual(self.store.managed_slots(),before)
        self.assertEqual(self.store.mine('patient-ava'),[visit])

    def test_absences_skip_only_overlapping_session_and_stale_plans_rejected(self):
        self.save();old=self.preview().json()
        self.store.add_unavailability('doctor-lim',self.week,'Afternoon meeting','split-partial-absence','14:00','14:30')
        self.assertEqual(self.generate(old).status_code,409)
        wednesday=(date.fromisoformat(self.week)+timedelta(days=2)).isoformat()
        self.store.add_unavailability('doctor-lim',wednesday,'Whole day','split-full-absence')
        plan=self.preview().json()
        self.assertEqual((plan['new_count'],plan['unavailable_count']),(3,5))
        result=self.generate(plan).json();self.assertEqual(result['created_count'],3)
        slots=[item for item in self.store.slots() if item['id'] in result['slot_ids']]
        self.assertEqual([item['starts_at'][11:16] for item in slots],['09:00','09:30','14:30'])

    def test_add_remove_second_session_never_retimes_or_closes_existing_slots(self):
        single=self.save(second_start_time=None,second_end_time=None).json()
        first=self.generate(self.preview().json()).json()
        existing=self.store.managed_slots()
        visit=self.store.book('patient-ava',first['slot_ids'][0],'single-before-split')
        old=self.preview().json()
        self.assertEqual(self.save(version=single['version']).json()['version'],2)
        self.assertEqual(self.generate(old,'stale-single-plan').status_code,409)
        plan=self.preview(version=2).json()
        self.assertEqual((plan['existing_count'],plan['new_count']),(4,4))
        result=self.generate(plan,'split-second-generation').json()
        all_slots=self.store.managed_slots()
        self.assertEqual(len(all_slots),len(existing)+4)
        removed=self.save(version=2,second_start_time=None,second_end_time=None).json()
        self.assertEqual(removed['version'],3)
        self.assertEqual(self.store.managed_slots(),all_slots)
        self.assertEqual(self.store.mine('patient-ava'),[visit])
        # Completed request remains historical despite later pattern edits.
        self.assertEqual(self.generate(plan,'split-second-generation').json(),result)

    def test_concurrent_second_session_edits_and_generation_remain_atomic(self):
        self.save()
        def edit(end):
            try:return self.store.save_schedule_pattern('doctor-lim',[0,2],'09:00','10:00',30,2,1,'14:00',end)['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,['15:30','16:00']))
        self.assertEqual(sorted(results),[2,409])
        plan=self.preview(version=2).json()
        before=len(self.store.managed_slots())
        def generate(_):return self.store.generate_schedule('doctor-lim',self.week,2,plan['preview_token'],'split-concurrent-generation')
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(generate,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        self.assertEqual(len(self.store.managed_slots()),before+plan['new_count'])
