"""Raw-input contracts; these miniature rows are fixtures, not thesis measurements."""
from pathlib import Path
import sys,unittest
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

class RawProtocolTest(unittest.TestCase):
    def test_source_labels_and_legacy_eligibility_are_recovered_without_cache(self):
        from raw_protocol import phi_eligible
        raw=pd.DataFrame({'URL':['https://example.com/a','HTTPS://example.com/a','https://evil.example/x','https://conflict.example/','https://conflict.example/'], 'label':[1,1,0,0,1]})
        rows,audit=phi_eligible(raw)
        self.assertEqual(rows[['URL','y']].to_dict('records'),[{'URL':'https://example.com/a','y':0},{'URL':'https://evil.example/x','y':1}])
        self.assertEqual(audit['conflicting_rows_removed'],2)
        self.assertEqual(audit['duplicate_rows_removed'],1)

    def test_bad_raw_hash_is_rejected_before_processing(self):
        from tempfile import TemporaryDirectory
        from raw_protocol import RAW_CATALOG,verify_raw_directory
        with TemporaryDirectory() as directory:
            first=next(iter(RAW_CATALOG));(Path(directory)/first).write_text('not the creator file')
            with self.assertRaisesRegex(ValueError,'Raw checksum mismatch'):
                verify_raw_directory(directory)
