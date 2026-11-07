import json
import re
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from classic import TEMPLATE, make_config, render, gpu_rows, memory_gb
from conky_tree import Collector, DEFAULTS, DrmSampler
from start import validate_monitor


class ClassicTest(unittest.TestCase):
    def fixture(self):
        return {'sample_unix': time.time(), 'static': {'os': 'Test Linux', 'cpu': 'Test CPU'},
                'cpu_percent': 12.5, 'sensors': {'cpu_temperature': 55},
                'memory_total': 16000000000, 'memory_used': 8000000000,'memory_method':'MemAvailable',
                'gpus': [{'role': 'integrated', 'name': 'Intel Test', 'driver': 'i915',
                          'vendor': '0x8086', 'engines': {'render': 12.5, 'video': 0.0}}],
                'disks': {'devices': [{'device': 'nvme7n1', 'model': 'Test disk', 'temperature': None}]},
                'networks': [], 'public_ip': {'status': '默认关闭'}}

    def test_all_visual_settings_equal_original_except_process_buffer_monitor(self):
        original = TEMPLATE.read_text().split('conky.text', 1)[0]
        candidate = make_config(DEFAULTS, {}, TEMPLATE.parent, Path('/tmp/cache.json')).split('conky.text', 1)[0]
        def settings(text):
            return dict(re.findall(r'^\s*(\w+)\s*=\s*(.*?),\s*(?:--.*)?$', text, re.M))
        a, b = settings(original), settings(candidate)
        self.assertEqual({k: v for k, v in b.items() if k not in ['background', 'text_buffer_size', 'xinerama_head']},
                         {k: v for k, v in a.items() if k not in ['background', 'text_buffer_size','minimum_height']})
        self.assertEqual(b['xinerama_head'], '0')
        self.assertEqual(b['background'], 'false')
        self.assertNotIn('minimum_height',b)

    def test_minimal_display_keeps_uptime_font_and_tree(self):
        output = render(self.fixture())
        self.assertIn('${font Noto Sans CJK SC:bold:size=20}< ${uptime} > 运行时间', output)
        self.assertIn('${alignr}< 8.00 GB > 已使用 ─┘   │', output)
        self.assertIn('Test Linux',output)
        self.assertIn('${kernel}',output)
        for removed in ['${time','${machine}','${mem}','${memmax}','${memperc}','Test CPU','55°C']:
            self.assertNotIn(removed,output)
        self.assertIn('${alignr}───────────────────────────┘', output)
        self.assertNotIn('${exec', output)
        self.assertNotIn('sudo', output)

    def test_unknown_values_are_not_faked_zero(self):
        output = render(self.fixture())
        self.assertIn('不可用', output)
        self.assertNotIn('0°C', output)
        self.assertIn('< 12.5% > 核显渲染（本用户）', output)
        self.assertNotIn('计算', output)
        self.assertNotIn('复制', output)

    def test_memory_decimal_GB_estimate_zero_and_unknown(self):
        self.assertEqual(memory_gb({'memory_used':8750000000,'memory_method':'MemAvailable'}),'8.75 GB')
        self.assertEqual(memory_gb({'memory_used':1073741824}),'1.07 GB')
        self.assertEqual(memory_gb({'memory_used':8750000000,'memory_method':'legacy estimate'}),'≈8.75 GB')
        self.assertEqual(memory_gb({'memory_used':0}),'0.00 GB')
        for value in [None,-1,float('nan'),float('inf'),'8GB',True]:
            with self.subTest(value=value):self.assertEqual(memory_gb({'memory_used':value}),'不可用')
        self.assertEqual(memory_gb({'memory_used':8750000000},stale=True),'不可用')

    def test_single_and_dual_GPU_only_show_topology_and_loads(self):
        integrated=self.fixture()['gpus'][0]
        discrete={'role':'discrete','driver':'nvidia','state':'active','name':'Secret Model','utilization':35,'temperature':60,'power':55,'memory_used':2000,'memory_total':8000}
        single=gpu_rows([integrated]);dual=gpu_rows([integrated,discrete]);only_discrete=gpu_rows([discrete])
        self.assertEqual(len(single),2);self.assertEqual(len(dual),3);self.assertEqual(len(only_discrete),2)
        self.assertIn('双 GPU 可见',dual[0]);self.assertIn('仅独显可见',only_discrete[0]);self.assertIn('35.0%',dual[-1])
        for removed in ['Secret Model','温度','功耗','显存','未枚举']:
            self.assertNotIn(removed,''.join(dual))
        self.assertEqual(gpu_rows([]),['[ 未枚举图形设备 ]','占用率：不可用'])

    def test_discrete_unavailable_and_suspended_never_reuse_old_load(self):
        base={'role':'discrete','name':'NVIDIA','driver':'nvidia','state':'active','utilization':99}
        suspended=gpu_rows([dict(base,state='suspended')])
        self.assertEqual(suspended[-1],'独显：挂起')
        for change in [{'state':'unknown'},{'driver':None},{'utilization':None}]:
            output=''.join(gpu_rows([dict(base,**change)]))
            self.assertIn('不可用',output);self.assertNotIn('99.0%',output)

    def test_disk_and_network_identical_to_previous_commit_for_shared_inputs(self):
        fixtures=json.loads((Path(__file__).parent/'fixtures/display-invariants.json').read_text())
        for case in fixtures:
            with self.subTest(case=case['name']),patch('classic.time.time',return_value=1000):
                output=render(case['data'])
                disk=output.split('${alignr}${color4}HARD DISK',1)[1].split('${alignr}${color4}NETWORK INFO',1)[0]
                network=output.split('${alignr}${color4}NETWORK INFO',1)[1]
                self.assertEqual(disk,case['disk']);self.assertEqual(network,case['network'])

    def test_unknown_and_missing_driver_discrete_do_not_change_rows(self):
        g = {'role': 'discrete', 'name': 'NVIDIA Test', 'driver': 'nvidia', 'state': 'active'}
        counts = [len(gpu_rows([dict(g, **changes)])) for changes in [{}, {'state': 'suspended'}, {'driver': None}, {'state': 'unknown'}]]
        self.assertEqual(len(set(counts)), 1)
        self.assertNotIn('0.0%', ''.join(gpu_rows([dict(g, state='suspended', utilization=99)])))

    def test_iGPU_unknown_role_and_AMD_busy_paths_have_stable_rows(self):
        g = {'role': 'integrated', 'name': 'Test', 'driver': 'amdgpu', 'state': 'active'}
        self.assertEqual(len(gpu_rows([g])), len(gpu_rows([dict(g, utilization=10)])))
        self.assertIn('未接管', ''.join(gpu_rows([dict(g, driver=None)])))

    def test_stale_cache_cannot_display_old_gpu_or_disk_percent(self):
        data = self.fixture();data['sample_unix'] = 1
        output = render(data)
        self.assertIn('采集暂停', output)
        self.assertNotIn('12.5%', output)

    def test_hardware_values_cannot_inject_executable_conky(self):
        data = self.fixture();data['static']['os'] = '${exec touch /tmp/not-allowed}'
        output = render(data)
        self.assertNotIn('${exec', output)

    def test_monitor_mismatch_stops_instead_of_external_fallback(self):
        head = {'index': 0, 'x': 2560, 'y': 240, 'width': 1920, 'height': 1200}
        with patch('start.run', return_value='eDP-1 connected primary 1920x1200+0+0'):
            with self.assertRaisesRegex(RuntimeError, 'no longer matches'):
                validate_monitor(DEFAULTS, [head])
        with patch('start.run', return_value='eDP-1 disconnected'):
            with self.assertRaisesRegex(RuntimeError, 'inactive'):
                validate_monitor(DEFAULTS, [head])

    def test_nvidia_cache_does_not_throttle_other_GPU_or_survive_suspend(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj = Collector(DEFAULTS, tmp)
            p = Path(tmp)/'bus/pci/devices/0000:01:00.0/power';p.mkdir(parents=True)
            status = p/'runtime_status';status.write_text('active')
            obj.drm.sample = lambda _: ({}, 0, 0)
            dev = {'pci': '0000:01:00.0', 'vendor': '0x10de', 'driver': 'nvidia', 'role': 'discrete', 'name': 'NVIDIA'}
            with patch('conky_tree.run', return_value='10, 50, 8000, 40, 5') as query:
                obj.gpu_snapshot(0, [dev], [])
                obj.gpu_snapshot(6, [dev], [])
                self.assertEqual(query.call_count, 1)
                status.write_text('suspended')
                snapshot = obj.gpu_snapshot(7, [dev], [])
                self.assertIsNone(snapshot[0]['utilization'])
                status.write_text('active')
                obj.gpu_snapshot(8, [dev], [])
                self.assertEqual(query.call_count, 2)
            obj.pool.shutdown()

    def test_real_fdinfo_aliases_exit_and_counter_rollback(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp)/'123';fds=proc/'fdinfo';fds.mkdir(parents=True)
            (proc/'stat').write_text('123 (test) '+ ' '.join(['S']+['0']*18+['777']))
            sample=DrmSampler(tmp)
            def counters(n):
                text='drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 8\ndrm-engine-render: '+str(n)+' ns\n'
                for name in ['4','5']:(fds/name).write_text(text)
            counters(0);sample.sample(0)
            counters(500000000);values,clients,_=sample.sample(1)
            self.assertEqual(clients,1)
            self.assertEqual(values['0000:00:02.0']['render'],50)
            counters(100000000);values,_,_=sample.sample(2)
            self.assertIsNone(values['0000:00:02.0']['render'])
            counters(600000000);values,_,_=sample.sample(3)
            self.assertEqual(values['0000:00:02.0']['render'],10)
            (proc/'stat').unlink()
            values,clients,_=sample.sample(4)
            self.assertEqual(clients,0)
            self.assertEqual(values,{})

    def test_permission_denied_does_not_create_zero_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc=Path(tmp)/'123';fds=proc/'fdinfo';fds.mkdir(parents=True)
            (proc/'stat').write_text('123 (test) '+ ' '.join(['S']+['0']*18+['777']))
            original=Path.iterdir
            def restricted(path):
                if path==fds:raise PermissionError('test')
                return original(path)
            with patch.object(Path,'iterdir',restricted):
                values,clients,denied=DrmSampler(tmp).sample(1)
            self.assertEqual(values,{})
            self.assertEqual(clients,0)
            self.assertEqual(denied,1)


if __name__ == '__main__':
    unittest.main()
