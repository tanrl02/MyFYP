import unittest
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store, RuleError
import test_appointment_links as links

class BackgroundTests(unittest.TestCase):
    setUp = links.AppointmentLinkTests.setUp
    book = links.AppointmentLinkTests.book
    lim = links.AppointmentLinkTests.lim
    anita = links.AppointmentLinkTests.anita

    def save(self, actor=None, **changes):
        body = {'allergies':' Fictional allergy A ','medicines':'Demo medicine history','conditions':'Fictional condition','version':0}
        body.update(changes)
        return self.client.post('/patient-background',headers=actor or self.patient,json=body)

    def test_ownership_reopen_validation_and_conflict(self):
        empty = self.client.get('/patient-background',headers=self.patient).json()
        self.assertEqual(empty['version'],0); self.assertIsNone(empty['updated_at'])
        saved = self.save().json()
        self.assertEqual(saved['allergies'],'Fictional allergy A')
        self.assertEqual(self.save().json(),saved)
        self.assertEqual(self.save(allergies='New value').status_code,409)
        self.assertEqual(self.save(conditions='x'*1001).status_code,422)
        self.assertEqual(self.save(version=True).status_code,422)
        for actor in (self.staff,self.lim,self.anita):
            self.assertEqual(self.client.get('/patient-background',headers=actor).status_code,403)
            self.assertEqual(self.save(actor).status_code,403)
        self.assertEqual(self.client.get('/patient-background',headers=self.other).json()['allergies'],'')
        reopened = TestClient(create_app(self.path))
        self.assertEqual(reopened.get('/patient-background',headers=self.patient).json(),saved)
        cleared = self.save(allergies='',medicines='',conditions='',version=1).json()
        self.assertEqual(cleared['version'],2); self.assertEqual(cleared['allergies'],'')

    def test_doctor_visit_access_latest_background_and_note_unchanged(self):
        visit = self.book(); route = f"/visits/{visit['id']}/consultation"
        self.save()
        self.assertEqual(self.client.get(route,headers=self.lim).status_code,404)
        self.client.post('/queue/call-next',headers=self.staff,json={'doctor_id':visit['doctor_id'],'clinic_date':visit['clinic_date']})
        for actor in (self.staff,self.anita,self.other):
            self.assertIn(self.client.get(route,headers=actor).status_code,(403,404))
        self.assertEqual(self.client.get(route,headers=self.lim).json()['background']['version'],1)
        self.assertNotIn('background',self.client.get('/consultations',headers=self.lim).json()[0])
        note = self.client.post(route,headers=self.lim,json={'findings':'Fictional findings','follow_up':'Demo follow-up'}).json()['note']
        self.client.post(f"/queue/{visit['id']}/complete",headers=self.staff)
        self.save(allergies='Updated fictional allergy',version=1)
        opened = self.client.get(route,headers=self.lim).json()
        self.assertEqual(opened['note'],note)
        self.assertEqual(opened['background']['allergies'],'Updated fictional allergy')
        self.assertNotIn('Updated fictional allergy',str(self.client.get('/care',headers=self.staff).json()))

    def test_concurrent_edits_do_not_silently_overwrite(self):
        store = Store(self.path)
        def save(value):
            try:
                return store.save_background('patient-ava',value,'','',0)['version']
            except RuleError as error:
                return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save,['Fictional A','Fictional B'])),[1,409])
