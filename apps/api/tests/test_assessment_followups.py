from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json,sqlite3,unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_predictions as predictions
from test_predictions import prediction

class AssessmentFollowupTests(unittest.TestCase):
    setUp=predictions.PredictionTests.setUp
    def symptoms(self,**kw):return {'body_area':'Forearm','onset':'3 days ago','itching':'yes','pain':'no','description':'Fictional follow-up context'}|kw
    def upload(self,request='followup-root-request',previous=None,actor=None,symptoms=None):
        data={'request_id':request,'symptoms':json.dumps(symptoms or self.symptoms())}
        if previous is not None:data['previous_id']=previous
        return self.client.post('/assessments',headers=actor or self.patient,data=data,files={'photo':('fictional.png',self.body,'image/png')})
    def pair(self):
        self.root=self.upload().json();self.predict.return_value=prediction('acne','test-next-model')
        result=self.upload('followup-child-request',self.root['id'],symptoms=self.symptoms(itching='no',description='Fictional new symptoms'));self.assertEqual(result.status_code,201,result.text);self.child=result.json();return self.root,self.child
    def share(self,id,doctor='doctor-lim',request=None):
        response=self.client.post('/assessments/'+id+'/share',headers=self.patient,json={'doctor_id':doctor,'patient_message':'Fictional review','request_id':request or 'share-'+id});self.assertEqual(response.status_code,200,response.text);return response.json()

    def test_new_photo_symptoms_predictions_are_independent_and_parent_is_preserved(self):
        root,child=self.pair();self.assertEqual(child['follow_up_of'],root['id']);self.assertNotEqual(child['id'],root['id'])
        self.assertEqual(child['symptoms']['itching'],'no');self.assertEqual(root['symptoms']['itching'],'yes')
        self.assertEqual(root['prediction']['model_id'],'test-model-v1');self.assertEqual(child['prediction']['model_id'],'test-next-model')
        self.assertTrue(all(call.args==(self.body,) for call in self.predict.call_args_list))
        reopened=TestClient(create_app(self.path));old=reopened.get('/assessments/'+root['id'],headers=self.patient).json()
        for key in root:
            if key!='follow_ups':self.assertEqual(old[key],root[key],key)
        self.assertEqual(old['follow_ups'],[{'id':child['id'],'created_at':child['created_at']}])
        comparison=reopened.get('/assessments/'+child['id']+'/comparison',headers=self.patient).json()
        self.assertEqual(comparison['previous']['photo_uri'],root['photo_uri']);self.assertEqual(comparison['current']['prediction'],child['prediction'])
        self.assertEqual(set(comparison),{'previous','current'})

    def test_invalid_foreign_parent_and_roles_reject_before_prediction_or_persistence(self):
        root=self.upload().json();count=self.predict.call_count
        for previous in (root['id'],'missing-parent'):
            result=self.upload('invalid-child-request',previous,actor=self.other);self.assertEqual(result.status_code,404)
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'},{'X-Demo-Actor':'admin-demo'}):self.assertIn(self.upload(previous=root['id'],actor=actor).status_code,(401,403))
        self.assertEqual(self.predict.call_count,count)
        missing=self.client.post('/assessments',headers=self.patient,data={'request_id':'missing-symptoms-request','previous_id':root['id']},files={'photo':('fictional.png',self.body,'image/png')});self.assertEqual(missing.status_code,422)
        with Store(self.path).connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assessments').fetchone()[0],1)

    def test_retries_cannot_change_parent_or_detach_link_and_do_not_run_model_again(self):
        root,child=self.pair();count=self.predict.call_count
        again=self.upload('followup-child-request',root['id'],symptoms=child['symptoms']);self.assertEqual(again.json(),child)
        self.assertEqual(self.predict.call_count,count)
        self.assertEqual(self.upload('followup-child-request',symptoms=child['symptoms']).status_code,409)
        other=self.upload('followup-second-root').json()
        self.assertEqual(self.upload('followup-child-request',other['id'],symptoms=child['symptoms']).status_code,409)
        self.assertEqual(self.upload('followup-root-request',other['id']).status_code,409)
        with Store(self.path).connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_followups').fetchone()[0],1)

    def test_concurrent_save_retry_links_once_and_link_failure_rolls_back_photo(self):
        root=self.upload().json();store=Store(self.path)
        def save(_):return store.save_assessment('patient-ava','concurrent-followup','same-hash',b'fictional-jpeg',384,384,prediction=prediction(),symptoms=self.symptoms(),previous_id=root['id'])
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(save,range(4)))
        self.assertEqual(len({row['id'] for row in rows}),1)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_followups').fetchone()[0],1)
            db.execute("CREATE TRIGGER fail_link BEFORE INSERT ON assessment_followups BEGIN SELECT RAISE(ABORT,'Injected link failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):store.save_assessment('patient-ava','rollback-followup','hash',b'photo',384,384,symptoms=self.symptoms(),previous_id=root['id'])
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM assessments').fetchone()[0],2)

    def test_patient_comparison_history_and_chain_remain_owned(self):
        root,child=self.pair();grand=self.upload('followup-grandchild',child['id']).json()
        history=self.client.get('/assessments/history',headers=self.patient).json()['items']
        self.assertEqual({row['id']:row['follow_up_of'] for row in history},{root['id']:None,child['id']:root['id'],grand['id']:child['id']})
        self.assertTrue(all('photo_uri' not in row for row in history))
        for id in (root['id'],child['id'],grand['id']):self.assertEqual(self.client.get('/assessments/'+id+'/comparison',headers=self.other).status_code,404)
        self.assertEqual(self.client.get('/assessments/'+root['id']+'/comparison',headers=self.patient).status_code,404)
        self.assertEqual(self.client.get('/assessments/'+child['id']+'/comparison',headers=self.staff).status_code,403)
        self.assertEqual(self.client.get('/assessments/'+grand['id']+'/comparison',headers=self.patient).json()['previous']['id'],child['id'])

    def test_doctor_needs_both_active_shares_and_revocation_removes_comparison(self):
        root,child=self.pair();current=self.share(child['id']);lim={'X-Demo-Actor':'doctor-lim'};url='/assessment-shares/'+current['id']+'/comparison'
        self.assertEqual(self.client.get(url,headers=lim).status_code,404)
        detail=self.client.get('/assessment-shares/'+current['id'],headers=lim).json();self.assertNotIn('previous',detail);self.assertNotIn('follow_ups',detail['assessment'])
        self.share(root['id'],'doctor-anita','parent-other-doctor');self.assertEqual(self.client.get(url,headers=lim).status_code,404)
        previous=self.share(root['id']);self.assertEqual(self.client.get(url,headers=lim).json()['previous']['id'],root['id'])
        self.assertEqual(self.client.get(url,headers={'X-Demo-Actor':'doctor-anita'}).status_code,404)
        for actor in (self.staff,self.patient):self.assertEqual(self.client.get(url,headers=actor).status_code,403)
        self.client.post('/assessment-shares/'+previous['id']+'/revoke',headers=self.patient,json={});self.assertEqual(self.client.get(url,headers=lim).status_code,404)
        self.assertEqual(self.client.get('/assessment-shares/'+current['id'],headers=lim).status_code,200)
        self.client.post('/assessment-shares/'+current['id']+'/revoke',headers=self.patient,json={});self.assertEqual(self.client.get(url,headers=lim).status_code,404)
        self.assertEqual(self.client.get('/assessments/'+child['id']+'/comparison',headers=self.patient).status_code,200)

    def test_cancelled_appointment_parent_share_does_not_grant_comparison(self):
        root,child=self.pair();booking=self.client.post('/bookings',headers=self.patient,json={'slot_id':self.slot['id'],'request_id':'comparison-booking'}).json();doctor=self.slot['doctor_id'];headers={'X-Demo-Actor':doctor}
        previous=self.client.post('/assessments/'+root['id']+'/link-appointment',headers=self.patient,json={'booking_id':booking['id'],'patient_message':'Fictional','request_id':'comparison-parent-link'});self.assertEqual(previous.status_code,200,previous.text)
        current=self.share(child['id'],doctor);url='/assessment-shares/'+current['id']+'/comparison';self.assertEqual(self.client.get(url,headers=headers).status_code,200)
        result=self.client.post('/bookings/'+booking['id']+'/cancel',headers=self.patient);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get(url,headers=headers).status_code,404)
        self.share(root['id'],doctor,'comparison-independent-share');self.assertEqual(self.client.get(url,headers=headers).status_code,200)

    def test_existing_unlinked_assessment_and_all_sharing_state_are_unchanged(self):
        root=self.upload().json();before=deepcopy(root)
        with Store(self.path).connect() as db:raw=tuple(db.execute('SELECT * FROM assessments WHERE id=?',(root['id'],)).fetchone())
        self.upload('followup-preservation',root['id'])
        with Store(self.path).connect() as db:
            self.assertEqual(tuple(db.execute('SELECT * FROM assessments WHERE id=?',(root['id'],)).fetchone()),raw)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_shares').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_reviews').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_notifications').fetchone()[0],0)
        self.assertEqual(root,before)
