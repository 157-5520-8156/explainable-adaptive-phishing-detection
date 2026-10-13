"""Regression checks for malformed URL values reaching offline prediction."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prediction_cli', ROOT / 'scripts/predict_record.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)

class PredictionInputTest(unittest.TestCase):
    def test_invalid_inputs_stop_before_checkpoint_loading(self):
        records = [None, [], {}, {'URL': None}, {'URL': 123}, {'URL': ''},
                   {'URL': 'http://bad host/path'}, {'URL': 'http://example.com:wrong/'},
                   {'URL': 'https://example.com:65536/'}, {'URL': 'file:///etc/passwd'},
                   {'URL': 'https:///path'}, {'URL': 'https://example.com/<tag>'}]
        for record in records:
            with self.subTest(record=record), patch.object(sys, 'argv', ['predict_record.py', '--checkpoint', 'unused.joblib', '--record', 'unused.json']), patch.object(cli.Path, 'read_text', return_value=cli.json.dumps(record)), patch.object(cli.joblib, 'load') as load, patch('sys.stderr'):
                with self.assertRaises(SystemExit) as error:
                    cli.main()
                self.assertEqual(error.exception.code, 2)
                load.assert_not_called()

    def test_valid_inputs_preserve_feature_input_exactly(self):
        for url in ['HTTPS://Example.org/A?Token=AbC', 'example.org/A', 'https://[2001:db8::1]:443/path', ' https://example.org/ ']:
            record = {'URL': url, 'unrelated': 7}
            self.assertIs(cli.validate_record_input(record), record)
            self.assertEqual(record, {'URL': url, 'unrelated': 7})

if __name__ == '__main__':
    unittest.main()
