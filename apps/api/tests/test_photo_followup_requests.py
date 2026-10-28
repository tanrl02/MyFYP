from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import sqlite3,unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
from app.scheduling import MALAYSIA
import test_assessment_followups as followups

class PhotoFollowupRequestTests(unittest.TestCase):
    setUp=followups.AssessmentFollowupTests.setUp
    upload=followups.AssessmentFollowupTests.upload
    symptoms=followups.AssessmentFollowupTests.symptoms
    share=followups.AssessmentFollowupTests.share
    doctor={'X-Demo-Actor':'doctor-lim'}
    def prepare(self):
        self.assessment=self.upload().json();self.shared=self.share(self.assessment['id']);self.route='/assessment-shares/'+self.shared['id']+'/photo-follow-up-request'
        return self.shared
    def payload(self,**kw):return {'due_date':(datetime.now(MALAYSIA).date()+timedelta(days=7)).isoformat(),'instructions':'Fictional instructions for the next photo.\nRecord fresh symptoms.','request_id':'photo-followup-request-one'}|kw
    def request(self,body=None,actor=None):return self.client.post(self.route,headers=actor or self.doctor,json=body or self.payload())
    def patient_route(self):return '/assessments/'+self.assessment['id']+'/photo-follow-up-requests'

    def test_published_request_and_one_scoped_notification_reopen_for_owner(self):
        self.prepare();result=self.request();self.assertEqual(result.status_code,201,result.text);saved=result.json()
        self.assertEqual(saved['assessment_id'],self.assessment['id']);self.assertEqual(saved['doctor_id'],'doctor-lim');self.assertEqual(saved['instructions'],self.payload()['instructions'])
        reopened=TestClient(create_app(self.path));self.assertEqual(reopened.get(self.route,headers=self.doctor).json(),saved)
        self.assertEqual(reopened.get(self.patient_route(),headers=self.patient).json(),[saved])
        inbox=reopened.get('/notifications',headers=self.patient).json();item,=inbox['items'];self.assertEqual((item['kind'],item['source_id'],item['target_id']),('photo_follow_up_requested',saved['id'],self.assessment['id']))
        self.assertNotIn(saved['instructions'],item['message']);self.assertIsNone(item['read_at'])
        self.assertEqual(reopened.get('/notifications',headers=self.other).json()['items'],[])
        self.assertEqual(reopened.get(self.patient_route(),headers=self.other).status_code,404)
        self.assertEqual(reopened.get(self.patient_route(),headers=self.staff).status_code,403)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_reviews').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM assessment_followups').fetchone()[0],0)

    def test_permissions_strict_inputs_and_malaysia_date_boundaries(self):
        self.prepare();today=datetime.now(MALAYSIA).date()
        for actor in (self.patient,self.other,self.staff):self.assertEqual(self.request(actor=actor).status_code,403)
        self.assertEqual(self.request(actor={'X-Demo-Actor':'doctor-anita'}).status_code,404)
        for body in (self.payload(due_date=today.isoformat()),self.payload(due_date=(today-timedelta(days=1)).isoformat()),self.payload(due_date=(today+timedelta(days=366)).isoformat()),self.payload(due_date='2026-02-30'),self.payload(due_date='2026-1-01'),self.payload(instructions=' '),self.payload(instructions='x'*1001),self.payload(instructions='a\x00b'),self.payload(request_id='x'),self.payload()|{'patient_id':'patient-noah'}):
            self.assertEqual(self.request(body).status_code,422,body)
        self.assertEqual(self.request(self.payload(due_date=(today+timedelta(days=365)).isoformat())).status_code,201)
        self.assertEqual(self.client.get(self.route,headers=self.staff).status_code,403)

    def test_concurrent_retries_do_not_duplicate_or_reset_read_and_old_dates_retry(self):
        self.prepare();store=Store(self.path);body=self.payload()
        def save(_):return store.request_photo_followup(self.shared['id'],'doctor-lim',body['due_date'],body['instructions'],body['request_id'])
        with ThreadPoolExecutor(max_workers=4) as pool:rows=list(pool.map(save,range(4)))
        self.assertTrue(all(row==rows[0] for row in rows))
        item=self.client.get('/notifications',headers=self.patient).json()['items'][0]
        read=self.client.post('/notifications/'+item['id']+'/read',headers=self.patient).json()['read_at']
        self.assertEqual(self.request(self.payload(instructions='  '+body['instructions']+'  ')).json(),rows[0])
        self.assertEqual(self.request(self.payload(instructions='Different instructions')).status_code,409)
        self.assertEqual(self.request(self.payload(request_id='new-request-same-share')).status_code,409)
        class Later(datetime):
            @classmethod
            def now(cls,tz=None):return datetime.fromisoformat(body['due_date']+'T12:00:00+08:00')+timedelta(days=1)
        with patch('app.store.datetime',Later):self.assertEqual(save(0),rows[0])
        reopened=TestClient(create_app(self.path));inbox=reopened.get('/notifications',headers=self.patient).json();self.assertEqual(len(inbox['items']),1);self.assertEqual(inbox['items'][0]['read_at'],read)

    def test_revocation_blocks_doctor_and_preserves_patient_published_instructions(self):
        self.prepare();saved=self.request().json();self.client.post('/assessment-shares/'+self.shared['id']+'/revoke',headers=self.patient,json={})
        self.assertEqual(self.request().status_code,404);self.assertEqual(self.client.get(self.route,headers=self.doctor).status_code,404)
        self.assertEqual(self.client.get(self.patient_route(),headers=self.patient).json(),[saved])
        self.assertEqual(len(self.client.get('/notifications',headers=self.patient).json()['items']),1)
        second=self.upload('second-photo-request-source').json();revoked=self.share(second['id']);self.client.post('/assessment-shares/'+revoked['id']+'/revoke',headers=self.patient,json={})
        result=self.client.post('/assessment-shares/'+revoked['id']+'/photo-follow-up-request',headers=self.doctor,json=self.payload(request_id='denied-photo-request'));self.assertEqual(result.status_code,404)

    def test_notification_failure_rolls_back_request_and_can_retry_once(self):
        self.prepare();store=Store(self.path)
        with store.connect() as db:db.execute("CREATE TRIGGER fail_photo_notice BEFORE INSERT ON patient_notifications WHEN NEW.kind='photo_follow_up_requested' BEGIN SELECT RAISE(ABORT,'Injected notification failure'); END")
        body=self.payload()
        with self.assertRaises(sqlite3.IntegrityError):store.request_photo_followup(self.shared['id'],'doctor-lim',**body)
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM photo_followup_requests').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_notifications').fetchone()[0],0)
            db.execute('DROP TRIGGER fail_photo_notice')
        self.assertEqual(self.request().status_code,201);self.assertEqual(self.request().status_code,201)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_notifications').fetchone()[0],1)

    def test_targeted_request_lookup_cannot_cross_assessments_or_patients(self):
        self.prepare();first=self.request().json();second_share=self.share(self.assessment['id'],'doctor-anita','other-request-doctor');route='/assessment-shares/'+second_share['id']+'/photo-follow-up-request'
        second=self.client.post(route,headers={'X-Demo-Actor':'doctor-anita'},json=self.payload(request_id='another-doctor-photo-request')).json()
        self.assertEqual(len(self.client.get(self.patient_route(),headers=self.patient).json()),2)
        target=self.patient_route()+'?photo_request_id='+first['id'];self.assertEqual(self.client.get(target,headers=self.patient).json(),[first])
        other=self.upload('other-owned-assessment').json()
        self.assertEqual(self.client.get('/assessments/'+other['id']+'/photo-follow-up-requests?photo_request_id='+first['id'],headers=self.patient).status_code,404)
        self.assertEqual(self.client.get(target,headers=self.other).status_code,404)
        self.assertEqual(self.client.get(route,headers=self.doctor).status_code,404)

    def test_requested_followup_uses_existing_link_flow_without_automatic_sharing(self):
        self.prepare();before=self.client.get('/assessments/'+self.assessment['id'],headers=self.patient).json();saved=self.request().json()
        child=self.upload('requested-followup-photo',before['id'],symptoms=self.symptoms(itching='no')).json()
        self.assertEqual(child['follow_up_of'],before['id']);self.assertEqual(child['symptoms']['itching'],'no')
        self.assertEqual(self.client.get('/assessments/'+child['id']+'/sharing-history',headers=self.patient).json(),[])
        self.assertEqual(self.client.get(self.patient_route(),headers=self.patient).json(),[saved])
        current=self.client.get('/assessments/'+before['id'],headers=self.patient).json()
        for key in before:
            if key!='follow_ups':self.assertEqual(current[key],before[key])

    def test_revocation_and_request_are_serialized_and_cancelled_appointment_denied(self):
        self.prepare();store=Store(self.path);body=self.payload()
        def save():
            try:store.request_photo_followup(self.shared['id'],'doctor-lim',**body);return True
            except RuleError as e:self.assertEqual(e.status,404);return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(save);b=pool.submit(store.revoke_share,self.shared['id'],'patient-ava');created=a.result();b.result()
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM photo_followup_requests').fetchone()[0],int(created))
            self.assertEqual(db.execute('SELECT COUNT(*) FROM patient_notifications').fetchone()[0],int(created))
        visit=self.client.post('/bookings',headers=self.patient,json={'slot_id':self.slot['id'],'request_id':'photo-request-visit'}).json()
        linked=self.client.post('/assessments/'+self.assessment['id']+'/link-appointment',headers=self.patient,json={'booking_id':visit['id'],'patient_message':'Fictional','request_id':'photo-request-visit-link'}).json()
        self.client.post('/bookings/'+visit['id']+'/cancel',headers=self.patient)
        result=self.client.post('/assessment-shares/'+linked['id']+'/photo-follow-up-request',headers={'X-Demo-Actor':self.slot['doctor_id']},json=self.payload(request_id='cancelled-visit-photo-request'));self.assertEqual(result.status_code,404)
