import unittest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_reviews as reviews
import test_appointment_links as links
import test_assessment_paging as paging
import test_assessment_sharing_history as sharing


class AssessmentReviewSummaryTests(unittest.TestCase):
    setUp=reviews.ReviewTests.setUp
    photo=reviews.ReviewTests.photo
    upload=reviews.ReviewTests.upload
    share=reviews.ReviewTests.share
    publish=reviews.ReviewTests.publish
    lim=reviews.ReviewTests.lim
    anita=reviews.ReviewTests.anita
    book=links.AppointmentLinkTests.book
    link=links.AppointmentLinkTests.link
    seed=paging.AssessmentPagingTests.seed
    seed_shares=sharing.AssessmentSharingHistoryTests.seed_shares

    def summary(self,id):
        return self.client.get('/assessments/'+id,headers=self.patient).json()['review_summary']

    def test_direct_shares_drafts_publication_revocation_and_persistence(self):
        id=self.upload().json()['id']
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':0})
        first=self.share(id).json()['id']
        store=Store(self.path)
        store.save_review_draft(first,'doctor-lim','Private fictional draft','Private follow up',0)
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':1})
        self.client.post('/assessment-shares/'+first+'/revoke',headers=self.patient)
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':0})
        second=self.share(id,request='summary-second-share').json()['id']
        self.assertEqual(self.publish(second).status_code,200)
        self.share(id,doctor='doctor-anita',request='summary-anita-share')
        self.assertEqual(self.summary(id),{'published_reviews':1,'awaiting_reviews':1})
        self.client.post('/assessment-shares/'+second+'/revoke',headers=self.patient)
        expected={'published_reviews':1,'awaiting_reviews':1}
        self.assertEqual(self.summary(id),expected)
        page=self.client.get('/assessments/history',headers=self.patient).json()['items']
        self.assertEqual(page[0]['review_summary'],expected)
        self.assertNotIn('Private fictional draft',str(page))
        self.assertNotIn('Fictional review only.',str(page))
        reopened=TestClient(create_app(self.path)).get('/assessments/history',headers=self.patient).json()
        self.assertEqual(reopened['items'][0]['review_summary'],expected)

    def test_awaiting_link_requires_current_access_and_published_reviews_remain(self):
        photo=self.upload().json();visit=self.book();grant=self.link(photo,visit).json()
        id=photo['id'];store=Store(self.path)
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':1})
        for status in ('cancelled','missed'):
            with store.connect() as db:db.execute('UPDATE bookings SET status=? WHERE id=?',(status,visit['id']))
            self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':0})
        with store.connect() as db:
            db.execute("UPDATE bookings SET status='waiting' WHERE id=?",(visit['id'],))
            db.execute("UPDATE slots SET doctor_id='doctor-anita' WHERE id=?",(visit['slot_id'],))
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':0})
        with store.connect() as db:
            db.execute("UPDATE slots SET doctor_id='doctor-lim' WHERE id=?",(visit['slot_id'],))
            db.execute("UPDATE bookings SET status='completed' WHERE id=?",(visit['id'],))
        self.assertEqual(self.summary(id),{'published_reviews':0,'awaiting_reviews':1})
        self.assertEqual(self.publish(grant['id']).status_code,200)
        with store.connect() as db:db.execute("UPDATE bookings SET status='cancelled' WHERE id=?",(visit['id'],))
        self.assertEqual(self.summary(id),{'published_reviews':1,'awaiting_reviews':0})

    def test_older_page_complete_counts_scope_privacy_and_read_only(self):
        ids=self.seed(105);target=min(ids);shares=self.seed_shares(target,205)
        foreign=self.seed(patient='patient-noah')[0]
        with Store(self.path).connect() as db:
            db.execute('UPDATE assessment_shares SET revoked_at=NULL WHERE id=?',(shares[0],))
            db.execute('INSERT INTO assessment_reviews(id,share_id,doctor_id,note,follow_up,created_at) VALUES(?,?,?,?,?,?)',
                       (str(uuid4()),shares[1],'doctor-lim','Private historical review body','Demo follow up','2005-01-01T00:00:00+00:00'))
            before=list(db.iterdump())
        first=self.client.get('/assessments/history',headers=self.patient).json()
        self.assertNotIn(target,[a['id'] for a in first['items']])
        last=self.client.get('/assessments/history',headers=self.patient,params={'cursor':first['next_cursor']}).json()
        saved=next(a for a in last['items'] if a['id']==target)
        self.assertEqual(saved['review_summary'],{'published_reviews':1,'awaiting_reviews':1})
        for item in first['items']+last['items']:
            self.assertEqual(set(item['review_summary']),{'published_reviews','awaiting_reviews'})
        self.assertNotIn('Private historical review body',str(first)+str(last))
        noah=self.client.get('/assessments/history',headers=self.other).json()['items']
        self.assertEqual([a['id'] for a in noah],[foreign])
        self.assertEqual(noah[0]['review_summary'],{'published_reviews':0,'awaiting_reviews':0})
        self.assertEqual(self.client.get('/assessments/'+target,headers=self.other).status_code,404)
        doctor=self.client.get('/assessment-shares/'+shares[0],headers=self.lim).json()
        self.assertNotIn('review_summary',doctor['assessment'])
        with Store(self.path).connect() as db:self.assertEqual(list(db.iterdump()),before)
