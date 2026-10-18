from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        # mkdtemp + no cleanup here: tests run within ignored project .test-data.
        root = Path(__file__).parents[1] / '.test-data'
        root.mkdir(exist_ok=True)
        self.path = Path(tempfile.mkdtemp(dir=root)) / 'test.sqlite3'
        # Workflow fixtures are synthetic blocks, not skin-validation examples.
        self.client = TestClient(create_app(self.path,photo_checker=lambda content:{'accepted':True},predictor=lambda content:None))
        self.slot = self.client.get('/slots').json()[0]
        self.patient = {'X-Demo-Actor':'patient-ava'}
        self.other = {'X-Demo-Actor':'patient-noah'}
        self.staff = {'X-Demo-Actor':'staff-demo'}

    def book(self, actor=None, request='request-one'):
        return self.client.post('/bookings', headers=actor or self.patient,
            json={'slot_id':self.slot['id'],'request_id':request})

    def test_doctor_profiles_roles_validation_and_persistence(self):
        self.assertEqual(self.client.get('/doctors').status_code,422)
        profiles=self.client.get('/doctors',headers=self.patient).json()
        self.assertEqual(len(profiles),2)
        self.assertTrue(all(p['specialty']=='Not specified' and p['expertise']==[] for p in profiles))
        payload={'specialty':' Dermatology (fictional) ','expertise':['acne','general'],'version':0}
        url='/staff/doctors/doctor-lim'
        for identity in (self.patient, self.other, {'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.client.post(url,headers=identity,json=payload).status_code,403)
        saved=self.client.post(url,headers=self.staff,json=payload).json()
        self.assertEqual(saved['specialty'],'Dermatology (fictional)')
        self.assertEqual(saved['version'],1)
        self.assertEqual(self.client.post(url,headers=self.staff,json=payload).json(),saved)
        reopened=TestClient(create_app(self.path))
        self.assertIn(saved,reopened.get('/doctors',headers=self.other).json())
        for changes in ({'specialty':' '},{'specialty':'x'*81},{'expertise':['unknown']},{'expertise':['acne','acne']},{'version':True}):
            self.assertEqual(self.client.post(url,headers=self.staff,json=payload|changes).status_code,422)
        self.assertEqual(self.client.post('/staff/doctors/missing',headers=self.staff,json=payload).status_code,404)

    def test_doctor_profiles_stale_edits_do_not_overwrite(self):
        url='/staff/doctors/doctor-anita'
        original={'specialty':'Fictional dermatology','expertise':['eczema'],'version':0}
        self.assertEqual(self.client.post(url,headers=self.staff,json=original).status_code,200)
        stale=self.client.post(url,headers=self.staff,json=original|{'expertise':['psoriasis']})
        self.assertEqual(stale.status_code,409)
        saved=self.client.post(url,headers=self.staff,json=original|{'expertise':[],'version':1}).json()
        self.assertEqual(saved['expertise'],[])
        self.assertEqual(saved['version'],2)

    def test_doctor_profile_concurrent_edits_only_one_wins(self):
        store=Store(self.path)
        def edit(specialty):
            try:
                return store.save_doctor_profile('doctor-lim',specialty,['general'],0)['version']
            except RuleError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(edit,['Fictional specialty one','Fictional specialty two']))
        self.assertEqual(sorted(outcomes),[1,409])

    def test_doctor_matching_manual_ranking_fallback_and_live_profiles(self):
        store=Store(self.path)
        store.save_doctor_profile('doctor-lim','Fictional dermatology',['acne'],0)
        store.save_doctor_profile('doctor-anita','Fictional dermatology',['general'],0)
        def matches(concern):
            return self.client.get('/doctor-matches',headers=self.patient,params={'concern':concern}).json()
        acne=matches('acne')
        self.assertEqual(acne['source'],'manual')
        self.assertEqual([(d['doctor_id'],d['match_level']) for d in acne['doctors']],
                         [('doctor-lim','concern'),('doctor-anita','general')])
        eczema=matches('eczema')
        self.assertEqual([(d['doctor_id'],d['match_level']) for d in eczema['doctors']],
                         [('doctor-anita','general'),('doctor-lim','none')])
        store.save_doctor_profile('doctor-lim','Fictional dermatology',['eczema'],1)
        self.assertEqual(matches('eczema')['doctors'][0]['doctor_id'],'doctor-lim')
        self.assertEqual(len(matches('psoriasis')['doctors']),2)
        for params in ({},{'concern':'unknown'},{'concern':'acne','assessment_id':'x'},{'assessment_id':''}):
            self.assertEqual(self.client.get('/doctor-matches',headers=self.patient,params=params).status_code,422)
        for who in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.client.get('/doctor-matches',headers=who,params={'concern':'general'}).status_code,403)

    def test_assessment_matching_is_owned_simulated_and_does_not_share(self):
        store=Store(self.path)
        assessment=store.save_assessment('patient-ava','match-photo-fixture','hash',b'fictional',1,1)
        params={'assessment_id':assessment['id']}
        result=self.client.get('/doctor-matches',headers=self.patient,params=params).json()
        self.assertEqual(result['source'],'simulation')
        self.assertEqual(result['concern'],'acne')
        self.assertIn('SIMULATION',result['message'])
        self.assertNotIn('photo_uri',str(result))
        self.assertEqual(self.client.get('/doctor-matches',headers=self.other,params=params).status_code,404)
        self.assertEqual(self.client.get('/doctor-matches',headers=self.patient,params={'assessment_id':'missing'}).status_code,404)
        self.assertEqual(store.shares('patient-ava'),[])
        self.book()
        self.assertEqual(store.shares('patient-ava'),[])

    def test_unknown_assessment_category_uses_general_matching(self):
        from unittest.mock import patch
        store=Store(self.path)
        assessment=store.save_assessment('patient-ava','unknown-result-fixture','hash',b'fictional',1,1)
        with patch.object(Store,'assessment_metadata',return_value={'origin':'simulation','example_category':'Uncertain'}):
            result=store.doctor_matches('patient-ava',assessment_id=assessment['id'])
        self.assertEqual(result['concern'],'general')

    def test_connected_persistence_and_scoping(self):
        booking = self.book().json()
        self.assertEqual(self.book().json()['id'], booking['id'])
        self.assertEqual(self.book(request='request-two').status_code,409)
        self.assertEqual(self.client.get('/bookings', headers=self.other).json(), [])
        self.assertEqual(self.client.post(f"/bookings/{booking['id']}/cancel", headers=self.other).status_code,403)
        payload={'doctor_id':self.slot['doctor_id'],'clinic_date':self.slot['clinic_date']}
        self.assertEqual(self.client.get('/queue',params=payload,headers=self.patient).status_code,403)
        self.assertEqual(self.client.post('/queue/call-next',json=payload,headers=self.staff).json()['id'],booking['id'])
        self.assertEqual(self.client.post('/queue/call-next',json=payload,headers=self.staff).status_code,409)
        self.assertEqual(self.client.post(f"/bookings/{booking['id']}/cancel",headers=self.patient).status_code,409)
        self.assertEqual(self.client.post(f"/queue/{booking['id']}/complete",headers=self.staff).json()['status'],'completed')
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/bookings',headers=self.patient).json()[0]['status'],'completed')

    def test_cancel_releases_capacity_and_preserves_token(self):
        first=self.book().json()
        second=self.book(self.other,'request-noah').json()
        self.assertNotEqual(first['queue_number'],second['queue_number'])
        self.assertEqual(self.client.post(f"/bookings/{first['id']}/cancel",headers=self.patient).status_code,200)
        third=self.book(request='request-new').json()
        self.assertGreater(third['queue_number'],second['queue_number'])
        self.assertEqual(self.client.get('/slots').json()[0]['available'],0)

    def test_simultaneous_duplicate_and_capacity(self):
        store=Store(self.path)
        def reserve(_):
            try:return store.book('patient-ava',self.slot['id'],'same-retry')['id']
            except RuleError as e:return e.message
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(reserve,range(4)))
        self.assertEqual(len(set(results)),1)
        self.assertEqual(len(store.mine('patient-ava')),1)

    def test_staff_and_invalid_inputs(self):
        self.assertEqual(self.book(self.staff).status_code,403)
        self.assertEqual(self.client.post('/bookings',headers=self.patient,json={}).status_code,422)
        self.assertEqual(self.client.get('/bookings').status_code,422)
        self.assertEqual(self.client.get('/bookings',headers={'X-Demo-Actor':'made-up'}).status_code,401)

    def test_competing_patients_cannot_overbook(self):
        store=Store(self.path)
        with store.connect() as db:
            db.execute('UPDATE slots SET capacity=1 WHERE id=?',(self.slot['id'],))
        def reserve(patient):
            try:
                store.book(patient,self.slot['id'],'competing-request')
                return 'saved'
            except RuleError:
                return 'rejected'
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reserve,['patient-ava','patient-noah']))
        self.assertCountEqual(results,['saved','rejected'])
        self.assertEqual(store.slots()[0]['available'],0)

    def test_waiting_cannot_complete_and_past_cannot_book(self):
        booking=self.book().json()
        self.assertEqual(self.client.post(f"/queue/{booking['id']}/complete",headers=self.staff).status_code,409)
        store=Store(self.path)
        with store.connect() as db:
            db.execute("UPDATE slots SET starts_at='2000-01-01T09:00:00+08:00' WHERE id=?",(self.slot['id'],))
        self.assertEqual(self.book(self.other,'past-request').status_code,409)

if __name__ == '__main__':unittest.main()
