import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import manage


class InstallTest(unittest.TestCase):
    def invoke(self, home, action):
        with patch.object(Path, 'home', return_value=home), patch.object(sys, 'argv', ['manage.py', action]), \
             patch('start.monitors', return_value=[]), patch('start.validate_monitor'), contextlib.redirect_stdout(io.StringIO()):
            manage.main()

    def setup_home(self, home):
        auto=home/'.config/autostart';auto.mkdir(parents=True)
        original=b'[Desktop Entry]\nType=Application\nExec=/test/conky-delay.sh\nName=original\n'
        (auto/'conky-original.desktop').write_bytes(original)
        (auto/'other.desktop').write_bytes(b'[Desktop Entry]\nExec=/test/other-app\n')
        return auto,original

    def test_install_and_exact_autostart_restore_without_touching_other_apps(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);auto,original=self.setup_home(home)
            self.invoke(home,'install')
            self.assertFalse((auto/'conky-original.desktop').exists())
            self.assertTrue((auto/'conky-classic-tree.desktop').exists())
            self.assertIn(str(home/'.config/conky/classic-tree/start.py'),(auto/'conky-classic-tree.desktop').read_text())
            self.invoke(home,'uninstall')
            self.assertEqual((auto/'conky-original.desktop').read_bytes(),original)
            self.assertEqual((auto/'other.desktop').read_bytes(),b'[Desktop Entry]\nExec=/test/other-app\n')
            self.assertFalse((auto/'conky-classic-tree.desktop').exists())
            self.assertTrue((home/'.config/conky/classic-tree/original-template.conf').exists())

    def test_rollback_refuses_to_overwrite_later_user_edit(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);auto,_=self.setup_home(home)
            self.invoke(home,'install')
            changed=b'[Desktop Entry]\nExec=/test/new-user-command\n'
            (auto/'conky-original.desktop').write_bytes(changed)
            with self.assertRaisesRegex(RuntimeError,'refusing to overwrite'):
                self.invoke(home,'uninstall')
            self.assertEqual((auto/'conky-original.desktop').read_bytes(),changed)
            self.assertTrue((auto/'conky-classic-tree.desktop').exists())

    def test_install_does_not_overwrite_an_existing_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);self.setup_home(home)
            self.invoke(home,'install')
            local=home/'.config/conky/classic-tree/config.local.json'
            config=json.loads(local.read_text());config['public_ip']=True;local.write_text(json.dumps(config))
            with self.assertRaisesRegex(RuntimeError,'installation already exists'):
                self.invoke(home,'install')
            self.assertTrue(json.loads(local.read_text())['public_ip'])


if __name__=='__main__':unittest.main()
