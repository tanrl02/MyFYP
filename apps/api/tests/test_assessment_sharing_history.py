import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews


class AssessmentSharingHistoryTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    publish=reviews.ReviewTests.publish
    lim=reviews.ReviewTests.lim
    anita=reviews.ReviewTests.anita

    def seed_shares(self,assessment,count=105):
        ids=[str(uuid4()) for _ in range(count)]
        with Store(self.path).connect() as db:
            db.executemany('INSERT INTO assessment_shares(id,assessment_id,patient_id,doctor_id,patient_message,request_id,created_at,revoked_at) VALUES(?,?,?,?,?,?,?,?)',
                [(id,assessment,'patient-ava','doctor-lim','Fictional history fixture','history-'+id,'2005-01-01T00:00:00+00:00','2005-01-02T00:00:00+00:00') for id in ids])
        return ids

    def history(self,assessment,actor=None):
        return self.client.get('/assessments/'+assessment+'/sharing-history',headers=actor or self.patient)

    def test_old_published_and_revoked_shares_survive_global_cutoff(self):
        selected=self.upload().json()['id']
        other=self.upload(request='different-history-photo').json()['id']
        shared=self.share(selected).json()
        reviewed=self.publish(shared['id']).json()['review']
        self.client.post('/assessment-shares/'+shared['id']+'/revoke',headers=self.patient)
        active=self.share(selected,doctor='doctor-anita',request='history-anita-share').json()
        with Store(self.path).connect() as db:
            db.execute("UPDATE assessment_shares SET created_at='2000-01-01T00:00:00+00:00' WHERE assessment_id=?",(selected,))
        self.seed_shares(other)
        global_items=self.client.get('/assessment-shares',headers=self.patient).json()
        self.assertEqual(len(global_items),100)
        self.assertNotIn(selected,[s['assessment_id'] for s in global_items])
        result=self.history(selected)
        self.assertEqual(result.status_code,200)
        rows={s['id']:s for s in result.json()}
        self.assertEqual(set(rows),{shared['id'],active['id']})
        self.assertEqual(rows[shared['id']]['review'],reviewed)
        self.assertIsNotNone(rows[shared['id']]['revoked_at'])
        self.assertIsNone(rows[active['id']]['revoked_at'])
        self.assertIsNone(rows[active['id']]['review'])
        self.assertTrue(all(s['assessment_id']==selected and s['patient_id']=='patient-ava' for s in rows.values()))
        reopened=TestClient(create_app(self.path)).get('/assessments/'+selected+'/sharing-history',headers=self.patient)
        self.assertEqual(reopened.json(),result.json())
        self.assertEqual(self.client.get('/assessment-shares/'+shared['id'],headers=self.lim).status_code,404)
        self.assertEqual(self.client.get('/assessment-shares/'+active['id'],headers=self.anita).status_code,200)

    def test_patient_only_ownership_and_empty_history(self):
        own=self.upload().json()['id'];foreign=self.upload(actor=self.other).json()['id']
        self.assertEqual(self.history(own).json(),[])
        self.assertEqual(self.history(foreign).status_code,404)
        self.assertEqual(self.history(own,self.other).status_code,404)
        self.assertEqual(self.history('missing').status_code,404)
        self.assertEqual(self.history(foreign,self.other).json(),[])
        for actor in (self.staff,self.lim,self.anita):
            self.assertEqual(self.history(own,actor).status_code,403)
        self.assertEqual(self.client.get('/assessments/'+own+'/sharing-history').status_code,422)

    def test_complete_scoped_history_beyond_hundred_is_read_only_and_excludes_drafts(self):
        selected=self.upload().json()['id']
        shared=self.share(selected).json();self.publish(shared['id'])
        with Store(self.path).connect() as db:
            db.execute("UPDATE assessment_shares SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?",(shared['id'],))
        ids=self.seed_shares(selected,205)
        with Store(self.path).connect() as db:
            db.execute('INSERT INTO assessment_review_drafts(share_id,doctor_id,note,follow_up,version,updated_at) VALUES(?,?,?,?,?,?)',
                       (ids[0],'doctor-lim','Private fictional draft must stay hidden','Private follow up',1,'2005-01-01T00:00:00+00:00'))
            before=list(db.iterdump())
        rows=self.history(selected).json()
        self.assertEqual(len(rows),206)
        self.assertEqual([s['id'] for s in rows],sorted(ids,reverse=True)+[shared['id']])
        self.assertEqual(len({s['id'] for s in rows}),206)
        self.assertIsNotNone(rows[-1]['review'])
        self.assertIsNone(rows[-1]['revoked_at'])
        self.assertNotIn('Private fictional draft',str(rows))
        for row in rows:
            self.assertNotIn('draft',row)
            self.assertNotIn('assessment',row)
            self.assertNotIn('photo_uri',row)
        with Store(self.path).connect() as db:self.assertEqual(list(db.iterdump()),before)
