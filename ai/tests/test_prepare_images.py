import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image

from ai.prepare_images import ROOT, RangeArchive, duplicate_flags, image_properties, selected_rows


class ImagePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = ROOT / 'tmp/image-preparation-tests'
        self.temp_root.mkdir(parents=True, exist_ok=True)

    def test_range_cache_can_read_zip_across_blocks_and_resume_offline(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr('folder/test.jpg', b'example image bytes')
        content = buffer.getvalue()
        calls = []
        def fetch(start, end, size):
            self.assertEqual(size, len(content))
            calls.append((start, end))
            return content[start:end + 1]
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            remote = RangeArchive(temporary, fetch, size=len(content), block_size=32)
            with zipfile.ZipFile(remote) as archive:
                self.assertEqual(archive.read('folder/test.jpg'), b'example image bytes')
            self.assertTrue(calls)
            def offline(*args): raise AssertionError('Unexpected network call')
            resumed = RangeArchive(temporary, offline, size=len(content), block_size=32)
            with zipfile.ZipFile(resumed) as archive:
                self.assertEqual(archive.read('folder/test.jpg'), b'example image bytes')

    def test_truncated_range_is_not_cached(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            remote = RangeArchive(temporary, lambda *args: b'x', size=20, block_size=10)
            with self.assertRaises(ValueError): remote.read(10)
            self.assertEqual(list(Path(temporary).iterdir()), [])

    def test_server_ignoring_range_is_rejected_without_reading_full_archive(self):
        class Response:
            status = 200
            headers = {}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, *args): raise AssertionError('Must reject before reading body')
        with patch('ai.prepare_images.urlopen', return_value=Response()):
            with self.assertRaises(ValueError): RangeArchive.fetch_range(0, 10, 100)

    def test_invalid_seek_rejected(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as temporary:
            remote = RangeArchive(temporary, size=20)
            with self.assertRaises(ValueError): remote.seek(-1)
            with self.assertRaises(ValueError): remote.seek(0, 3)

    def test_source_identity_and_image_integrity_required(self):
        buffer = io.BytesIO()
        Image.new('RGB', (160, 140), 'teal').save(buffer, format='JPEG')
        content = buffer.getvalue()
        properties = image_properties(content, hashlib.md5(content).hexdigest())
        self.assertEqual((properties['width'], properties['height']), (160, 140))
        with self.assertRaises(ValueError): image_properties(content, '0' * 32)
        corrupt = b'not an image'
        with self.assertRaises(OSError): image_properties(corrupt, hashlib.md5(corrupt).hexdigest())

    def test_selection_keeps_source_splits_and_only_explicit_labels(self):
        rules = {'classes': {'acne': {'fitzpatrick': ['acne', 'acne vulgaris']}}}
        rows = [{'label': label, 'md5hash': str(index) * 32, 'partition': 'test'}
                for index, label in enumerate(('acne', 'acne vulgaris', 'rosacea'))]
        selected = selected_rows(rows, rules)
        self.assertEqual(len(selected), 2)
        self.assertTrue(all(row['partition'] == 'test' for row in selected))
        with self.assertRaises(ValueError): selected_rows(rows + [rows[0]], rules)
        with self.assertRaises(ValueError): selected_rows([], rules)

    def test_duplicate_flags_quarantine_both_sides_of_split_and_label_conflict(self):
        rows = [
            {'md5hash': 'a', 'dhash': '0000000000000000', 'pixel_sha256': 'same', 'partition': 'train', 'target_class': 'acne'},
            {'md5hash': 'b', 'dhash': '0000000000000000', 'pixel_sha256': 'same', 'partition': 'test', 'target_class': 'eczema'},
            {'md5hash': 'c', 'dhash': 'ffffffffffffffff', 'pixel_sha256': 'other', 'partition': 'test', 'target_class': 'acne'},
        ]
        flags, pairs = duplicate_flags(rows)
        self.assertEqual(len(pairs), 1)
        for identity in ('a', 'b'):
            self.assertIn('possible_split_leakage', flags[identity])
            self.assertIn('label_conflict_candidate', flags[identity])
        self.assertNotIn('c', flags)


if __name__ == '__main__':
    unittest.main()
