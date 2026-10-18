import importlib.util
import unittest

HAS_TORCH=importlib.util.find_spec('torch') is not None
if HAS_TORCH:
    from ai.check_upload_preprocessing import transition_counts


@unittest.skipUnless(HAS_TORCH,'Requires .venv-ai')
class UploadTransitionTests(unittest.TestCase):
    def test_correctness_transitions_distinguish_wrong_to_wrong_changes(self):
        result=transition_counts([0,1,2,3],[0,0,2,2],[1,1,3,2])
        self.assertEqual(result,{'predictions_changed':3,'correct_to_wrong':2,'wrong_to_correct':1})

    def test_unpaired_or_empty_predictions_are_rejected(self):
        for args in (([],[],[]),([0],[0],[]),([0,1],[0],[0])):
            with self.assertRaises(ValueError):transition_counts(*args)


if __name__=='__main__':unittest.main()
