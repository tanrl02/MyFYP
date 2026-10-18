import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_workflow as workflow


class ScheduleClock(datetime):
    instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
    @classmethod
    def now(cls,tz=None):
        return cls.instant.astimezone(tz) if tz else cls.instant.replace(tzinfo=None)


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        ScheduleClock.instant=datetime(2035,1,1,4,tzinfo=timezone.utc)
        clock=patch('app.store.datetime',ScheduleClock);clock.start();self.addCleanup(clock.stop)
        workflow.WorkflowTests.setUp(self)
        self.store=Store(self.path)
        today=ScheduleClock.instant.astimezone(timezone(timedelta(hours=8))).date()
        monday=today+timedelta(days=1)
        while monday.weekday()!=0:monday+=timedelta(days=1)
        self.week=monday.isoformat()
        self.url='/staff/schedules/doctor-lim'
        self.body={'weekdays':[0,2],'start_time':'14:00','end_time':'15:00','duration_minutes':30,'capacity':2,'version':0}
        self.lim={'X-Demo-Actor':'doctor-lim'};self.anita={'X-Demo-Actor':'doctor-anita'}

    def save(self,**changes):
        return self.client.post(self.url,headers=self.staff,json=self.body|changes)

    def preview(self,version=1,week=None):
        return self.client.post(self.url+'/preview',headers=self.staff,json={'version':version,'week_start':week or self.week})

    def generate(self,preview,key='weekly-generation-one'):
        return self.client.post(self.url+'/generate',headers=self.staff,json={'week_start':preview['week_start'],'version':preview['pattern_version'],'preview_token':preview['preview_token'],'request_id':key})

    def test_staff_only_pattern_validation_versioning_and_reopen(self):
        patterns=self.client.get('/staff/schedules',headers=self.staff).json()
        self.assertTrue(all(pattern['version']==0 and pattern['weekdays']==[] for pattern in patterns))
        for actor in (self.patient,self.other,self.lim,self.anita):
            self.assertEqual(self.client.get('/staff/schedules',headers=actor).status_code,403)
            for suffix,body in (('',self.body),('/preview',{'week_start':self.week,'version':1}),('/generate',{'week_start':self.week,'version':1,'preview_token':'a'*64,'request_id':'denied-request'})):
                self.assertEqual(self.client.post(self.url+suffix,headers=actor,json=body).status_code,403)
        for change in ({'weekdays':[]},{'weekdays':[0,0]},{'weekdays':[True]},{'weekdays':[7]},{'weekdays':['1']},
                       {'end_time':'13:00'},{'end_time':'14:40'},{'start_time':'25:00'},{'duration_minutes':20},
                       {'capacity':True},{'capacity':21},{'version':True},{'version':-1},
                       {'weekdays':list(range(7)),'start_time':'00:00','end_time':'23:45','duration_minutes':15}):
            self.assertEqual(self.save(**change).status_code,422,str(change))
        saved=self.save(weekdays=[2,0]).json()
        self.assertEqual((saved['version'],saved['weekdays']),(1,[0,2]))
        self.assertEqual(self.save().json(),saved)
        self.assertEqual(self.save(capacity=3).status_code,409)
        self.assertEqual(self.save(capacity=3,version=1).json()['version'],2)
        self.assertEqual(TestClient(create_app(self.path)).get('/staff/schedules',headers=self.staff).json()[0]['version'],2)
        self.assertEqual(self.client.post('/staff/schedules/unknown',headers=self.staff,json=self.body).status_code,404)

    def test_read_only_preview_generation_retry_public_booking_and_existing_preservation(self):
        self.save()
        existing=self.store.add_slot('doctor-lim',self.week,'14:00',2,'matching-slot')
        booked=self.store.book('patient-ava',existing['id'],'existing-booking')
        before=len(self.store.managed_slots())
        preview=self.preview().json()
        self.assertEqual((preview['new_count'],preview['existing_count'],preview['conflict_count']),(3,1,0))
        self.assertEqual(len(self.store.managed_slots()),before)
        self.assertEqual(self.preview().json(),preview)
        # A patient booking an already retained slot does not invalidate the creation plan.
        self.store.book('patient-noah',existing['id'],'booking-after-preview')
        generated=self.generate(preview)
        self.assertEqual(generated.status_code,201)
        result=generated.json()
        self.assertEqual((result['created_count'],result['existing_count'],len(result['slot_ids'])),(3,1,4))
        self.assertEqual(self.generate(preview).json(),result)
        self.assertEqual(self.generate(preview|{'preview_token':'b'*64}).status_code,409)
        self.assertEqual(self.store.mine('patient-ava')[0],booked)
        self.assertTrue(set(result['slot_ids']).issubset({slot['id'] for slot in self.client.get('/slots').json()}))
        new=next(slot for slot in self.client.get('/slots').json() if slot['id'] in result['slot_ids'] and slot['id']!=existing['id'])
        own=self.store.book('patient-noah',new['id'],'new-generated-booking')
        self.assertEqual((own['duration_minutes'],own['ends_at']),(30,new['ends_at']))
        replay=self.preview().json()
        self.assertEqual((replay['new_count'],replay['existing_count']),(0,4))
        self.assertEqual(self.generate(replay,'second-generation').json()['created_count'],0)
        self.assertEqual(self.store.mine('patient-ava')[0],booked)
        ScheduleClock.instant+=timedelta(days=20)
        reopened=Store(self.path)
        self.assertEqual(reopened.generate_schedule('doctor-lim',self.week,1,preview['preview_token'],'weekly-generation-one'),result)

    def test_closed_different_and_overlapping_slots_block_entire_batch(self):
        self.save()
        first=self.store.add_slot('doctor-lim',self.week,'14:00',2,'closed-slot')
        self.store.close_slot(first['id'])
        self.store.add_slot('doctor-lim',self.week,'14:30',3,'different-capacity')
        wednesday=(date.fromisoformat(self.week)+timedelta(days=2)).isoformat()
        self.store.add_slot('doctor-lim',wednesday,'13:45',2,'overlapping-slot',30)
        preview=self.preview().json()
        self.assertEqual((preview['conflict_count'],preview['new_count']),(3,1))
        before=len(self.store.managed_slots())
        self.assertEqual(self.generate(preview).status_code,409)
        self.assertEqual(len(self.store.managed_slots()),before)
        with self.store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM schedule_generations').fetchone()[0],0)

    def test_changed_preview_and_pattern_cannot_generate_stale_plan(self):
        self.save();preview=self.preview().json()
        # Even a newly matching manual slot must be reviewed before confirming a changed plan.
        self.store.add_slot('doctor-lim',self.week,'14:00',2,'new-between-preview-confirm')
        self.assertEqual(self.generate(preview).status_code,409)
        preview=self.preview().json()
        self.save(version=1,capacity=3)
        self.assertEqual(self.generate(preview).status_code,409)

    def test_concurrent_pattern_and_generation_saves_do_not_duplicate(self):
        def pattern(capacity):
            try:return self.store.save_schedule_pattern('doctor-lim',[0,2],'14:00','15:00',30,capacity,0)['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(pattern,[2,3])),[1,409])
        preview=self.preview().json()
        def generate(_):return self.store.generate_schedule('doctor-lim',self.week,1,preview['preview_token'],'same-generation')
        with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(generate,range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schedule_generations').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM slots WHERE clinic_date>=?',(self.week,)).fetchone()[0],4)

    def test_failed_insert_rolls_back_all_slots_and_generation(self):
        self.save();preview=self.preview().json()
        with self.store.connect() as db:
            db.execute("""CREATE TRIGGER fail_schedule BEFORE INSERT ON slots WHEN NEW.starts_at LIKE '%T14:30:%'
                BEGIN SELECT RAISE(ABORT,'Injected generation failure'); END""")
        with self.assertRaises(Exception):self.store.generate_schedule('doctor-lim',self.week,1,preview['preview_token'],'failed-generation')
        with self.store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM slots WHERE clinic_date>=?',(self.week,)).fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM schedule_generations').fetchone()[0],0)
            db.execute('DROP TRIGGER fail_schedule')
        self.assertEqual(self.generate(preview,'failed-generation').status_code,201)

    def test_generation_races_manual_slot_without_partial_creation(self):
        self.save();preview=self.preview().json()
        def change(kind):
            try:
                if kind=='manual':
                    self.store.add_slot('doctor-lim',self.week,'14:00',3,'racing-manual-slot')
                else:
                    self.store.generate_schedule('doctor-lim',self.week,1,preview['preview_token'],'racing-generation')
                return kind
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,['manual','generate']))
        self.assertEqual(results.count(409),1)
        with self.store.connect() as db:
            count=db.execute('SELECT COUNT(*) FROM slots WHERE clinic_date>=?',(self.week,)).fetchone()[0]
            self.assertEqual(count,1 if 'manual' in results else 4)

    def test_doctor_view_is_own_week_operational_only_and_cannot_manage(self):
        self.save();result=self.generate(self.preview().json()).json()
        visit=self.store.book('patient-ava',result['slot_ids'][0],'schedule-doctor-view')
        response=self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':self.week})
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual({slot['id'] for slot in data['slots']},set(result['slot_ids']))
        booked=next(slot for slot in data['slots'] if slot['visits'])['visits'][0]
        self.assertEqual(booked,{'id':visit['id'],'queue_number':visit['queue_number'],'status':'waiting','patient_name':'Ava Demo'})
        for field in ('background','findings','photo','prescription','invoice','reason','patient_id'):
            self.assertNotIn(field,json.dumps(data))
        self.assertEqual(self.client.get('/doctor/schedule',headers=self.anita,params={'week_start':self.week}).json()['slots'],[])
        for actor in (self.patient,self.staff):
            self.assertEqual(self.client.get('/doctor/schedule',headers=actor,params={'week_start':self.week}).status_code,403)
        otherday=(date.fromisoformat(self.week)+timedelta(days=1)).isoformat()
        self.assertEqual(self.client.get('/doctor/schedule',headers=self.lim,params={'week_start':otherday}).status_code,422)

    def test_future_monday_limits_and_cross_midnight_conflict(self):
        self.assertEqual(self.preview().status_code,409)
        self.save(weekdays=[0],start_time='00:00',end_time='00:30')
        for week in ('2035-01-01','2035-01-02','2035-03-05'):
            self.assertEqual(self.preview(week=week).status_code,422)
        sunday=(date.fromisoformat(self.week)-timedelta(days=1)).isoformat()
        self.store.add_slot('doctor-lim',sunday,'23:45',2,'previous-day-overlap',30)
        self.assertEqual(self.preview().json()['conflict_count'],1)

    def test_saved_patterns_stop_new_demo_seed_slots_but_preserve_existing_rows(self):
        before={slot['id'] for slot in self.store.managed_slots() if slot['doctor_id']=='doctor-lim'}
        self.save()
        ScheduleClock.instant+=timedelta(days=1)
        reopened=Store(self.path)
        with reopened.connect() as db:
            after={row['id'] for row in db.execute("SELECT id FROM slots WHERE doctor_id='doctor-lim'")}
            other={row['id'] for row in db.execute("SELECT id FROM slots WHERE doctor_id='doctor-anita'")}
        self.assertEqual(after,before)
        self.assertGreater(len(other),len(before))
