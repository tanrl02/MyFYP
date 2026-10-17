from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from ai.freeze_dataset import ROOT, curate, write_frozen


class FreezeDatasetTests(unittest.TestCase):
    def setUp(self):
        self.rules = {'classes': {'a': {'fitzpatrick': ['label a']}, 'b': {'fitzpatrick': ['label b']}}}
        self.rows, self.source = [], []
        for index, (target, split, flag) in enumerate([
            ('a', 'train', ''), ('b', 'train', ''), ('a', 'val', ''), ('b', 'val', ''), ('a', 'test', ''), ('b', 'test', ''),
            ('a', 'train', 'possible_near_duplicate'), ('b', 'test', 'possible_near_duplicate'),
            ('a', 'val', 'label_conflict_candidate'), ('b', 'val', ''),
        ]):
            identity = f'{index:032x}'
            label = 'label ' + target
            self.rows.append({'md5hash': identity, 'sha256': str(index), 'pixel_sha256': str(index), 'local_path': 'example',
                              'target_class': target, 'source_label': label, 'partition': split, 'quality_flags': flag,
                              'width': '200', 'height': '200', 'fst': '1'})
            self.source.append({'md5hash': identity, 'label': label, 'partition': split})
        self.initial = {'flagged_image_ids': [self.rows[i]['md5hash'] for i in (6, 7)], 'sample_image_ids': [], 'confirmed_visual_groups': []}
        self.expanded = {'new_flagged_image_ids': [self.rows[8]['md5hash']], 'additional_class_sample_ids': [self.rows[9]['md5hash']],
                         'manual_exclusions': [{'md5hash': self.rows[9]['md5hash'], 'related_md5hash': self.rows[6]['md5hash'], 'reason': 'visual_overlap'}],
                         'research_freeze_policy': {'exclude_all_mechanical_flags': True, 'manual_exclusions_apply': True, 'keep_original_partitions': True, 'augment_before_split': False}}

    def run_curate(self):
        return curate(self.rows, self.source, self.rules, self.initial, self.expanded)

    def test_exclusions_conserve_rows_and_preserve_source_partitions(self):
        accepted, excluded, mapping = self.run_curate()
        self.assertEqual({split: len(rows) for split, rows in accepted.items()}, {'train': 2, 'val': 2, 'test': 2})
        self.assertEqual(len(excluded), 4)
        self.assertEqual(sum(map(len, accepted.values())) + len(excluded), len(self.source))
        self.assertEqual(mapping, {'a': 0, 'b': 1})
        source = {row['md5hash']: row for row in self.source}
        for split, rows in accepted.items():
            for row in rows: self.assertEqual(source[row['md5hash']]['partition'], split)

    def test_changed_label_or_partition_rejected(self):
        for key, value in [('partition', 'test'), ('source_label', 'wrong')]:
            with self.subTest(key=key):
                rows = deepcopy(self.rows)
                rows[0][key] = value
                with self.assertRaises(ValueError): curate(rows, self.source, self.rules, self.initial, self.expanded)

    def test_cross_split_pixel_duplicate_rejected(self):
        self.rows[4]['pixel_sha256'] = self.rows[0]['pixel_sha256']
        with self.assertRaises(ValueError): self.run_curate()

    def test_unreviewed_flag_or_unanchored_manual_exclusion_rejected(self):
        self.expanded['new_flagged_image_ids'] = []
        with self.assertRaises(ValueError): self.run_curate()
        self.expanded['new_flagged_image_ids'] = [self.rows[8]['md5hash']]
        self.expanded['manual_exclusions'][0]['related_md5hash'] = self.rows[0]['md5hash']
        with self.assertRaises(ValueError): self.run_curate()

    def test_frozen_version_is_idempotent_and_refuses_overwrite(self):
        temporary_root = ROOT / 'tmp/freeze-tests'
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as temporary:
            output = Path(temporary) / 'version'
            files = {'train.csv': b'original\n', 'test.csv': b'held out\n'}
            write_frozen(output, files)
            write_frozen(output, files)
            with self.assertRaises(ValueError): write_frozen(output, {**files, 'train.csv': b'changed\n'})
            self.assertEqual((output / 'train.csv').read_bytes(), b'original\n')


if __name__ == '__main__':
    unittest.main()
