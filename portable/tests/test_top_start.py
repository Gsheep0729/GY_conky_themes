import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from top_start import load_fresh, stop_children
from top_tree import layout, make_config, visible
from classic import TEMPLATE
from conky_tree import config


class StandaloneTopTest(unittest.TestCase):
    def test_cache_must_be_fresh_and_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'state.json'
            self.assertIsNone(load_fresh(p,now=100))
            for payload in ['bad','[]','{}','{"sample_unix":80}','{"sample_unix":101}']:
                p.write_text(payload);self.assertIsNone(load_fresh(p,now=100))
            p.write_text(json.dumps({'sample_unix':99,'memory_used':123}))
            self.assertEqual(load_fresh(p,now=100)['memory_used'],123)

    def test_layout_choice_is_explicit_and_old_default_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'config.json'
            self.assertEqual(config(p)['layout'],'classic')
            p.write_text('{"layout":"top"}')
            self.assertEqual(config(p)['layout'],'top')
            p.write_text('{"layout":"bad"}')
            with self.assertRaises(ValueError):config(p)

    def test_owned_children_terminate_and_timeout_is_cleaned(self):
        first=Mock();first.poll.return_value=None
        second=Mock();second.poll.return_value=None
        second.wait.side_effect=[subprocess.TimeoutExpired('test',4),0]
        stop_children([first,second])
        first.terminate.assert_called_once();second.terminate.assert_called_once()
        first.kill.assert_not_called();second.kill.assert_called_once()

    def test_production_config_has_no_preview_class_and_explicit_target_backend(self):
        def measure(s):return len(visible(s))*10
        spec=layout({},3200,2,measure)
        text=make_config(TEMPLATE,Path('/tmp/top.text'),spec,0,30,72,preview=False,xwayland_backend=True)
        self.assertIn("own_window_class = 'ConkyTopTree'",text)
        self.assertNotIn('ConkyTopPreview',text)
        self.assertIn('out_to_x = true',text);self.assertIn('out_to_wayland = false',text)
        self.assertIn("size=7.5",text);self.assertIn('${catp /tmp/top.text}',text)


if __name__=='__main__':unittest.main()
