from io import BytesIO
from unittest.mock import patch
import unittest
from PIL import Image,ImageFilter,ImageDraw
from fastapi.testclient import TestClient
from app.main import create_app
from app.photo_checks import check_photo,photo_quality
from app.store import RuleError
import test_workflow as workflow


class FixedScreener:
    def __init__(self,status='likely_skin'):self.status=status;self.calls=0
    def classify(self,image,key):self.calls+=1;return {'status':self.status}


class PhotoCheckTests(unittest.TestCase):
    def setUp(self):
        workflow.WorkflowTests.setUp(self)
        self.screener=FixedScreener()
        self.client=TestClient(create_app(self.path,photo_checker=lambda body:check_photo(body,self.screener)))

    def photo(self,kind='detail'):
        image=Image.new('RGB',(384,384),(160,115,85))
        if kind=='detail':
            draw=ImageDraw.Draw(image)
            for x in range(0,384,8):draw.line((x,0,x,383),fill=(115,75,55),width=2)
        elif kind=='black':image=Image.new('RGB',image.size,'black')
        elif kind=='white':image=Image.new('RGB',image.size,'white')
        elif kind=='blur':
            draw=ImageDraw.Draw(image);draw.rectangle((60,60,260,260),fill=(90,60,40))
            image=image.filter(ImageFilter.GaussianBlur(25))
        elif kind=='tiny':image=image.resize((80,80))
        buffer=BytesIO();image.save(buffer,format='PNG');return buffer.getvalue()

    def check(self,body=None,actor=None):
        return self.client.post('/photo-check',headers=actor or self.patient,
            files={'photo':('photo.png',body or self.photo(),'image/png')})

    def save(self,body):
        return self.client.post('/assessments',headers=self.patient,data={'request_id':'checked-photo-request'},
            files={'photo':('photo.png',body,'image/png')})

    def test_preflight_does_not_save_and_save_rechecks_actual_bytes(self):
        response=self.check();self.assertEqual(response.status_code,200)
        self.assertTrue(response.json()['accepted']);self.assertEqual(self.screener.calls,1)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),[])
        self.assertEqual(self.save(self.photo('black')).status_code,422)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),[])
        saved=self.save(self.photo());self.assertEqual(saved.status_code,201)
        self.assertIn('No disease prediction',saved.json()['message']);self.assertEqual(self.screener.calls,2)
        self.assertEqual(self.client.get('/assessments',headers=self.other).json(),[])

    def test_bad_quality_blocks_before_semantic_inference(self):
        for kind in ('black','white','blur','tiny','flat'):
            result=self.check(self.photo(kind)).json()
            self.assertFalse(result['accepted'],kind);self.assertTrue(result['reasons'])
            self.assertEqual(result['skin_content'],'not_checked')
        self.assertEqual(self.screener.calls,0)

    def test_uncertain_and_non_skin_cannot_be_saved(self):
        for status in ('uncertain','not_skin'):
            self.screener.status=status
            self.assertFalse(self.check().json()['accepted'])
            self.assertEqual(self.save(self.photo()).status_code,422)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),[])

    def test_corrupt_oversized_role_and_model_unavailability(self):
        self.assertEqual(self.check(b'not an image').status_code,422)
        self.assertEqual(self.check(b'x'*(5*1024*1024+1)).status_code,422)
        self.assertEqual(self.check(actor=self.staff).status_code,403)
        self.assertEqual(self.check(actor={'X-Demo-Actor':'doctor-lim'}).status_code,403)
        real=TestClient(create_app(self.path))
        with patch('app.photo_checks.get_screener',side_effect=RuntimeError('missing')):
            response=real.post('/photo-check',headers=self.patient,files={'photo':('x.png',self.photo(),'image/png')})
            self.assertEqual(response.status_code,503)
            response=real.post('/assessments',headers=self.patient,data={'request_id':'missing-model-request'},files={'photo':('x.png',self.photo(),'image/png')})
            self.assertEqual(response.status_code,503)
        self.assertEqual(self.client.get('/assessments',headers=self.patient).json(),[])

    def test_dark_but_detailed_image_is_not_rejected_for_skin_colour(self):
        image=Image.new('RGB',(384,384),(22,16,12));draw=ImageDraw.Draw(image)
        for x in range(0,384,8):draw.line((x,0,x,383),fill=(45,34,26),width=2)
        self.assertEqual(photo_quality(image)[0],[])


if __name__=='__main__':unittest.main()
