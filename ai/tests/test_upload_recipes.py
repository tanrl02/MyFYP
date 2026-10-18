from io import BytesIO
import unittest
from PIL import Image,ImageOps
from ai.upload_recipes import render_variants,encode
from app.store import RuleError


class UploadRecipeTests(unittest.TestCase):
    def test_orientation_metadata_stripping_and_lossless_pixels(self):
        source=Image.new('RGB',(64,40),(80,135,190))
        exif=Image.Exif();exif[274]=6;exif[315]='Fictional private metadata'
        stream=BytesIO();source.save(stream,format='JPEG',exif=exif,icc_profile=b'fictional-profile')
        content=stream.getvalue()
        with Image.open(BytesIO(content)) as original:expected=ImageOps.exif_transpose(original).convert('RGB')
        variants,size=render_variants(content)
        self.assertEqual(size,(40,64))
        for name,body in variants.items():
            with Image.open(BytesIO(body)) as image:
                self.assertEqual(image.size,size);self.assertEqual(image.mode,'RGB')
                self.assertFalse(image.getexif());self.assertNotIn('icc_profile',image.info)
                if name=='png_lossless':self.assertEqual(image.tobytes(),expected.tobytes())

    def test_shared_resize_and_actual_production_constraints(self):
        stream=BytesIO();Image.new('RGB',(1800,900)).save(stream,format='PNG')
        variants,size=render_variants(stream.getvalue());self.assertEqual(size,(1600,800))
        for body in variants.values():
            with Image.open(BytesIO(body)) as image:self.assertEqual(image.size,size)
        for content in (b'not an image',b'x'*(5*1024*1024+1)):
            with self.assertRaises(RuleError):render_variants(content)
        with self.assertRaises(ValueError):encode(Image.new('RGB',(32,32)),'unregistered')


if __name__=='__main__':unittest.main()
