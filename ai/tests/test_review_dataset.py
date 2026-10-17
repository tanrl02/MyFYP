import unittest

from ai.review_dataset import validate_review


class ReviewConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'md5hash': 'a', 'partition': 'train'}, {'md5hash': 'b', 'partition': 'test'}, {'md5hash': 'c', 'partition': 'train'}]
        self.review = {'flagged_image_ids': ['a', 'b'], 'sample_image_ids': ['c'],
                       'confirmed_visual_groups': [{'members': ['a', 'b'], 'cross_split': True}]}

    def test_cross_split_visual_evidence_agrees_with_manifest(self):
        self.assertEqual(len(validate_review(self.review, self.rows)), 3)
        self.review['confirmed_visual_groups'][0]['cross_split'] = False
        with self.assertRaises(ValueError): validate_review(self.review, self.rows)

    def test_sample_overlap_or_missing_image_fails(self):
        self.review['sample_image_ids'] = ['a']
        with self.assertRaises(ValueError): validate_review(self.review, self.rows)
        self.review['sample_image_ids'] = ['missing']
        with self.assertRaises(ValueError): validate_review(self.review, self.rows)

    def test_duplicate_or_unreviewed_group_membership_fails(self):
        with self.assertRaises(ValueError): validate_review(self.review, self.rows + [self.rows[0]])
        self.review['confirmed_visual_groups'].append({'members': ['a', 'c'], 'cross_split': False})
        with self.assertRaises(ValueError): validate_review(self.review, self.rows)


if __name__ == '__main__':
    unittest.main()
