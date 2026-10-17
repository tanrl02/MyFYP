import base64
import hashlib
import io
import unittest
from PIL import Image
from ai.prepare_scin_review import checked_properties, pair_match, source_path, crc32c


class ScinPreparationTests(unittest.TestCase):
    def test_crc32c_uses_castagnoli_polynomial_and_checks_server_value(self):
        self.assertEqual(crc32c(b'123456789'), 0xe3069283)
        self.assertEqual(crc32c(b''), 0)
        with self.assertRaises(ValueError): checked_properties(b'123456789', {'x-goog-hash':'crc32c=AAAAAA=='}, 100)

    def test_remote_md5_and_response_length_detect_corruption(self):
        stream = io.BytesIO(); Image.new('RGB',(130,150),'red').save(stream,format='PNG')
        content = stream.getvalue()
        headers = {'x-goog-hash': 'md5='+base64.b64encode(hashlib.md5(content).digest()).decode(), 'Content-Length': str(len(content))}
        self.assertTrue(checked_properties(content, headers, 10000)['server_md5_verified'])
        with self.assertRaises(ValueError): checked_properties(content, {**headers,'x-goog-hash':'md5=AAAAAAAAAAAAAAAAAAAAAA=='},10000)
        with self.assertRaises(ValueError): checked_properties(content, {**headers,'Content-Length': '1'},10000)
        with self.assertRaises(ValueError): checked_properties(content, headers, 1)

    def test_paths_stay_within_expected_public_objects(self):
        self.assertEqual(source_path('dataset/images/-123.png'), '-123.png')
        for value in ('../images/1.png','https://example.com/1.png','dataset/images/../../1.png'):
            with self.assertRaises(ValueError): source_path(value)

    def test_near_match_is_not_reported_as_exact_content(self):
        row={'sha256':'a','pixel_sha256':'b','dhash':'0000000000000000'}
        self.assertEqual(pair_match(row,{**row,'sha256':'c','pixel_sha256':'d','dhash':'000000000000000f'}),'dhash_candidate')
        self.assertIsNone(pair_match(row,{**row,'sha256':'c','pixel_sha256':'d','dhash':'ffffffffffffffff'}))
        self.assertEqual(pair_match(row,{**row,'sha256':'c'}),'exact_pixels')


if __name__ == '__main__': unittest.main()
