from io import BytesIO
import unittest
from unittest.mock import Mock
from PIL import Image
from ai.evaluate_photo_validation import png,skin_variants,verified_bytes,sha,summarise


class PhotoValidationEvaluationTests(unittest.TestCase):
    def test_derived_inputs_are_deterministic_bounded_and_strip_metadata(self):
        image=Image.new('RGB',(1800,1200),(130,85,60))
        exif=Image.Exif();exif[315]='Fictional private metadata';image.info['exif']=exif.tobytes()
        first=skin_variants(image);second=skin_variants(image)
        self.assertEqual(len(first),6)
        for name,variant in first.items():
            body=png(variant);self.assertEqual(body,png(second[name]))
            with Image.open(BytesIO(body)) as decoded:
                self.assertEqual(decoded.mode,'RGB');self.assertFalse(decoded.getexif())
                self.assertLessEqual(max(decoded.size),1024)
        self.assertEqual(first['skin_screenshot'].size,(1024,800))
        self.assertLessEqual(max(first['low_resolution'].size),100)
        bounded=image.copy();bounded.thumbnail((1024,1024),Image.Resampling.LANCZOS)
        self.assertEqual(first['cropped_skin_screenshot'].tobytes(),bounded.tobytes())

    def test_mutated_source_fails_instead_of_being_silently_used(self):
        path=Mock();path.name='fixture.bin';path.read_bytes.return_value=b'original'
        self.assertEqual(verified_bytes(path,sha(b'original')),b'original')
        path.read_bytes.return_value=b'changed'
        with self.assertRaisesRegex(ValueError,'hash mismatch'):verified_bytes(path,sha(b'original'))

    def test_summary_keeps_probes_separate_and_accounts_for_paired_changes(self):
        def row(group,source,accepted,quality=False):
            return {'group':group,'source_id':source,'accepted':accepted,
                    'quality_reasons':['blur'] if quality else [],'disagreement':False}
        rows=[row('original_skin','a',True),row('original_skin','b',True),
              row('dimmer','a',False,True),row('dimmer','b',True),
              row('object','c',False)]
        summary=summarise(rows)
        self.assertEqual(summary['dimmer']['expectation'],'probe')
        self.assertEqual(summary['dimmer']['changed_from_original'],1)
        self.assertEqual(summary['dimmer']['quality_blocked'],1)
        self.assertEqual(summary['object']['content_blocked'],1)
        self.assertNotIn('accuracy',summary)


if __name__=='__main__':unittest.main()
