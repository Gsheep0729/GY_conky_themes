import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rollback_top import rollback, tree_manifest


class TopRollbackTest(unittest.TestCase):
    def make_target(self,root):
        (root/'etc').mkdir();(root/'etc/os-release').write_text('ID=manjaro\n')
        here=root/'root/.local/state/conky-top-sync/test';here.mkdir(parents=True)
        dest=root/'root/.config/conky/classic-tree';dest.mkdir(parents=True)
        previous=here/'previous-classic-tree';previous.mkdir()
        (dest/'start.py').write_text('new')
        (previous/'start.py').write_text('old')
        (here/'result.json').write_text(json.dumps({'installed_manifest':tree_manifest(dest),'previous_manifest':tree_manifest(previous)}))
        untouched=root/'root/.config/other.txt';untouched.write_text('keep')
        return here,dest,untouched

    def test_exact_previous_source_is_restored_without_other_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            here,dest,other=self.make_target(Path(tmp))
            with patch('os.geteuid',return_value=0):rollback(here)
            self.assertEqual((dest/'start.py').read_text(),'old')
            self.assertEqual(other.read_text(),'keep')
            self.assertEqual((here/'rolled-back-top-tree/start.py').read_text(),'new')

    def test_later_user_changes_are_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            here,dest,_=self.make_target(Path(tmp));(dest/'start.py').write_text('user edit')
            with patch('os.geteuid',return_value=0),self.assertRaisesRegex(RuntimeError,'changed since sync'):
                rollback(here)
            self.assertEqual((dest/'start.py').read_text(),'user edit')


if __name__=='__main__':unittest.main()
