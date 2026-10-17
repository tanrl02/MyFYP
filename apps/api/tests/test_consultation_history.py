import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow

class ConsultationHistoryTests(unittest.TestCase):
    setUp=workflow.WorkflowTests.setUp
    lim={'X-Demo-Actor':'doctor-lim'}
    anita={'X-Demo-Actor':'doctor-anita'}

    def visit(self,key,start='2026-10-18T10:00:00+08:00',patient='patient-ava',doctor='doctor-lim',status='completed'):
        with Store(self.path).connect() as db:
            db.execute('INSERT INTO slots(id,doctor_id,starts_at,clinic_date,capacity) VALUES(?,?,?,?,2)',
                       ('history-slot-'+key,doctor,start,start[:10]))
            db.execute('INSERT INTO bookings VALUES(?,?,?,?,?,?,?)',
                       (key,patient,'history-slot-'+key,1,status,'2026-10-01T00:00:00+00:00','history-'+key))
        return key

    def history(self,current,actor=None):
        return self.client.get(f'/visits/{current}/history',headers=actor or self.lim)

    def test_patient_doctor_time_and_status_scope_with_frozen_clinical_content(self):
        current=self.visit('current',status='called')
        previous=self.visit('previous','2026-10-17T10:00:00+08:00')
        older=self.visit('older','2026-10-16T10:00:00+08:00')
        self.visit('other-patient','2026-10-17T09:00:00+08:00',patient='patient-noah')
        self.visit('other-doctor','2026-10-17T09:00:00+08:00',doctor='doctor-anita')
        self.visit('future','2026-10-19T09:00:00+08:00')
        self.visit('same-time')
        self.visit('cancelled','2026-10-17T08:00:00+08:00',status='cancelled')
        self.visit('waiting','2026-10-17T07:00:00+08:00',status='waiting')
        self.visit('called','2026-10-17T06:00:00+08:00',status='called')
        store=Store(self.path)
        with store.connect() as db:
            db.execute('INSERT INTO consultation_notes VALUES(?,?,?,?,?,?)',
                       ('history-note',previous,'doctor-lim','Fictional prior findings.','Fictional follow-up.','2026-10-17T03:00:00Z'))
        store.issue_prescription(previous,'doctor-lim',[{'medicine_id':'demo-a','quantity':1,'directions':'Fictional directions only.'}])
        with store.connect() as db:
            db.execute("UPDATE medicines SET name='Changed catalogue',price_cents=999 WHERE id='demo-a'")
        response=self.history(current)
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual([item['visit']['id'] for item in data['items']],[previous,older])
        item=data['items'][0]
        self.assertEqual(item['note']['findings'],'Fictional prior findings.')
        self.assertEqual(item['prescription']['items'][0]['name'],'Demo item A (not medication)')
        for field in ('invoice','price_cents','photo_uri','linked_share','draft','background'):
            self.assertNotIn(field,str(data))
        self.assertIsNone(data['items'][1]['note'])
        self.assertIsNone(data['items'][1]['prescription'])

    def test_current_visit_access_and_role_denials(self):
        current=self.visit('current',status='called')
        for actor in (self.patient,self.other,self.staff):
            self.assertEqual(self.history(current,actor).status_code,403)
        self.assertEqual(self.history(current,self.anita).status_code,404)
        self.assertEqual(self.history('missing').status_code,404)
        for state in ('waiting','cancelled'):
            with Store(self.path).connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(state,current))
            self.assertEqual(self.history(current).status_code,404)
        with Store(self.path).connect() as db:db.execute("UPDATE bookings SET status='completed' WHERE id=?",(current,))
        self.assertEqual(self.history(current).json()['items'],[])

    def test_history_limit_order_restart_and_read_only(self):
        current=self.visit('current','2026-12-31T10:00:00+08:00',status='called')
        for day in range(1,27):
            for hour in (9,10):self.visit(f'past-{day}-{hour}',f'2026-11-{day:02d}T{hour:02d}:00:00+08:00')
        data=self.history(current).json()
        self.assertEqual(data['limit'],50)
        self.assertEqual(len(data['items']),50)
        self.assertEqual(data['items'][0]['visit']['id'],'past-26-10')
        self.assertEqual(data['items'][-1]['visit']['id'],'past-2-9')
        reopened=TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f'/visits/{current}/history',headers=self.lim).json(),data)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM bookings').fetchone()[0],53)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)

    def test_each_doctor_only_gets_own_history_and_offsets_sort_correctly(self):
        lim_current=self.visit('lim-current','2026-10-18T01:00:00+08:00',status='called')
        self.visit('lim-past','2026-10-17T16:30:00+00:00') # 00:30 Malaysia, earlier than selected visit
        anita_current=self.visit('anita-current','2026-10-18T10:00:00+08:00',doctor='doctor-anita',status='called')
        self.visit('anita-past','2026-10-17T09:00:00+08:00',doctor='doctor-anita')
        self.assertEqual([i['visit']['id'] for i in self.history(lim_current).json()['items']],['lim-past'])
        self.assertEqual([i['visit']['id'] for i in self.history(anita_current,self.anita).json()['items']],['anita-past'])
