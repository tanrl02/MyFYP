import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import RuleError, Store
import test_consultations as consultations


class ConsultationDraftTests(unittest.TestCase):
    setUp=consultations.ConsultationTests.setUp
    book=consultations.ConsultationTests.book
    call=consultations.ConsultationTests.call
    lim=consultations.ConsultationTests.lim
    anita=consultations.ConsultationTests.anita

    def fixture(self):
        visit=self.book()
        self.assertEqual(self.call(visit).status_code,200)
        return visit,f"/visits/{visit['id']}/consultation/draft"

    def test_partial_draft_validation_retry_reopen_and_private_payloads(self):
        visit,url=self.fixture()
        initial=self.client.get(url,headers=self.lim).json()
        self.assertEqual((initial['version'],initial['findings'],initial['updated_at']),(0,'',None))
        body={'findings':' Fictional unfinished consultation ','follow_up':'','version':0}
        response=self.client.post(url,headers=self.lim,json=body)
        self.assertEqual(response.status_code,200)
        saved=response.json()
        self.assertEqual((saved['version'],saved['findings']),(1,body['findings'].strip()))
        self.assertEqual(self.client.post(url,headers=self.lim,json=body).json(),saved)
        self.assertEqual(TestClient(create_app(self.path)).get(url,headers=self.lim).json(),saved)
        for actor in (self.patient,self.other,self.staff):
            self.assertEqual(self.client.get(url,headers=actor).status_code,403)
            self.assertEqual(self.client.post(url,headers=actor,json=body).status_code,403)
        self.assertEqual(self.client.get(url,headers=self.anita).status_code,404)
        self.assertEqual(self.client.post(url,headers=self.anita,json=body).status_code,404)
        for actor,paths in ((self.patient,('/consultations','/notifications',f"/bookings/{visit['id']}/details",'/care')),
                            (self.staff,('/care','/feedback')),
                            (self.lim,('/consultations',f"/visits/{visit['id']}/consultation",f"/visits/{visit['id']}/history"))):
            for path in paths:
                data=self.client.get(path,headers=actor)
                self.assertEqual(data.status_code,200,path)
                self.assertNotIn(saved['findings'],data.text,path)
                self.assertNotIn('draft',data.text,path)
        for change in ({'findings':'x'*2001},{'follow_up':'x'*1001},{'version':True},{'version':-1},{'version':'1'}):
            self.assertEqual(self.client.post(url,headers=self.lim,json=body|change).status_code,422)
        self.assertEqual(self.client.get(url,headers=self.lim).json(),saved)

    def test_same_and_different_content_concurrent_saves(self):
        visit,url=self.fixture();store=Store(self.path)
        def save(text):
            try:return store.save_consultation_draft(visit['id'],'doctor-lim',text,'',0)['version']
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,['Private one','Private two'])),[1,409])
        saved=self.client.get(url,headers=self.lim).json()
        with ThreadPoolExecutor(max_workers=3) as pool:
            self.assertEqual(list(pool.map(save,[saved['findings']]*3)),[1,1,1])
        self.assertEqual(self.client.get(url,headers=self.lim).json(),saved)
        # An old retry cannot restore its content after a newer save.
        self.assertEqual(store.save_consultation_draft(visit['id'],'doctor-lim','New private text','',1)['version'],2)
        self.assertEqual(save(saved['findings']),409)

    def test_versioned_publication_conversion_exact_retry_and_immutable_result(self):
        visit,url=self.fixture();publish=url.removesuffix('/draft')
        self.client.post(url,headers=self.lim,json={'findings':'Private saved','follow_up':'','version':0})
        body={'findings':'Fictional final findings','follow_up':'Fictional final follow-up','draft_version':0}
        self.assertEqual(self.client.post(publish,headers=self.lim,json=body).status_code,409)
        self.assertEqual(self.client.post(publish,headers=self.lim,json={k:v for k,v in body.items() if k!='draft_version'}).status_code,409)
        for version in (True,-1,'1'):
            self.assertEqual(self.client.post(publish,headers=self.lim,json=body|{'draft_version':version}).status_code,422)
        body['draft_version']=1
        result=self.client.post(publish,headers=self.lim,json=body)
        self.assertEqual(result.status_code,200)
        note=result.json()['note']
        self.assertEqual(note['findings'],body['findings'])
        self.assertEqual(self.client.post(publish,headers=self.lim,json=body).json()['note'],note)
        self.assertEqual(self.client.post(publish,headers=self.lim,json=body|{'findings':'Changed'}).status_code,409)
        self.assertEqual(self.client.get(url,headers=self.lim).status_code,409)
        self.assertEqual(self.client.post(url,headers=self.lim,json={'findings':'Edit','follow_up':'','version':1}).status_code,409)
        with Store(self.path).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM consultation_drafts').fetchone()[0],0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='consultation-published'").fetchone()[0],1)
        self.assertEqual(self.client.get('/consultations',headers=self.patient).json()[0]['note'],note)
        self.assertEqual(self.client.get('/consultations',headers=self.other).json(),[])

    def test_completed_draft_is_read_only_and_waiting_cancelled_missing_denied(self):
        visit=self.book();url=f"/visits/{visit['id']}/consultation/draft"
        body={'findings':'Private before completion','follow_up':'','version':0}
        self.assertEqual(self.client.get(url,headers=self.lim).status_code,404)
        self.assertEqual(self.client.post(url,headers=self.lim,json=body).status_code,404)
        self.call(visit)
        saved=self.client.post(url,headers=self.lim,json=body).json()
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.assertEqual(self.client.get(url,headers=self.lim).json(),saved)
        self.assertEqual(self.client.post(url,headers=self.lim,json=body).status_code,409)
        self.assertEqual(self.client.post(url.removesuffix('/draft'),headers=self.lim,json={'findings':'Final','follow_up':'Later','draft_version':1}).status_code,409)
        self.assertEqual(TestClient(create_app(self.path)).get(url,headers=self.lim).json(),saved)
        self.assertEqual(self.client.get('/consultations',headers=self.patient).json(),[])
        other=self.book(self.other)
        self.client.post(f"/bookings/{other['id']}/cancel",headers=self.other)
        for booking_id in (other['id'],'missing'):
            path=f'/visits/{booking_id}/consultation/draft'
            self.assertEqual(self.client.get(path,headers=self.lim).status_code,404)
            self.assertEqual(self.client.post(path,headers=self.lim,json=body).status_code,404)

    def test_failed_publication_rolls_back_note_event_and_draft_deletion(self):
        visit,_=self.fixture();store=Store(self.path)
        saved=store.save_consultation_draft(visit['id'],'doctor-lim','Private saved','',0)
        def fail(*args):raise RuntimeError('Injected event failure')
        store.event=fail
        with self.assertRaises(RuntimeError):
            store.publish_consultation(visit['id'],'doctor-lim','Final','Later',1)
        self.assertEqual(store.consultation_draft(visit['id'],'doctor-lim'),saved)
        self.assertIsNone(store.consultation(visit['id'],'doctor-lim')['note'])
        with store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE action='consultation-published'").fetchone()[0],0)

    def test_save_publish_race_serializes_without_losing_newer_draft(self):
        visit,_=self.fixture();store=Store(self.path)
        store.save_consultation_draft(visit['id'],'doctor-lim','First','',0)
        def action(kind):
            try:
                if kind=='save':store.save_consultation_draft(visit['id'],'doctor-lim','New private','',1)
                else:store.publish_consultation(visit['id'],'doctor-lim','Confirmed final','Later',1)
                return kind
            except RuleError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes=list(pool.map(action,['save','publish']))
        self.assertEqual(outcomes.count(409),1)
        record=store.consultation(visit['id'],'doctor-lim')
        if record['note']:
            self.assertEqual(record['note']['findings'],'Confirmed final')
        else:
            draft=store.consultation_draft(visit['id'],'doctor-lim')
            self.assertEqual((draft['findings'],draft['version']),('New private',2))

    def test_upgrade_adds_draft_table_without_rewriting_published_note(self):
        visit,_=self.fixture();store=Store(self.path)
        note=store.publish_consultation(visit['id'],'doctor-lim','Existing final','Later')['note']
        with store.connect() as db:db.execute('DROP TABLE consultation_drafts')
        reopened=Store(self.path)
        self.assertEqual(reopened.consultation(visit['id'],'doctor-lim')['note'],note)
        with reopened.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM consultation_drafts').fetchone()[0],0)
