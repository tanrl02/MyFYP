import unittest
from ai.audit_scin_expansion import POSITIVE, screen_case


def fixture(weights="{'Eczema': 0.8, 'Psoriasis': 0.2}", grades=(POSITIVE,)):
    case = {'image_1_path': 'dataset/images/1.png', 'image_2_path': 'dataset/images/2.png', 'image_3_path': ''}
    labels = {'weighted_skin_condition_label': weights, **{
        f'dermatologist_gradable_for_skin_condition_{i}': grades[i-1] if i <= len(grades) else '' for i in (1, 2, 3)}}
    return case, labels


class ScinExpansionTests(unittest.TestCase):
    def test_grade_disagreement_is_not_hidden_by_one_positive(self):
        case, labels = fixture(grades=(POSITIVE, 'NO_IMAGE_QUALITY_INSUFFICIENT'))
        result = screen_case(case, labels, set())
        self.assertTrue(result['initial_screen'])
        self.assertTrue(result['gradable_disagreement'])
        self.assertFalse(result['strict_screen'])

    def test_raters_are_case_level_and_multiple_views_not_independent_cases(self):
        case, labels = fixture(grades=(POSITIVE, POSITIVE))
        result = screen_case(case, labels, set())
        self.assertTrue(result['multiple_graders_strict'])
        self.assertEqual(result['positive_graders'], 2)
        self.assertEqual(len(result['image_references']), 2)
        self.assertTrue(screen_case(*fixture(), set())['strict_screen'])
        self.assertFalse(screen_case(*fixture(), set())['multiple_graders_strict'])

    def test_ties_shared_paths_and_invalid_paths_cannot_enter_strict_pool(self):
        self.assertFalse(screen_case(*fixture("{'Eczema': 0.5, 'Psoriasis': 0.5}"), set())['strict_screen'])
        case, labels = fixture()
        self.assertFalse(screen_case(case, labels, {'dataset/images/1.png'})['strict_screen'])
        case['image_2_path'] = '../images/2.png'
        self.assertFalse(screen_case(case, labels, set())['strict_screen'])


if __name__ == '__main__': unittest.main()
