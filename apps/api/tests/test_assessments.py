import base64
from io import BytesIO
import unittest
from PIL import Image, PngImagePlugin
from fastapi.testclient import TestClient
from app.main import create_app
from app.store import Store
import test_workflow as workflow

class AssessmentTests(unittest.TestCase):
    setUp = workflow.WorkflowTests.setUp

    def photo(self, colour='green'):
        buffer = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Private', 'REMOVE-THIS-METADATA')
        Image.new('RGB', (64, 64), colour).save(buffer, format='PNG', pnginfo=metadata)
        return buffer.getvalue()

    def upload(self, content=None, actor=None, request='photo-request-one'):
        return self.client.post('/assessments', headers=actor or self.patient,
            data={'request_id':request}, files={'photo':('example.png', self.photo() if content is None else content, 'image/png')})

    def test_photo_save_retry_ownership_and_reopen(self):
        response = self.upload()
        self.assertEqual(response.status_code,201)
        saved = response.json()
        self.assertEqual(saved['origin'],'simulation')
        self.assertIn('No disease prediction', saved['message'])
        self.assertEqual(self.upload().json()['id'], saved['id'])
        self.assertEqual(self.upload(self.photo('red')).status_code,409)
        self.assertEqual(len(self.client.get('/assessments',headers=self.patient).json()),1)
        self.assertEqual(self.client.get('/assessments',headers=self.other).json(),[])
        self.assertEqual(self.client.get(f"/assessments/{saved['id']}",headers=self.other).status_code,404)
        self.assertEqual(self.client.get('/assessments',headers=self.staff).status_code,403)
        decoded = base64.b64decode(saved['photo_uri'].split(',')[1])
        self.assertNotIn(b'REMOVE-THIS-METADATA',decoded)
        with Image.open(BytesIO(decoded)) as image:
            self.assertEqual(image.format,'JPEG')
            self.assertFalse(image.getexif())
        reopened = TestClient(create_app(self.path))
        self.assertEqual(reopened.get(f"/assessments/{saved['id']}",headers=self.patient).json()['photo_uri'],saved['photo_uri'])

    def test_reject_invalid_oversized_and_missing_photo(self):
        for content in (b'not an image',b'x'*(5*1024*1024+1)):
            self.assertEqual(self.upload(content).status_code,422)
        buffer=BytesIO()
        Image.new('RGB',(10,10)).save(buffer,format='PNG')
        self.assertEqual(self.upload(buffer.getvalue()).status_code,422)
        self.assertEqual(self.upload(actor=self.staff).status_code,403)
        self.assertEqual(self.client.post('/assessments',headers=self.patient,data={'request_id':'photo-request'}).status_code,422)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),[])

    def test_resize_and_distinct_patient_records(self):
        buffer=BytesIO()
        Image.new('RGB',(2000,1000),'blue').save(buffer,format='JPEG')
        saved=self.upload(buffer.getvalue()).json()
        self.assertEqual((saved['width'],saved['height']),(1600,800))
        other=self.upload(actor=self.other).json()
        self.assertNotEqual(saved['id'],other['id'])
        self.assertEqual(len(Store(self.path).assessments('patient-ava')),1)
