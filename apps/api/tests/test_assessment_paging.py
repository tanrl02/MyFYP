import json
import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow


class AssessmentPagingTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp

    def seed(self,count=1,patient='patient-ava',created='2026-01-01T00:00:00+00:00'):
        ids=[str(uuid4()) for _ in range(count)]
        with Store(self.path).connect() as db:
            db.executemany('INSERT INTO assessments(id,patient_id,request_id,source_hash,photo,width,height,created_at,symptoms_json) VALUES(?,?,?,?,?,?,?,?,?)',
                [(id,patient,'paging-'+id,'fictional-source',b'fictional-photo',64,64,created,json.dumps({'body_area':'Arm','onset':'Demo only','itching':'no','pain':'no','description':'Fictional paging test'})) for id in ids])
        return ids

    def page(self,cursor=None,actor=None):
        return self.client.get('/assessments/history',headers=actor or self.patient,params={} if cursor is None else {'cursor':cursor})

    def test_equal_time_pages_new_arrivals_retries_and_legacy_list(self):
        ids=self.seed(205)
        first=self.page().json()
        self.assertEqual(len(first['items']),100)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),first['items'])
        arrival=self.seed(created='2026-02-01T00:00:00+00:00')[0]
        second=self.page(first['next_cursor']).json()
        self.assertEqual(second,self.page(first['next_cursor']).json())
        third=self.page(second['next_cursor']).json()
        self.assertEqual([len(p['items']) for p in (first,second,third)],[100,100,5])
        collected=[n['id'] for p in (first,second,third) for n in p['items']]
        self.assertEqual(collected,sorted(ids,reverse=True))
        self.assertEqual(len(set(collected)),205)
        self.assertNotIn(arrival,collected)
        self.assertIsNone(third['next_cursor'])
        self.assertEqual(self.page(third['items'][-1]['id']).json(),{'items':[],'next_cursor':None})
        self.assertEqual(self.page().json()['items'][0]['id'],arrival)
        for item in second['items']:
            self.assertNotIn('photo',item)
            self.assertNotIn('photo_uri',item)
            self.assertNotIn('source_hash',item)
            self.assertEqual(item['origin'],'simulation')
            self.assertEqual(item['symptoms']['body_area'],'Arm')
        reopened=TestClient(create_app(self.path)).get('/assessments/history',headers=self.patient,params={'cursor':first['next_cursor']}).json()
        self.assertEqual(reopened,second)

    def test_cursor_validation_roles_and_patient_separation(self):
        own=self.seed()[0];foreign=self.seed(patient='patient-noah')[0]
        for cursor in ('missing',foreign,'','x'*101):
            self.assertEqual(self.page(cursor).status_code,422)
        self.assertEqual(self.page(own,self.other).status_code,422)
        for actor in (self.staff,{'X-Demo-Actor':'doctor-lim'}):
            self.assertEqual(self.page(own,actor).status_code,403)
        self.assertEqual(self.client.get('/assessments/history').status_code,422)
        self.assertEqual([n['id'] for n in self.page(actor=self.other).json()['items']],[foreign])
        self.assertEqual([n['id'] for n in self.page().json()['items']],[own])
        self.assertEqual(self.client.get('/assessments/'+own,headers=self.other).status_code,404)
        self.assertEqual(self.client.get('/assessments/'+own,headers=self.patient).status_code,200)

    def test_empty_and_exact_hundred_have_no_spurious_next_page(self):
        self.assertEqual(self.page().json(),{'items':[],'next_cursor':None})
        self.seed(100)
        first=self.page().json()
        self.assertEqual(len(first['items']),100)
        self.assertIsNone(first['next_cursor'])
        self.seed()
        first=self.page().json()
        self.assertEqual(len(first['items']),100)
        self.assertIsNotNone(first['next_cursor'])
        last=self.page(first['next_cursor']).json()
        self.assertEqual(len(last['items']),1)
        self.assertIsNone(last['next_cursor'])
