import unittest
from ai.audit_dermnet import aggregate


class DermnetAuditTests(unittest.TestCase):
    def test_counts_keep_category_and_split_and_do_not_claim_content_duplicates(self):
        result = aggregate([
            {'name': 'train/Eczema Photos/a.jpg', 'totalBytes': 100},
            {'name': 'test/Eczema Photos/a.jpg', 'totalBytes': 200},
            {'name': 'train/Acne and Rosacea Photos/b.jpg', 'totalBytes': 50}])
        self.assertEqual(result['file_entries'], 3)
        self.assertEqual(result['categories']['Eczema Photos'], {'train': 1, 'test': 1})
        self.assertEqual(result['bytes_by_split'], {'train': 150, 'test': 200})
        self.assertEqual(result['basenames_shared_between_train_test'], 1)
        self.assertEqual(result['category_basenames_shared_between_train_test'], 1)
        self.assertEqual(result['same_category_name_size_pairs_by_category'], {})
        self.assertTrue(result['basename_check_is_not_content_duplicate_check'])
        self.assertNotIn('acne', result['categories'])  # A mixed group is not relabelled.
        same_size = aggregate([
            {'name': 'train/Acne and Rosacea Photos/a.jpg', 'totalBytes': 100},
            {'name': 'test/Acne and Rosacea Photos/a.jpg', 'totalBytes': 100}])
        self.assertEqual(same_size['same_category_name_size_pairs_by_category'], {'Acne and Rosacea Photos': 1})

    def test_duplicate_paths_and_unexpected_layout_fail(self):
        row = {'name': 'train/Eczema Photos/a.jpg', 'totalBytes': 100}
        with self.assertRaises(ValueError): aggregate([row, row])
        for name in ('../Eczema Photos/a.jpg', '/train/Eczema Photos/a.jpg',
                     'validation/Eczema Photos/a.jpg', 'train/Eczema Photos/script.py'):
            with self.assertRaises(ValueError): aggregate([{'name': name, 'totalBytes': 100}])


if __name__ == '__main__': unittest.main()
