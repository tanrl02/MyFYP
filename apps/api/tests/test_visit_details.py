import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow

class VisitDetailsTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book
    def detail(self,visit,actor=None):
        return self.client.get(f"/bookings/{visit['id']}/details",headers=actor or self.patient)
    def linked(self,store,visit):
        image=store.save_assessment('patient-ava','details-assessment','hash',b'photo',32,32)
        return store.link_assessment(image['id'],'patient-ava',visit['id'],'Demo message','details-link-request')
    def test_full_visit_bundle_ownership_and_reopen(self):
        store=Store(self.path);visit=self.book().json();share=self.linked(store,visit)
        store.publish_review(share['id'],visit['doctor_id'],'Fictional review','Fictional review follow-up')
        store.call_next(visit['doctor_id'],visit['clinic_date'],'staff-demo')
        store.publish_consultation(visit['id'],visit['doctor_id'],'Fictional findings','Fictional visit follow-up')
        rx=store.issue_prescription(visit['id'],visit['doctor_id'],[{'medicine_id':'demo-a','quantity':2,'directions':'Fictional directions'}])
        store.complete(visit['id'],'staff-demo');invoice=store.generate_invoice(visit['id'],'staff-demo')
        store.dispense(rx['id'],'staff-demo');store.pay_simulated(invoice['id'],'patient-ava')
        store.submit_feedback(visit['id'],'patient-ava',4,'Fictional feedback')
        response=self.detail(visit);self.assertEqual(response.status_code,200);data=response.json()
        self.assertEqual(data['linked_shares'][0]['review']['note'],'Fictional review')
        self.assertEqual(data['linked_shares'][0]['assessment']['origin'],'simulation')
        self.assertNotIn('photo_uri',data['linked_shares'][0]['assessment'])
        self.assertEqual(data['note']['findings'],'Fictional findings')
        self.assertEqual(data['prescription']['status'],'dispensed');self.assertEqual(data['invoice']['total_cents'],4000)
        self.assertEqual(data['invoice']['status'],'paid');self.assertEqual(data['feedback']['rating'],4)
        self.assertIsNone(data['replacement'])
        self.assertEqual(self.detail(visit,self.other).status_code,404)
        for actor in (self.staff,{'X-Demo-Actor':visit['doctor_id']}):self.assertEqual(self.detail(visit,actor).status_code,403)
        self.assertEqual(self.detail({'id':'missing'}).status_code,404)
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/bookings/{visit['id']}/details",headers=self.patient).json(),data)
    def test_empty_visit_direct_share_exclusion_and_revoked_review(self):
        visit=self.book().json();store=Store(self.path);data=self.detail(visit).json()
        for key in ('note','prescription','invoice','feedback','replacement'):self.assertIsNone(data[key])
        self.assertEqual(data['linked_shares'],[])
        share=self.linked(store,visit)
        store.share_assessment(share['assessment_id'],'patient-ava',visit['doctor_id'],'Direct message','direct-details-key')
        store.publish_review(share['id'],visit['doctor_id'],'Retained review','Retained follow-up')
        store.revoke_share(share['id'],'patient-ava')
        data=self.detail(visit).json();self.assertEqual(len(data['linked_shares']),1)
        self.assertTrue(data['linked_shares'][0]['revoked_at'])
        self.assertEqual(data['linked_shares'][0]['review']['note'],'Retained review')
    def test_rescheduled_visit_links_and_replacement_are_scoped(self):
        visit=self.book().json();store=Store(self.path);share=self.linked(store,visit)
        target=next(s for s in store.slots() if s['doctor_id']==visit['doctor_id'] and s['id']!=visit['slot_id'])
        new=store.reschedule(visit['id'],'patient-ava',target['id'],'details-reschedule')
        old=self.detail(visit).json();self.assertEqual(old['replacement']['id'],new['id']);self.assertEqual(old['linked_shares'],[])
        self.assertEqual(self.detail(new).json()['linked_shares'][0]['id'],share['id'])
        target=next(s for s in store.slots() if s['doctor_id']!=new['doctor_id'])
        changed=store.reschedule(new['id'],'patient-ava',target['id'],'details-doctor-change')
        self.assertTrue(self.detail(new).json()['linked_shares'][0]['revoked_at'])
        self.assertEqual(self.detail(changed).json()['linked_shares'],[])
