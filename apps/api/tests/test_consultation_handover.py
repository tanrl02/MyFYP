from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store,RuleError
import test_consultations as consultations


class ConsultationHandoverTests(unittest.TestCase):
    setUp=consultations.ConsultationTests.setUp
    book=consultations.ConsultationTests.book
    call=consultations.ConsultationTests.call
    publish=consultations.ConsultationTests.publish
    lim=consultations.ConsultationTests.lim
    anita=consultations.ConsultationTests.anita

    def finish(self,visit,actor=None):
        return self.client.post('/visits/'+visit['id']+'/consultation/finish',headers=actor or self.lim,json={})

    def prepared(self):
        visit=self.book();self.call(visit);self.publish(visit);return visit

    def issue(self,visit):
        return self.client.post('/visits/'+visit['id']+'/prescription',headers=self.lim,json={'items':[{'medicine_id':'demo-a','quantity':2,'directions':'Fictional instructions only.'}]})

    def test_roles_called_state_and_published_note_required(self):
        visit=self.book()
        for actor in (self.patient,self.other,self.staff,self.anita):
            self.assertEqual(self.finish(visit,actor).status_code,403)
        self.assertEqual(self.finish({'id':'missing'}).status_code,404)
        self.assertEqual(self.finish(visit).status_code,409)
        self.call(visit)
        store=Store(self.path)
        store.save_consultation_draft(visit['id'],'doctor-lim','Private unfinished draft','Draft follow-up',0)
        self.assertEqual(self.finish(visit).status_code,409)
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM consultation_handoffs').fetchone()[0],0)
        published=self.client.post('/visits/'+visit['id']+'/consultation',headers=self.lim,
            json={'findings':'Fictional published findings.','follow_up':'Fictional follow-up.','draft_version':1})
        self.assertEqual(published.status_code,200)
        self.assertEqual(self.finish(visit).status_code,200)

    def test_optional_prescription_handoff_visible_without_note_leak_and_staff_still_completes(self):
        visit=self.prepared();saved=self.finish(visit).json()
        self.assertEqual(saved['status'],'called');self.assertIsNotNone(saved['consultation_finished_at'])
        queue=self.client.get('/queue',headers=self.staff,params={'doctor_id':'doctor-lim','clinic_date':visit['clinic_date']}).json()
        queued=next(row for row in queue if row['id']==visit['id'])
        self.assertEqual(queued['consultation_finished_at'],saved['consultation_finished_at'])
        self.assertNotIn('findings',str(queue));self.assertNotIn('Fictional consultation findings.',str(queue))
        self.assertEqual(self.issue(visit).status_code,409)
        self.assertEqual(self.client.post('/queue/'+visit['id']+'/complete',headers=self.lim).status_code,403)
        completed=self.client.post('/queue/'+visit['id']+'/complete',headers=self.staff).json()
        self.assertEqual(completed['status'],'completed')
        self.assertEqual(self.finish(visit).json()['consultation_finished_at'],saved['consultation_finished_at'])
        invoice=self.client.post('/visits/'+visit['id']+'/invoice',headers=self.staff,json={'prescription_id':None}).json()
        self.assertEqual(invoice['total_cents'],3000)
        self.assertEqual(self.client.post('/invoices/'+invoice['id']+'/pay-simulated',headers=self.patient).json()['status'],'paid')
        reopened=TestClient(create_app(self.path)).get('/bookings/'+visit['id']+'/details',headers=self.patient).json()
        self.assertEqual(reopened['visit']['consultation_finished_at'],saved['consultation_finished_at'])
        with Store(self.path).connect() as db:
            handoff=db.execute('SELECT * FROM consultation_handoffs').fetchone()
            self.assertIsNone(handoff['prescription_id']);self.assertIsNotNone(handoff['note_id'])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='consultation-finished'").fetchone()[0],1)

    def test_existing_prescription_retry_and_concurrent_finish_are_idempotent(self):
        visit=self.prepared();rx=self.issue(visit).json();store=Store(self.path)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:store.finish_consultation(visit['id'],'doctor-lim'),range(4)))
        self.assertEqual(len({r['consultation_finished_at'] for r in results}),1)
        self.assertEqual(self.issue(visit).json()['id'],rx['id'])
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT prescription_id FROM consultation_handoffs').fetchone()[0],rx['id'])
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='consultation-finished'").fetchone()[0],1)
        self.assertEqual(store.catalog()[0]['stock'],20)

    def test_finish_vs_new_prescription_serialises(self):
        visit=self.prepared();store=Store(self.path)
        def issue():
            try:return store.issue_prescription(visit['id'],'doctor-lim',[{'medicine_id':'demo-a','quantity':2,'directions':'Fictional instructions only.'}])
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            finishing=pool.submit(store.finish_consultation,visit['id'],'doctor-lim');issuing=pool.submit(issue)
            self.assertIsNotNone(finishing.result()['consultation_finished_at']);rx=issuing.result()
        with store.connect() as db:
            snapshot=db.execute('SELECT prescription_id FROM consultation_handoffs').fetchone()[0]
            if rx==409:self.assertIsNone(snapshot);self.assertEqual(db.execute('SELECT COUNT(*) FROM prescriptions').fetchone()[0],0)
            else:self.assertEqual(snapshot,rx['id'])

    def test_failed_event_rolls_back_handoff_and_legacy_completion_stays_available(self):
        visit=self.prepared();store=Store(self.path)
        def fail(*args):raise RuntimeError('Injected handover event failure')
        store.event=fail
        with self.assertRaises(RuntimeError):store.finish_consultation(visit['id'],'doctor-lim')
        with store.connect() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM consultation_handoffs').fetchone()[0],0)
        self.assertIsNone(Store(self.path).mine('patient-ava')[0]['consultation_finished_at'])
        completed=self.client.post('/queue/'+visit['id']+'/complete',headers=self.staff)
        self.assertEqual(completed.status_code,200)
        self.assertIsNone(completed.json()['consultation_finished_at'])
        self.assertEqual(self.finish(visit).status_code,409)
        self.assertEqual(self.issue(visit).status_code,200)
