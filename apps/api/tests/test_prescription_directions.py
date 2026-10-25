from concurrent.futures import ThreadPoolExecutor
import unittest
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_care as care


class PrescriptionDirectionsTests(unittest.TestCase):
    setUp=care.CareTests.setUp
    book=care.CareTests.book
    prepare=care.CareTests.prepare
    issue=care.CareTests.issue

    def opened(self):
        visit=self.prepare(completed=False)
        self.rx=self.issue(visit).json()
        return visit

    def body(self, version=1, text='Corrected fictional directions.', reason='Fictional correction reason.'):
        return {'version':version,'reason':reason,'items':[{'medicine_id':'demo-a','directions':text}]}

    def correct(self, visit, body=None, actor=None):
        return self.client.post(f'/visits/{visit}/prescription/directions',headers=actor or self.doctor,json=body or self.body())

    def history(self, visit):
        return self.client.get(f'/visits/{visit}/prescription/directions-history',headers=self.doctor).json()

    def test_correction_changes_only_directions_and_preserves_private_revision_history(self):
        visit=self.opened();store=Store(self.path);stock=store.catalog()
        saved=self.correct(visit).json()
        self.assertEqual(saved['version'],2);self.assertIsNotNone(saved['directions_updated_at'])
        for field in ('id','booking_id','doctor_id','status','created_at','dispensed_at'):
            self.assertEqual(saved[field],self.rx[field])
        self.assertEqual({k:v for k,v in saved['items'][0].items() if k!='directions'},
                         {k:v for k,v in self.rx['items'][0].items() if k!='directions'})
        self.assertEqual(store.catalog(),stock)
        revision,=self.history(visit)['revisions']
        self.assertEqual(revision['previous_directions'][0]['directions'],self.rx['items'][0]['directions'])
        self.assertEqual(revision['directions'][0]['directions'],self.body()['items'][0]['directions'])
        self.assertEqual(revision['reason'],self.body()['reason'])
        own=self.client.get('/care',headers=self.patient).json()[0]['prescription']
        self.assertEqual(own,saved);self.assertNotIn('previous_directions',str(own));self.assertNotIn(self.body()['reason'],str(own))
        self.assertEqual(self.client.get('/care',headers=self.other).json(),[])
        reopened=TestClient(create_app(self.path)).get(f'/visits/{visit}/prescription/directions-history',headers=self.doctor).json()
        self.assertEqual(reopened,self.history(visit))

    def test_roles_validation_and_item_quantity_price_changes_are_rejected(self):
        visit=self.opened()
        wrong={'X-Demo-Actor':'doctor-anita' if self.slot['doctor_id']=='doctor-lim' else 'doctor-lim'}
        for actor in (self.patient,self.other,self.staff,wrong):
            self.assertEqual(self.correct(visit,actor=actor).status_code,403)
            self.assertEqual(self.client.get(f'/visits/{visit}/prescription/directions-history',headers=actor).status_code,403)
        self.assertEqual(self.correct('missing').status_code,404)
        invalid=[self.body(version=0),self.body(version=True),self.body(text=' '),self.body(reason=' '),self.body(text='x'*301)]
        invalid += [self.body()|{'quantity':3},self.body()|{'items':[{'medicine_id':'demo-a','directions':'New','quantity':3}]},
            self.body()|{'items':[{'medicine_id':'demo-b','directions':'New'}]},self.body()|{'items':self.body()['items']*2}]
        for body in invalid:self.assertEqual(self.correct(visit,body).status_code,422)
        self.assertEqual(self.history(visit)['revisions'],[])
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],self.rx)

    def test_retry_stale_version_noop_and_second_revision(self):
        visit=self.opened();saved=self.correct(visit).json()
        self.assertEqual(self.correct(visit).json(),saved)
        self.assertEqual(self.correct(visit,self.body(reason='Another reason')).status_code,409)
        self.assertEqual(self.correct(visit,self.body(version=2)).status_code,409)
        second=self.correct(visit,self.body(version=2,text='Second fictional correction.')).json()
        self.assertEqual(second['version'],3)
        rows=self.history(visit)['revisions']
        self.assertEqual([row['version'] for row in rows],[3,2])
        self.assertEqual(rows[0]['previous_directions'],rows[1]['directions'])

    def test_handover_blocks_new_correction_but_saved_retry_still_returns_current(self):
        visit=self.opened();saved=self.correct(visit).json()
        self.assertEqual(self.client.post(f'/visits/{visit}/consultation',headers=self.doctor,
            json={'findings':'Fictional findings.','follow_up':'Demo.'}).status_code,200)
        self.assertEqual(self.client.post(f'/visits/{visit}/consultation/finish',headers=self.doctor).status_code,200)
        self.assertEqual(self.correct(visit,self.body(version=2,text='Too late')).status_code,409)
        self.assertEqual(self.correct(visit).json(),saved)
        self.assertEqual(len(self.history(visit)['revisions']),1)

    def test_completed_and_billed_visit_is_locked(self):
        visit=self.opened()
        self.client.post(f'/queue/{visit}/complete',headers=self.staff)
        self.assertEqual(self.correct(visit).status_code,409)
        invoice=self.client.post(f'/visits/{visit}/invoice',headers=self.staff).json()
        self.assertEqual(self.correct(visit).status_code,409)
        self.assertEqual(self.client.post(f'/visits/{visit}/invoice',headers=self.staff).json(),invoice)
        self.assertEqual(self.history(visit)['revisions'],[])

    def test_dispensed_called_visit_is_locked(self):
        visit=self.opened()
        self.assertEqual(self.client.post(f'/prescriptions/{self.rx["id"]}/dispense',headers=self.staff).status_code,200)
        self.assertEqual(self.correct(visit).status_code,409)
        self.assertEqual(self.history(visit)['revisions'],[])

    def test_identical_concurrent_corrections_are_one_revision_and_event(self):
        visit=self.opened();store=Store(self.path);body=self.body()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:store.correct_prescription_directions(visit,self.slot['doctor_id'],1,body['reason'],body['items']),range(4)))
        self.assertTrue(all(result==results[0] for result in results))
        self.assertEqual(len(self.history(visit)['revisions']),1)
        with store.connect() as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='prescription-directions-corrected'").fetchone()[0],1)

    def test_competing_corrections_reject_stale_writer(self):
        visit=self.opened();store=Store(self.path)
        def change(text):
            try:return store.correct_prescription_directions(visit,self.slot['doctor_id'],1,text,[{'medicine_id':'demo-a','directions':text}])
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,['First edit.','Different edit.']))
        self.assertEqual(sum(result==409 for result in results),1)
        self.assertEqual(len(self.history(visit)['revisions']),1)

    def test_failed_audit_event_rolls_back_history_and_directions(self):
        visit=self.opened();store=Store(self.path)
        def fail(*args):raise RuntimeError('Injected directions audit failure')
        store.event=fail;body=self.body()
        with self.assertRaises(RuntimeError):store.correct_prescription_directions(visit,self.slot['doctor_id'],1,body['reason'],body['items'])
        self.assertEqual(self.history(visit)['revisions'],[])
        self.assertEqual(self.client.get('/care',headers=self.patient).json()[0]['prescription'],self.rx)

    def test_dispensing_requires_latest_reviewed_revision(self):
        visit=self.opened();self.correct(visit);route=f'/prescriptions/{self.rx["id"]}/dispense'
        store=Store(self.path);stock=store.catalog()
        self.assertEqual(self.client.get(f'/prescriptions/{self.rx["id"]}/stock-sources',headers=self.staff).json()['prescription_version'],2)
        for body in ({},{'prescription_version':1},{'prescription_version':3}):
            self.assertEqual(self.client.post(route,headers=self.staff,json=body).status_code,409)
        self.assertEqual(store.catalog(),stock)
        result=self.client.post(route,headers=self.staff,json={'prescription_version':2})
        self.assertEqual(result.status_code,200);self.assertEqual(result.json()['version'],2)
        self.assertEqual(result.json()['items'][0]['directions'],self.body()['items'][0]['directions'])
        self.assertEqual(self.client.post(route,headers=self.staff,json={'prescription_version':2}).json(),result.json())

    def test_correction_and_old_dispensing_review_cannot_both_succeed(self):
        visit=self.opened();store=Store(self.path);body=self.body()
        def attempt(action):
            try:return action()
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            edit=pool.submit(attempt,lambda:store.correct_prescription_directions(visit,self.slot['doctor_id'],1,body['reason'],body['items']))
            dispense=pool.submit(attempt,lambda:store.dispense(self.rx['id'],'staff-demo',prescription_version=1))
            results=[edit.result(),dispense.result()]
        self.assertEqual(sum(result==409 for result in results),1)
        current=self.client.get('/care',headers=self.patient).json()[0]['prescription']
        self.assertIn((current['status'],current['version']),[('issued',2),('dispensed',1)])

    def test_read_does_not_pair_old_directions_with_a_new_revision(self):
        visit=self.opened();store=Store(self.path);triggered=[];errors=[]
        def interleave(sql):
            if 'prescription_direction_revisions' not in sql or triggered:return
            triggered.append(True)
            try:store.correct_prescription_directions(visit,self.slot['doctor_id'],1,'Read consistency check.',
                [{'medicine_id':'demo-a','directions':'Atomic revised directions.'}])
            except Exception as error:errors.append(error)
        with store.connect() as db:
            db.set_trace_callback(interleave)
            result=store.prescription(db,visit)
        self.assertEqual(errors,[]);self.assertTrue(triggered)
        self.assertEqual((result['version'],result['items'][0]['directions']),(2,'Atomic revised directions.'))
