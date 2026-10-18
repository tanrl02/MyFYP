from io import BytesIO
import importlib.util
import unittest
from PIL import Image,ImageOps
from ai.enhancement_pipeline import prepare_input,ContrastBlend
from ai.enhancement_evaluation import candidate_guard


class EnhancementInputTests(unittest.TestCase):
    def test_shared_preparation_rotates_strips_metadata_and_bounds_geometry(self):
        original=Image.new('RGB',(1800,900),(80,130,160))
        exif=Image.Exif();exif[274]=6;exif[315]='Fictional private text'
        source=BytesIO();original.save(source,format='JPEG',exif=exif)
        result=prepare_input(source.getvalue())
        with Image.open(BytesIO(result)) as image:
            self.assertEqual(image.size,(800,1600));self.assertEqual(image.mode,'RGB')
            self.assertFalse(image.getexif());self.assertLessEqual(len(result),5*1024*1024)
        with self.assertRaises(ValueError):
            tiny=BytesIO();Image.new('RGB',(8,8)).save(tiny,format='PNG');prepare_input(tiny.getvalue())

    def test_contrast_change_is_deterministic_and_bounded(self):
        image=Image.new('RGB',(16,16));image.putdata([(75+i%16,110+i%25,150+i%33) for i in range(256)])
        first=ContrastBlend()(image);second=ContrastBlend()(image)
        self.assertEqual(first.size,image.size);self.assertEqual(first.tobytes(),second.tobytes())
        self.assertNotEqual(first.tobytes(),image.tobytes())
        self.assertLessEqual(max(abs(a-b) for a,b in zip(first.tobytes(),image.tobytes())),64)

    def test_guard_rejects_accuracy_gain_with_large_recall_loss_or_probe_loss(self):
        control={'validation':{'accuracy':.6,'macro_f1':.55,'per_class':[{'recall':.5}]*8},
                 'lighting_probe_mean_accuracy':.5}
        candidate={'validation':{'accuracy':.65,'macro_f1':.6,'per_class':[{'recall':.52}]*8},
                   'lighting_probe_mean_accuracy':.51}
        self.assertTrue(candidate_guard(control,candidate)['passes'])
        candidate['validation']['per_class']=[{'recall':.3}]+[{'recall':.52}]*7
        self.assertFalse(candidate_guard(control,candidate)['passes'])
        candidate['validation']['per_class']=[{'recall':.52}]*8
        candidate['lighting_probe_mean_accuracy']=.49
        self.assertFalse(candidate_guard(control,candidate)['passes'])


@unittest.skipUnless(importlib.util.find_spec('torch'),'Requires .venv-ai')
class EnhancementTransformTests(unittest.TestCase):
    def test_permanent_correction_is_shared_and_random_jitter_is_train_only(self):
        from ai.compare_models import transforms_for
        train,val=transforms_for({'experiment':'enhancement-v1','enhancement_variant':'contrast_blend'})
        self.assertIsInstance(train.transforms[0],ContrastBlend)
        self.assertIsInstance(val.transforms[0],ContrastBlend)
        self.assertEqual(repr(train.transforms[0]),repr(val.transforms[0]))
        train,val=transforms_for({'experiment':'enhancement-v1','enhancement_variant':'train_jitter'})
        self.assertIn('ColorJitter',repr(train));self.assertNotIn('ColorJitter',repr(val))
        image=Image.new('RGB',(256,256),(100,130,160))
        self.assertEqual(tuple(val(image).shape),(3,224,224))


if __name__=='__main__':unittest.main()
