import copy
import json
from pathlib import Path
import re
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from classic import TEMPLATE, memory_gb
from top_tree import blocks, layout, render, visible, wrap, make_config
from preview_top import geometry
from preview_windows import comparison_position
from classic import speed, temperature
from conky_tree import network_total


def measure(text):
    return sum(20 if ord(ch)>255 else 10 for ch in visible(text))


class TopTreeTest(unittest.TestCase):
    def fixture(self):
        cases=json.loads((Path(__file__).parent/'fixtures/display-invariants.json').read_text())
        data=copy.deepcopy(cases[0]['data'])
        data['static']['kernel']='6.14.0-test'
        data['gpus']=[{'role':'integrated','driver':'i915','engines':{'render':10}}]
        return data

    def test_same_memory_disk_network_fields_and_no_old_visual_wrappers(self):
        data=self.fixture();groups,root=blocks(data)
        self.assertEqual(groups[2][0],'内存 '+memory_gb(data))
        self.assertIn('${fs_used /}/${fs_size /} (${fs_used_perc /}%)',root)
        for d in data['disks']['devices']:
            self.assertIn(d['model'],'\n'.join(groups[3]+groups[4]))
        spec=layout(data,3200,2,measure);out=render(data,spec,measure,now=1000)
        self.assertNotIn('${alignr}',out);self.assertNotIn('size=20',out)
        self.assertNotIn('< ',out);self.assertNotIn('────────────────────',out)
        self.assertIn('本用户',out)

    def test_disk_and_network_numbers_match_accepted_helpers(self):
        data=self.fixture();groups,_=blocks(data)
        net=network_total(data['networks'])
        self.assertEqual(groups[2][1],'下载 ↓ '+speed(net['rx_bps'])+'/s')
        self.assertEqual(groups[2][2],'上传 ↑ '+speed(net['tx_bps'])+'/s')
        for i,d in enumerate(data['disks']['devices']):
            text='\n'.join(groups[3+i%2])
            self.assertIn('读 '+speed(d['read_bps'])+'/s',text)
            self.assertIn('写 '+speed(d['write_bps'])+'/s',text)
            self.assertIn('温度 '+temperature(d['temperature']),text)
        split,_=blocks(data,split_rates=True)
        for i,d in enumerate(data['disks']['devices']):
            self.assertIn('读 '+speed(d['read_bps'])+'/s',split[3+i%2])
            self.assertIn('写 '+speed(d['write_bps'])+'/s',split[3+i%2])

    def test_all_five_branches_reach_one_common_trunk(self):
        data=self.fixture();spec=layout(data,3200,2,measure)
        lines=render(data,spec,measure,now=1000).splitlines()
        trunks=[(i,row) for i,row in enumerate(lines) if '┴' in row]
        self.assertEqual(len(trunks),1)
        index,trunk=trunks[0]
        self.assertEqual(trunk.count('┴'),3)
        self.assertEqual(trunk.count('├'),1);self.assertEqual(trunk.count('┘'),1)
        output='\n'.join(lines)
        self.assertEqual(output.count('${voffset -8}'),output.count('${voffset 8}'))
        for row in lines[:index]:self.assertNotIn('┘',row)
        self.assertIn('根分区',lines[index+1]);self.assertIn('└─',lines[-1])
        data['gpus'].append({'role':'discrete','driver':'nvidia','state':'suspended'})
        extended=render(data,spec,measure,now=1000).splitlines()
        trunk_i=next(i for i,row in enumerate(extended) if '┴' in row)
        self.assertIn('│',extended[trunk_i-1])
        self.assertIn('独显：挂起',''.join(extended[:trunk_i]))

    def test_missing_stale_suspended_and_dual_gpu(self):
        data=self.fixture();data['gpus']=[{'role':'integrated','driver':'i915','engines':{'render':10}},
            {'role':'discrete','driver':'nvidia','state':'suspended','utilization':99}]
        spec=layout(data,3200,2,measure)
        out=render(data,spec,measure,now=1000)
        self.assertIn('双 GPU 可见',out);self.assertIn('独显：挂起',out);self.assertNotIn('99.0%',out)
        stale=render(data,spec,measure,now=10000)
        self.assertIn('采集暂停',stale);self.assertNotIn('10.0%',stale)
        self.assertIn('不可用',render({},spec,measure,now=1000))

    def test_column_anchors_stay_fixed_for_large_values_and_changed_models(self):
        data=self.fixture();spec=layout(data,3200,2,measure)
        a=render(data,spec,measure,now=1000)
        data['memory_used']=999999999999;data['memory_total']=9999999999999
        data['cpu_percent']=100;data['disks']['devices'][0]['model']='非常长的型号'*15
        b=render(data,spec,measure,now=1000)
        def headers(out):return re.findall(r'\$\{goto (\d+)\}\$\{color4\}',out)
        self.assertEqual(headers(a),headers(b));self.assertLessEqual(spec.width,3200)
        for line in b.splitlines():
            positions=[int(v) for v in re.findall(r'\$\{goto (\d+)\}',line)]
            self.assertEqual(positions,sorted(positions))

    def test_wrapping_respects_measured_pixels_and_keeps_variables_atomic(self):
        value='VeryLongModel中文'+ '${fs_used /}'
        result=wrap(value,120,measure)
        self.assertEqual(''.join(result),value)
        self.assertTrue(all(measure(row)<=120 for row in result))
        self.assertTrue(any('${fs_used /}' in row for row in result))
        with self.assertRaises(RuntimeError):wrap('${fs_used /}',10,measure)

    def test_narrower_width_wraps_without_smaller_font_or_missing_information(self):
        data=self.fixture();spec=layout(data,1600,2,measure)
        self.assertLessEqual(spec.width,1600)
        out=render(data,spec,measure,now=1000)
        self.assertNotIn('${font',out)
        self.assertTrue(spec.split_rates)
        with self.assertRaises(RuntimeError):layout(data,100,2,measure)

    def test_more_than_two_disks_remain_in_two_disk_columns(self):
        data=self.fixture();data['disks']['devices']*=2
        groups,_=blocks(data)
        self.assertIn('硬盘 3',groups[3]);self.assertIn('硬盘 4',groups[4])
        self.assertEqual(len(groups),5)

    def test_hardware_cannot_inject_expressions_or_extra_rows(self):
        data=self.fixture();data['static']['os']='${exec bad}\nother'
        spec=layout(data,3200,2,measure);out=render(data,spec,measure,now=1000)
        self.assertNotIn('${exec',out)

    def test_right_facing_branches_precede_all_left_aligned_text(self):
        spec=layout(self.fixture(),3200,2,measure)
        out=render(self.fixture(),spec,measure,now=1000)
        self.assertNotIn('┤',out);self.assertNotIn('┐',out)
        self.assertEqual(out.splitlines()[0].count('┌─'),5)
        self.assertEqual(spec.gap,18)
        for row in out.splitlines()[:4]:
            self.assertEqual(row.count('├─') if '┌─' not in row else row.count('┌─'),5)

    def test_generated_config_preserves_desktop_layer_and_font(self):
        spec=layout(self.fixture(),3200,2,measure)
        out=make_config(TEMPLATE,Path('/tmp/test.text'),spec,0,30,72)
        self.assertIn("font = 'Noto Sans CJK SC:bold:size=7.5'",out)
        self.assertIn('below,sticky,skip_taskbar,skip_pager',out)
        self.assertIn('gap_y = 36',out);self.assertIn('uppercase = false',out)
        self.assertNotIn('minimum_height',out);self.assertNotIn('size=20',out)

    def test_comparison_only_temporarily_moves_intersecting_window(self):
        head={'x':0,'y':0,'width':3200,'height':2000}
        old={'x':2403,'y':64,'width':777,'height':1034}
        new={'x':852,'y':72,'width':2318,'height':234}
        self.assertEqual(comparison_position(old,new,head,24),{'x':2403,'y':330})
        self.assertIsNone(comparison_position(dict(old,y=400),new,head,24))
        with self.assertRaises(RuntimeError):comparison_position(old,new,dict(head,height=1100),24)

    def test_workarea_geometry_and_safe_fallback(self):
        head={'index':0,'x':0,'y':0,'width':3200,'height':2000}
        geo=geometry(head,r'Xft.dpi:\t192','_NET_WORKAREA = 0, 64, 3200, 1936, 0, 64, 3200, 1936','not found')
        self.assertEqual(geo['target_top'],72);self.assertEqual(geo['gap_x'],30)
        self.assertEqual(geometry(head,'','not found','')['gap_y'],20)
        self.assertIsNone(geometry(head,'','_NET_WORKAREA = 0, 64, 100, 1936','')['workarea'])


if __name__=='__main__':unittest.main()
