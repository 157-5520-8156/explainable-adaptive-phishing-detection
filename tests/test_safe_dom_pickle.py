"""The parser interprets data opcodes and never imports/calls pickle globals."""
from pathlib import Path
import sys,unittest,pickle
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

class PassivePickleTest(unittest.TestCase):
    def test_plain_data_round_trip(self):
        from safe_dom_pickle import parse_dom_pickle
        fixture={'https://example.org/':{'label':0,'attrs':{'href':'/x'},'children':['text']}}
        self.assertEqual(parse_dom_pickle(pickle.dumps(fixture,protocol=2)),fixture)

    def test_executable_global_is_rejected(self):
        from safe_dom_pickle import parse_dom_pickle
        with self.assertRaisesRegex(ValueError,'Unapproved global'):
            parse_dom_pickle(b"cos\nsystem\n(S'echo must-not-run'\ntR.")
