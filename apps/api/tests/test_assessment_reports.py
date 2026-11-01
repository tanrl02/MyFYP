import json,unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews
from test_predictions import prediction

class AssessmentReportTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    publish=reviews.ReviewTests.publish
    lim=reviews.ReviewTests.lim
    anita=reviews.ReviewTests.anita

    def fixture(self):
        symptoms={'body_area':'Forearm','onset':'3 days','itching':'yes','pain':'no','description':'Fictional 中文 <text>'}
        a=Store(self.path).save_assessment('patient-ava','report-assessment-request','hash',self.photo(),64,64,prediction=prediction(),symptoms=symptoms)
        s=self.share(a['id']).json()
        return a,s,f"/assessments/{a['id']}/report",f"/assessment-shares/{s['id']}/report"

    def test_patient_snapshot_photo_symptoms_ai_and_ownership(self):
        a,s,url,doctor=self.fixture()
        report=self.client.get(url,headers=self.patient);self.assertEqual(report.status_code,200)
        data=report.json();self.assertEqual(data['scope'],'patient');self.assertIsNone(data['source_share_id'])
        for key in ('id','patient_id','photo_uri','symptoms','prediction','created_at','origin'):self.assertEqual(data['assessment'][key],a[key])
        self.assertEqual(data['reviews'],[]);self.assertNotIn('request_id',data['assessment'])
        self.assertEqual(self.client.get(url,headers=self.other).status_code,404)
        for actor in (self.lim,self.staff,{'X-Demo-Actor':'admin-demo'}):self.assertIn(self.client.get(url,headers=actor).status_code,(401,403))
        self.assertEqual(report.headers['cache-control'],'no-store, private')
        self.assertEqual(self.client.get('/assessments/missing/report',headers=self.patient).status_code,404)

    def test_private_drafts_excluded_and_only_published_reviews_in_patient_history(self):
        a,s,url,doctor=self.fixture();base=f"/assessment-shares/{s['id']}"
        body={'doctor_assessment':'PRIVATE DRAFT ONLY','note':'SECRET NOTE','follow_up':'SECRET NEXT','version':0}
        draft=self.client.post(base+'/draft',headers=self.lim,json=body);self.assertEqual(draft.status_code,200,draft.text)
        for endpoint,actor in ((url,self.patient),(doctor,self.lim)):
            report=self.client.get(endpoint,headers=actor);self.assertEqual(report.json()['reviews'],[]);self.assertNotIn('SECRET',report.text);self.assertNotIn('PRIVATE DRAFT',report.text)
        published=self.client.post(base+'/review',headers=self.lim,json={k:body[k] for k in ('doctor_assessment','note','follow_up')}|{'draft_version':draft.json()['version']});self.assertEqual(published.status_code,200,published.text)
        review=self.client.get(url,headers=self.patient).json()['reviews'][0];self.assertEqual(review['id'],published.json()['review']['id']);self.assertFalse(review['access_revoked'])
        self.client.post(base+'/revoke',headers=self.patient)
        retained=TestClient(create_app(self.path)).get(url,headers=self.patient).json()['reviews'][0]
        self.assertTrue(retained['access_revoked']);self.assertEqual(retained['note'],body['note'])
        self.assertEqual(self.client.get(doctor,headers=self.lim).status_code,404)

    def test_doctor_scope_requires_active_share_and_excludes_other_doctors_reviews(self):
        a,s,url,doctor=self.fixture();other=self.share(a['id'],doctor='doctor-anita',request='report-share-anita').json()
        self.assertEqual(self.publish(s['id']).status_code,200)
        self.assertEqual(self.publish(other['id'],actor=self.anita,note='Anita only').status_code,200)
        patient=self.client.get(url,headers=self.patient).json();self.assertEqual(len(patient['reviews']),2)
        own=self.client.get(doctor,headers=self.lim).json();self.assertEqual(own['scope'],'doctor');self.assertEqual(own['source_share_id'],s['id']);self.assertEqual(len(own['reviews']),1);self.assertEqual(own['reviews'][0]['doctor_id'],'doctor-lim');self.assertNotIn('Anita only',json.dumps(own))
        self.assertEqual(self.client.get(doctor,headers=self.anita).status_code,404)
        for actor in (self.patient,self.other,self.staff):self.assertEqual(self.client.get(doctor,headers=actor).status_code,403)
        self.client.post(f"/assessment-shares/{s['id']}/revoke",headers=self.patient)
        self.assertEqual(self.client.get(doctor,headers=self.lim).status_code,404)

    def test_cancelled_appointment_removes_doctor_report_access(self):
        a,s,url,doctor=self.fixture()
        booking=self.client.post('/bookings',headers=self.patient,json={'slot_id':self.slot['id'],'request_id':'report-visit-request'}).json()
        linked=self.client.post(f"/assessments/{a['id']}/link-appointment",headers=self.patient,json={'booking_id':booking['id'],'patient_message':'Fictional','request_id':'report-visit-share'});self.assertEqual(linked.status_code,200,linked.text)
        endpoint=f"/assessment-shares/{linked.json()['id']}/report";actor={'X-Demo-Actor':booking['doctor_id']}
        self.assertEqual(self.client.get(endpoint,headers=actor).status_code,200)
        self.assertEqual(self.client.post(f"/bookings/{booking['id']}/cancel",headers=self.patient).status_code,200)
        self.assertEqual(self.client.get(endpoint,headers=actor).status_code,404)
        self.assertEqual(self.client.get(url,headers=self.patient).status_code,200)

    def test_report_reads_do_not_change_any_saved_table_or_run_inference(self):
        a,s,url,doctor=self.fixture();self.publish(s['id'])
        def snapshot():
            with Store(self.path).connect() as db:return {r[0]:[tuple(x) for x in db.execute('SELECT * FROM "'+r[0]+'" ORDER BY rowid')] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        before=snapshot()
        for _ in range(3):
            self.assertEqual(self.client.get(url,headers=self.patient).status_code,200)
            self.assertEqual(self.client.get(doctor,headers=self.lim).status_code,200)
        self.assertEqual(snapshot(),before)
        self.assertEqual(Store(self.path).assessment(a['id'],'patient-ava')['prediction'],a['prediction'])

    def test_legacy_simulation_is_not_reported_as_ai_prediction(self):
        a=self.upload().json();report=self.client.get(f"/assessments/{a['id']}/report",headers=self.patient).json()
        self.assertEqual(report['assessment']['origin'],'simulation');self.assertNotIn('prediction',report['assessment']);self.assertIsNone(report['assessment']['symptoms']);self.assertIn('No disease prediction',report['assessment']['message'])
