import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from recover_official_archive_ranges import recover, validate_range_response


class PublicArchiveRangeTests(unittest.TestCase):
    def test_full_response_is_rejected_even_if_http_successful(self):
        response = SimpleNamespace(status_code=200, headers={})
        with self.assertRaises(ValueError):
            validate_range_response(response, 0, 7, 16)

    def test_wrong_offset_is_rejected_before_any_bytes_are_appended(self):
        response = SimpleNamespace(status_code=206,
                                   headers={'Content-Range': 'bytes 0-7/16'})
        with self.assertRaises(ValueError):
            validate_range_response(response, 8, 15, 16)
        validate_range_response(response, 0, 7, 16)

    def test_wrong_complete_hash_never_promotes_partial_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            partial = folder / 'example.zip.range.part'
            partial.write_bytes(b'bad')
            record = {'filename': 'example.zip', 'bytes': 3,
                      'sha256': hashlib.sha256(b'yes').hexdigest(),
                      'url': 'https://data.mendeley.com/public-files/example/file_downloaded'}
            with self.assertRaisesRegex(RuntimeError, 'failed creator SHA-256'):
                recover(record, folder, 8, 1)
            self.assertTrue(partial.exists())
            self.assertFalse((folder / 'example.zip').exists())
            self.assertFalse((folder / 'example.zip.acquisition.json').exists())

    def test_catalog_cannot_escape_destination_or_request_credentials(self):
        with tempfile.TemporaryDirectory() as folder:
            for name, url in [('.. /../other.zip', 'https://data.mendeley.com/file'),
                              ('valid.zip', 'https://user@data.mendeley.com/file')]:
                record = {'filename': name, 'url': url, 'bytes': 1, 'sha256': '0' * 64}
                with self.assertRaises(ValueError):
                    recover(record, Path(folder), 8, 1)


if __name__ == '__main__':
    unittest.main()
