import unittest
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from conky_tree import DrmSampler, Collector, DEFAULTS, engine_delta, topology, gpu_lines, rate, clean, render

class MetricsTest(unittest.TestCase):
    def test_descriptor_alias_dedup_identity(self):
        text='drm-driver: i915\ndrm-pdev: 0000:00:02.0\ndrm-client-id: 8\ndrm-engine-render: 100 ns\n'
        a=DrmSampler.parse(text);b=DrmSampler.parse(text)
        clients={a[0]:a[1],b[0]:b[1]}
        self.assertEqual(len(clients),1)
        self.assertEqual(a[0],('0000:00:02.0','i915','8'))

    def test_engine_capacity_and_distinct_engines(self):
        k=('pci','i915','8')
        old={k:({'render':100,'video':0},{'video':2})}
        new={k:({'render':500000100,'video':1000000000},{'video':2})}
        r=engine_delta(old,new,1)
        self.assertEqual(r[('pci','render')],50)
        self.assertEqual(r[('pci','video')],50)

    def test_rollback_not_false_zero(self):
        k=('pci','i915','8')
        self.assertIsNone(engine_delta({k:({'render':500},{})},{k:({'render':10},{})},1)[('pci','render')])

    def test_new_or_departed_clients_need_two_samples(self):
        a={('pci','i915','1'):({'render':10},{})}
        b={('pci','i915','2'):({'render':10},{})}
        self.assertEqual(engine_delta(a,b,1),{})

    def test_invalid_capacity_and_out_of_range(self):
        k=('pci','i915','8')
        self.assertIsNone(engine_delta({k:({'render':0},{})},{k:({'render':2000000000},{})},1)[('pci','render')])

    def test_gpu_modes_are_topology_only(self):
        self.assertEqual(topology([{'role':'integrated'}]),'仅核显可见')
        self.assertEqual(topology([{'role':'discrete'}]),'仅独显可见')
        self.assertEqual(topology([{'role':'integrated'},{'role':'discrete'}]),'双 GPU 可见')
        self.assertIn('GPU 可见',topology([{'role':'unknown'}]))

    def test_discrete_active_and_suspended_keep_row_count(self):
        g={'name':'Test GPU','role':'discrete','driver':'nvidia','state':'active'}
        active=gpu_lines([g]);suspended=gpu_lines([dict(g,state='suspended')])
        self.assertEqual(len(active),len(suspended))
        self.assertTrue(any('挂起' in x for x in suspended))
        self.assertFalse(any('0.0%' in x for x in suspended))

    def test_missing_driver_and_metrics(self):
        r=gpu_lines([{'name':'Test','role':'integrated','driver':None,'state':'unknown'}])
        self.assertTrue(any('驱动未接管' in x for x in r))

    def test_untrusted_names_cannot_inject_conky(self):
        self.assertNotIn('${',clean('${exec bad}\nmore'))
        self.assertNotIn('\n',clean('a\nb'))

    def test_net_and_disk_counter_reset(self):
        self.assertIsNone(rate(100,10,2))
        self.assertEqual(rate(100,300,2),100)

    def test_same_client_id_on_different_devices_not_merged(self):
        def record(pdev):return DrmSampler.parse('drm-driver: i915\ndrm-pdev: '+pdev+'\ndrm-client-id: 1\ndrm-engine-render: 10 ns\n')
        a,b=record('0000:00:02.0'),record('0000:03:00.0')
        self.assertNotEqual(a[0],b[0])

    def test_non_pci_or_missing_identification_not_falsely_counted(self):
        self.assertIsNone(DrmSampler.parse('drm-driver: i915\ndrm-engine-render: 10 ns'))

    def test_nvidia_suspended_never_queries_driver(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=Collector(DEFAULTS.copy(),tmp)
            p=Path(tmp)/'bus/pci/devices/0000:01:00.0/power';p.mkdir(parents=True)
            (p/'runtime_status').write_text('suspended')
            obj.drm.sample=lambda _:({},0,0)
            dev={'pci':'0000:01:00.0','vendor':'0x10de','driver':'nvidia','role':'discrete','name':'NVIDIA'}
            with patch('conky_tree.run') as mock:
                out=obj.gpu_snapshot(1,[dev],[])
                mock.assert_not_called()
                self.assertIsNone(out[0]['utilization'])
            obj.pool.shutdown()

    def test_nvidia_missing_tool_is_unavailable_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            obj=Collector(DEFAULTS.copy(),tmp)
            p=Path(tmp)/'bus/pci/devices/0000:01:00.0/power';p.mkdir(parents=True)
            (p/'runtime_status').write_text('active');obj.drm.sample=lambda _:({},0,0)
            dev={'pci':'0000:01:00.0','vendor':'0x10de','driver':'nvidia','role':'discrete','name':'NVIDIA'}
            with patch('conky_tree.run',return_value=None):
                out=obj.gpu_snapshot(1,[dev],[])
                self.assertIsNone(out[0]['utilization'])
            obj.pool.shutdown()

    def test_missing_cpu_temperature(self):
        self.assertIsNone(Collector.cpu_temperature(None,[]))

    def test_stale_data_does_not_present_old_values_as_current(self):
        self.assertIn('采集已暂停',render({'sample_unix':1}))

    def test_public_ip_disabled_starts_no_network_job(self):
        obj=Collector(DEFAULTS.copy())
        with patch.object(obj.pool,'submit') as submit:
            self.assertEqual(obj.public_address(1)['status'],'默认关闭')
            submit.assert_not_called()
        obj.pool.shutdown()

if __name__=='__main__':unittest.main()
