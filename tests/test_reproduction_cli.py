"""Failed input acquisition is an observable, auditable CLI result."""
from pathlib import Path
import json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]

class ReproductionCliTest(unittest.TestCase):
    def test_missing_raw_files_leave_a_failure_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);raw=base/'raw';raw.mkdir();out=base/'out'
            result=subprocess.run([sys.executable,str(ROOT/'scripts/reproduce.py'),'--raw-dir',str(raw),'--output-dir',str(out)],capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0)
            self.assertTrue((out/'manifest.json').is_file())
            manifest=json.loads((out/'manifest.json').read_text())
            self.assertEqual(manifest['status'],'failed')
            self.assertIn('Required creator CSV missing',manifest['error'])
