import copy,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from plasma_compat import connector_rectangle,logical_rectangles,validate_fixed
from start import validate_monitor,make_config
from conky_tree import DEFAULTS


def config():
    return {'outputs':[{'name':'eDP-1','connected':True,'enabled':True,'pos':{'x':2560,'y':440},'scale':2,'rotation':1,'currentModeId':'internal','modes':[{'id':'internal','size':{'width':3200,'height':2000}}]}, {'name':'DP-1','connected':True,'enabled':True,'pos':{'x':0,'y':0},'scale':1,'rotation':1,'currentModeId':'external','modes':[{'id':'external','size':{'width':2560,'height':1440}}]}]}


def heads(internal_first=False,factor=1):
    values=[(0,0,2560,1440),(2560,440,1600,1000)]
    if internal_first:values.reverse()
    return [dict(index=i,**dict(zip(['x','y','width','height'],[v*factor for v in rect]))) for i,rect in enumerate(values)]


class PlasmaTest(unittest.TestCase):
    def test_native_KScreen_geometry_and_global_XWayland_scale(self):
        self.assertEqual(connector_rectangle(config(),'eDP-1',heads()),(2560,440,1600,1000))
        self.assertEqual(connector_rectangle(config(),'eDP-1',heads(factor=2)),(5120,880,3200,2000))

    def test_fixed_zero_refuses_external_without_switching(self):
        cfg=DEFAULTS.copy()
        with patch('plasma_compat.run',return_value=json.dumps(config())):
            with self.assertRaisesRegex(RuntimeError,'固定0号'):validate_fixed(cfg,heads())
        self.assertEqual(cfg['monitor_index'],0)

    def test_fixed_zero_accepts_internal_only_when_it_is_index_zero(self):
        with patch('plasma_compat.run',return_value=json.dumps(config())):
            self.assertEqual(validate_fixed(DEFAULTS,heads(True))['index'],0)

    def test_disabled_internal_never_falls_back(self):
        d=config();d['outputs'][0]['enabled']=False
        with self.assertRaisesRegex(RuntimeError,'disabled or absent'):connector_rectangle(d,'eDP-1',heads())

    def test_bad_data_and_missing_tool_stop(self):
        for value in [None,'not JSON','{}']:
            with self.subTest(value=value),patch('plasma_compat.run',return_value=value):
                with self.assertRaises(RuntimeError):validate_fixed(DEFAULTS,heads())

    def test_unknown_geometry_does_not_guess(self):
        h=heads();h[0]['width']=3000
        with self.assertRaisesRegex(RuntimeError,'Cannot uniquely'):connector_rectangle(config(),'eDP-1',h)

    def test_mirrored_outputs_are_rejected(self):
        d=config();d['outputs'][1]=copy.deepcopy(d['outputs'][0]);d['outputs'][1]['name']='DP-1'
        h=heads();h[0]=copy.deepcopy(h[1]);h[0]['index']=0
        with self.assertRaisesRegex(RuntimeError,'Mirrored'):connector_rectangle(d,'eDP-1',h)

    def test_negative_positions_normalize_and_rotation_is_respected(self):
        d=config();d['outputs'][0]['pos']['x']=0;d['outputs'][1]['pos']['x']=-2560
        self.assertEqual(connector_rectangle(d,'eDP-1',heads()),(2560,440,1600,1000))
        d=config();d['outputs']=d['outputs'][:1];d['outputs'][0]['rotation']=2;d['outputs'][0]['scale']=1.25
        self.assertEqual(logical_rectangles(d)['eDP-1'],(0,0,1600,2560))

    def test_Plasma_fallback_integrates_without_changing_fixed_index(self):
        env={'XDG_SESSION_TYPE':'wayland','XDG_CURRENT_DESKTOP':'KDE'}
        with patch.dict(os.environ,env),patch('start.run',return_value='XWAYLAND0 connected 2560x1440+0+0'),patch('plasma_compat.run',return_value=json.dumps(config())):
            self.assertEqual(validate_monitor(DEFAULTS,heads(True))['index'],0)
            with self.assertRaisesRegex(RuntimeError,'固定0号'):validate_monitor(DEFAULTS,heads())

    def test_target_config_explicitly_uses_XWayland_backend(self):
        text=make_config(DEFAULTS,{},Path(__file__).resolve().parents[1],Path('/tmp/state.json'))
        self.assertIn('out_to_x = true',text);self.assertIn('out_to_wayland = false',text)
        self.assertIn('xinerama_head = 0',text)


if __name__=='__main__':unittest.main()
