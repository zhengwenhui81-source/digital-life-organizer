"""Independent read-only copy audit tests; all files are temporary synthetic data."""
import hashlib
from pathlib import Path
import tempfile
import unittest
from check_completed_task import check_bytes

class CopyAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='dlo-copy-audit-test-')
        self.root=Path(self.temp.name)
        source=self.root/'source.txt';source.write_text('actual test bytes',encoding='utf-8')
        stat=source.stat();self.baseline={'source.txt':{'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'size':str(stat.st_size),'mtime_ns':str(stat.st_mtime_ns)}}
        self.destination=self.root/'整理结果'/'类别'/'source.txt';self.destination.parent.mkdir(parents=True)
        self.destination.write_bytes(source.read_bytes())
        self.operations=[{'tool':'copy_file','data':{'source':str(source),'destination':str(self.destination)}}]
    def tearDown(self):self.temp.cleanup()
    def test_actual_bytes_and_original_metadata_pass(self):
        checked=check_bytes(self.root,self.baseline,self.operations)
        self.assertEqual(len(checked),1);self.assertEqual(checked[0]['sha256'],self.baseline['source.txt']['sha256'])
    def test_changed_copy_fails(self):
        self.destination.write_bytes(b'wrong')
        with self.assertRaises(AssertionError):check_bytes(self.root,self.baseline,self.operations)
    def test_changed_original_fails(self):
        (self.root/'source.txt').write_bytes(b'changed')
        with self.assertRaises(AssertionError):check_bytes(self.root,self.baseline,self.operations)
    def test_extra_copy_fails(self):
        (self.destination.parent/'extra.txt').write_bytes(b'unexpected')
        with self.assertRaises(AssertionError):check_bytes(self.root,self.baseline,self.operations)
    def test_duplicate_destination_fails(self):
        with self.assertRaises(AssertionError):check_bytes(self.root,self.baseline,self.operations*2)
    def test_missing_copy_fails(self):
        self.destination.unlink()
        with self.assertRaises(AssertionError):check_bytes(self.root,self.baseline,self.operations)

if __name__=='__main__':unittest.main()
