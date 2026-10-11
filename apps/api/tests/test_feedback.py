from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow

class FeedbackTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    book=workflow.WorkflowTests.book
    def finish(self):
        visit=self.book().json()
        queue={'doctor_id':visit['doctor_id'],'clinic_date':visit['clinic_date']}
        self.client.post('/queue/call-next',headers=self.staff,json=queue)
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        return visit
    def submit(self,visit,actor=None,rating=4,comment='Fictional demo feedback.'):
        return self.client.post(f"/visits/{visit['id']}/feedback",headers=actor or self.patient,json={'rating':rating,'comment':comment})
    def test_shared_own_staff_retry_and_persistence(self):
        visit=self.finish();response=self.submit(visit);self.assertEqual(response.status_code,201)
        saved=response.json();self.assertEqual(self.submit(visit).json()['id'],saved['id'])
        self.assertEqual(self.submit(visit,rating=5).status_code,409)
        self.assertEqual(self.client.get('/feedback',headers=self.patient).json(),[saved])
        self.assertEqual(self.client.get('/feedback',headers=self.other).json(),[])
        self.assertEqual(self.client.get('/feedback',headers=self.staff).json(),[saved])
        self.assertEqual(TestClient(create_app(self.path)).get('/feedback',headers=self.patient).json(),[saved])
        self.assertNotIn('findings',str(self.client.get('/feedback',headers=self.staff).json()))
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='feedback-submitted'").fetchone()[0],1)
    def test_ownership_status_roles_and_input_validation(self):
        visit=self.book().json()
        self.assertEqual(self.submit(visit).status_code,409)
        self.assertEqual(self.submit(visit,self.other).status_code,403)
        for who in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.submit(visit,who).status_code,403)
        self.assertEqual(self.client.get('/feedback',headers={'X-Demo-Actor':'doctor-lim'}).status_code,403)
        for rating in (0,6,True,'5',3.5):self.assertEqual(self.submit(visit,rating=rating).status_code,422)
        self.assertEqual(self.submit(visit,comment='x'*1001).status_code,422)
        self.assertEqual(self.submit({'id':'unknown'}).status_code,404)
        with Store(self.path).connect() as db:
            for status in ('called','cancelled'):
                db.execute('UPDATE bookings SET status=? WHERE id=?',(status,visit['id']))
                db.commit()
                self.assertEqual(self.submit(visit).status_code,409)
    def test_concurrent_submission_and_optional_comment(self):
        visit=self.finish();store=Store(self.path)
        def save(_):return store.submit_feedback(visit['id'],'patient-ava',5,'')['id']
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(len(set(pool.map(save,range(4)))),1)
        self.assertEqual(len(store.feedback('staff-demo')),1)
        self.assertEqual(self.submit(visit,rating=5,comment='   ').json()['comment'],'')
