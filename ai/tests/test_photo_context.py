import unittest
from PIL import Image
from ai.photo_context_experiment import whole_view,score_pass,guard,RULES,cases


class PhotoContextTests(unittest.TestCase):
    def test_whole_view_preserves_edge_context_and_aspect_ratio(self):
        image=Image.new('RGB',(1000,500),'red')
        output=whole_view(image)
        self.assertEqual(output.size,(224,224))
        self.assertEqual(output.getpixel((0,0)),(127,127,127))
        self.assertEqual(output.getpixel((0,112)),(255,0,0))
        self.assertEqual(output.getpixel((223,112)),(255,0,0))

    def test_fixed_cutoffs_and_guard_cannot_trade_skin_loss_for_negative_gain(self):
        self.assertTrue(score_pass(.25,.23));self.assertFalse(score_pass(.21,.1))
        self.assertFalse(score_pass(.25,.245))
        def summary(skin,screen):
            return {'skin':{'accepted':skin},'object':{'accepted':0},
                    'prior_screen':{'accepted':screen},'novel_screen':{'accepted':screen},'pattern':{'accepted':1}}
        data={'baseline':summary(18,17),'whole_frame':summary(17,0)}
        self.assertFalse(guard(data,'whole_frame','development')['passes'])
        data['whole_frame']=summary(18,0)
        self.assertTrue(guard(data,'whole_frame','development')['passes'])
        data['whole_frame']['object']['accepted']=1
        self.assertFalse(guard(data,'whole_frame','development')['passes'])

    def test_frozen_split_is_grouped_and_has_all_expected_cases(self):
        fixtures=cases();self.assertEqual(len(fixtures),128)
        source_splits={}
        for fixture in fixtures:
            if fixture['group'] in ('skin','prior_screen','novel_screen'):
                source_splits.setdefault(fixture['source_id'],set()).add(fixture['split'])
        self.assertEqual(len(source_splits),37)
        self.assertTrue(all(len(splits)==1 for splits in source_splits.values()))
        for split,expected in (('development',18),('validation',19)):
            self.assertEqual(sum(row['split']==split and row['group']=='skin' for row in fixtures),expected)
        self.assertEqual(tuple(RULES),('baseline','whole_frame','whole_frame_context'))


if __name__=='__main__':unittest.main()
