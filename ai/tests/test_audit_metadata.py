import unittest

from ai.audit_metadata import audit_fitz, audit_scin, candidate_table, index_unique, leading_label, literal_weights


class MetadataAuditTests(unittest.TestCase):
    def test_weight_parser_rejects_invalid_values(self):
        for value in ("[]", "{'Acne': True}", "{'Acne': 1e999}", "{'Acne': -1}", "{1: 0.5}", "__import__('os')"):
            with self.subTest(value=value), self.assertRaises((ValueError, SyntaxError)):
                literal_weights(value)
        self.assertEqual(literal_weights(''), {})
        self.assertEqual(literal_weights('{}'), {})
        self.assertEqual(literal_weights("{'Acne': 0, 'Eczema': 0.8}"), {'Eczema': 0.8})

    def test_ties_are_not_unique_leaders(self):
        self.assertIsNone(leading_label({'Acne': 0.5, 'Eczema': 0.5})[0])
        self.assertEqual(leading_label({'Acne': 0.6, 'Eczema': 0.4})[0], 'Acne')

    def test_duplicate_or_missing_case_ids_fail(self):
        for rows in ([{'case_id': 'a'}, {'case_id': 'a'}], [{'case_id': ''}]):
            with self.assertRaises(ValueError):
                index_unique(rows, 'case_id')
        with self.assertRaises(ValueError):
            audit_scin([{'case_id': 'a'}], [], {})

    def test_screen_counts_cases_once_and_requires_grade_and_image(self):
        cases, labels = [], []
        for identity, images, grade in (
            ('a', ['one', 'two'], 'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT'),
            ('b', ['three'], 'NO_IMAGE_QUALITY_INSUFFICIENT'),
            ('c', [], 'DEFAULT_YES_IMAGE_QUALITY_SUFFICIENT'),
        ):
            cases.append({'case_id': identity, 'release': 'test', **{
                f'image_{i}_path': images[i - 1] if i <= len(images) else '' for i in (1, 2, 3)}})
            labels.append({'case_id': identity, 'weighted_skin_condition_label': "{'Acne': 0.6, 'Eczema': 0.4}", **{
                f'dermatologist_gradable_for_skin_condition_{i}': grade if i == 1 else '' for i in (1, 2, 3)}})
        summary, counts = audit_scin(cases, labels, {'minimum_top_weight': 0.6, 'minimum_margin': 0.2})
        self.assertEqual(summary['screened_cases'], 1)
        self.assertEqual(counts['Acne']['screened_image_references'], 2)
        self.assertEqual(counts['Acne']['unique_top_cases'], 3)

    def test_fitz_flags_cross_split_duplicates(self):
        rows = [{'label': 'acne', 'md5hash': 'same', 'url': 'same-url', 'partition': split} for split in ('train', 'test')]
        summary, counts = audit_fitz(rows, corrected=True)
        self.assertEqual(summary['repeated_md5_rows'], 1)
        self.assertEqual(summary['cross_split_repeated_md5'], 1)
        self.assertEqual(summary['cross_split_repeated_literal_urls'], 1)
        self.assertEqual(counts['acne']['train'], 1)
        with self.assertRaises(ValueError):
            audit_fitz([{**rows[0], 'partition': 'unknown'}], corrected=True)

    def test_candidate_mapping_combines_only_explicit_aliases(self):
        rules = {'classes': {'acne': {'scin': ['Acne'], 'fitzpatrick': ['acne', 'acne vulgaris']}}}
        counts = {'acne': {'images': 2, 'train': 2}, 'acne vulgaris': {'images': 3, 'test': 3}, 'rosacea': {'images': 99}}
        row = candidate_table(rules, {}, counts, counts)[0]
        self.assertEqual(row['fitz_c_images'], 5)
        self.assertEqual(row['fitz_c_train'], 2)
        self.assertEqual(row['fitz_c_test'], 3)


if __name__ == '__main__':
    unittest.main()
