import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from conky_tree import Collector,DEFAULTS,network_total
from classic import render,network_rows


class CompatTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.sys=self.root/'sys';self.proc=self.root/'proc';self.etc=self.root/'etc'
        for p in [self.sys,self.proc,self.etc]:p.mkdir()
        self.obj=Collector(DEFAULTS.copy(),self.sys,self.proc,self.etc)
        self.addCleanup(self.obj.pool.shutdown,wait=False,cancel_futures=True)

    def put(self,path,text):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(str(text));return path

    def disk(self,name='nvme0n1',model='Test SSD',diskseq=1):
        p=self.sys/'block'/name
        for key,value in [('size',1000000),('device/model',model),('wwid','test-'+model),('diskseq',diskseq)]:self.put(p/key,value)
        return p

    def diskstats(self,name,read,write):
        self.put(self.proc/'diskstats',f'259 0 {name} 1 0 {read} 0 1 0 {write} 0 0 0 0\n')

    def net(self,name='eth0',physical=True,index=1,rx=100,tx=200):
        p=self.sys/'class/net'/name
        for key,value in [('ifindex',index),('operstate','up'),('statistics/rx_bytes',rx),('statistics/tx_bytes',tx)]:self.put(p/key,value)
        if physical:(p/'device').mkdir()
        return p

    def test_linux_distro_and_ARM_cpu_names_without_model_name(self):
        self.put(self.etc/'os-release','PRETTY_NAME="Manjaro Linux"\n')
        self.put(self.proc/'cpuinfo','processor : 0\nHardware : Example ARM SoC\n')
        data=self.obj.static_info()
        self.assertEqual(data['os'],'Manjaro Linux');self.assertEqual(data['cpu'],'Example ARM SoC')

    def test_os_release_fallback_under_usr_lib(self):
        self.put(self.root/'usr/lib/os-release','PRETTY_NAME="Test Linux"\n')
        self.assertEqual(self.obj.static_info()['os'],'Test Linux')

    def test_CPU_guest_not_counted_twice_and_older_four_fields(self):
        for guest in [True,False]:
            self.obj.old.clear()
            self.put(self.proc/'stat','cpu 100 0 100 100'+(' 0 0 0 0 50 0' if guest else '')+'\n')
            self.assertIsNone(self.obj.cpu_memory(0)['cpu_percent'])
            self.put(self.proc/'stat','cpu 200 0 100 200'+(' 0 0 0 0 100 0' if guest else '')+'\n')
            self.assertEqual(self.obj.cpu_memory(2)['cpu_percent'],50)

    def test_CPU_missing_or_reset_does_not_break_memory(self):
        self.put(self.proc/'meminfo','MemTotal: 1000 kB\nMemAvailable: 400 kB\n')
        data=self.obj.cpu_memory(0)
        self.assertIsNone(data['cpu_percent']);self.assertEqual(data['memory_used'],600*1024)
        self.put(self.proc/'stat','cpu 100 0 100 100\n');self.obj.cpu_memory(1)
        self.put(self.proc/'stat','cpu 1 0 1 1\n')
        self.assertIsNone(self.obj.cpu_memory(2)['cpu_percent'])

    def test_legacy_memory_estimate_and_missing_data(self):
        self.put(self.proc/'meminfo','MemTotal: 1000 kB\nMemFree: 100 kB\nBuffers: 100 kB\nCached: 200 kB\nSReclaimable: 100 kB\nShmem: 50 kB\n')
        data=self.obj.cpu_memory(0);self.assertEqual(data['memory_used'],550*1024);self.assertEqual(data['memory_method'],'legacy estimate')
        self.put(self.proc/'meminfo','MemTotal: 1000 kB\n')
        self.assertIsNone(self.obj.cpu_memory(1)['memory_used'])
        self.assertIsNone(self.obj.cpu_memory(1)['uptime_seconds'])

    def test_multiple_CPU_packages_and_AMD_actual_die_temperature(self):
        sensors=[{'chip':'coretemp','label':'Package id 0','celsius':50},{'chip':'coretemp','label':'Package id 1','celsius':75},{'chip':'coretemp','label':'Core 0','celsius':99}]
        self.assertEqual(self.obj.cpu_temperature(sensors),75)
        sensors=[{'chip':'k10temp','label':'Tctl','celsius':85},{'chip':'k10temp','label':'Tdie','celsius':65}]
        self.assertEqual(self.obj.cpu_temperature(sensors),65)

    def test_faulty_disabled_and_invalid_hwmon_sensors_are_excluded(self):
        p=self.sys/'class/hwmon/hwmon0';self.put(p/'name','coretemp')
        for i in range(1,5):self.put(p/f'temp{i}_input',50000)
        self.put(p/'temp1_fault',1);self.put(p/'temp2_enable',0);self.put(p/'temp3_input',9999999)
        self.assertEqual(len(self.obj.sensors()),1)

    def test_known_ARM_thermal_zone_only(self):
        for name,kind in [('thermal_zone0','cpu-thermal'),('thermal_zone1','acpitz')]:
            p=self.sys/'class/thermal'/name;self.put(p/'type',kind);self.put(p/'temp',45000)
        self.assertEqual(len(self.obj.sensors()),1)
        self.assertEqual(self.obj.cpu_temperature(self.obj.sensors()),45)

    def test_disk_sector_units_and_hotplug_diskseq_reset(self):
        p=self.disk();self.diskstats('nvme0n1',100,200);self.obj.disks(0,[])
        self.diskstats('nvme0n1',300,400)
        self.assertEqual(self.obj.disks(2,[])['devices'][0]['read_bps'],200*512/2)
        self.put(p/'diskseq',2);self.diskstats('nvme0n1',1000,2000)
        self.assertIsNone(self.obj.disks(4,[])['devices'][0]['read_bps'])

    def test_removed_disk_state_is_pruned(self):
        p=self.disk();self.diskstats('nvme0n1',100,200);self.obj.disks(0,[])
        shutil.rmtree(p);self.obj.disks(2,[])
        self.assertNotIn('disk:nvme0n1',self.obj.old)

    def test_disk_order_not_dependent_on_nvme_number(self):
        self.disk('nvme0n1','Z SSD');self.disk('nvme1n1','A SSD')
        self.assertEqual([x['model'] for x in self.obj.disks(0,[])['devices']],['A SSD','Z SSD'])

    def test_sata_xen_mmc_without_virtual_double_counting(self):
        for name in ['sda','xvda','mmcblk0','dm-0','loop0']:self.disk(name,name)
        self.assertEqual(len(self.obj.disks(0,[])['devices']),3)

    def test_root_stat_failure_keeps_disk_records(self):
        self.disk()
        with patch('conky_tree.os.statvfs',side_effect=PermissionError):data=self.obj.disks(0,[])
        self.assertEqual(len(data['devices']),1);self.assertIsNone(data['root_total'])

    def test_network_works_without_ip_command_and_excludes_virtual_links(self):
        self.net('eth0');self.net('wlan0',index=2);self.net('Meta',physical=False);self.net('lo',physical=False)
        with patch('conky_tree.run') as command:
            data=self.obj.interfaces();command.assert_not_called()
        self.assertEqual({n['name'] for n in data},{'eth0','wlan0'})
        self.assertTrue(all(not n['addresses'] for n in data))

    def test_network_counter_reset_and_reused_ifindex(self):
        p=self.net();interfaces=self.obj.interfaces();self.obj.networks(0,interfaces)
        self.put(p/'statistics/rx_bytes',500);self.put(p/'statistics/tx_bytes',1000)
        self.assertEqual(self.obj.networks(2,interfaces)[0]['rx_bps'],200)
        self.put(p/'ifindex',99);self.put(p/'statistics/rx_bytes',100000)
        self.assertIsNone(self.obj.networks(4,interfaces)[0]['rx_bps'])
        self.put(p/'statistics/rx_bytes',1)
        self.assertIsNone(self.obj.networks(6,interfaces)[0]['rx_bps'])

    def test_network_total_sums_physical_once_and_marks_partial_unknown(self):
        data=[{'physical':True,'rx_bps':100,'tx_bps':20},{'physical':True,'rx_bps':200,'tx_bps':30},{'physical':False,'rx_bps':10000,'tx_bps':20000}]
        self.assertEqual(network_total(data)['rx_bps'],300)
        self.assertEqual(network_total(data)['tx_bps'],50)
        data[0]['rx_bps']=None
        self.assertIsNone(network_total(data)['rx_bps'])
        self.assertIsNone(network_total([])['rx_bps'])

    def test_invalid_network_counter_requires_new_baseline(self):
        p=self.net(rx=-1);interfaces=self.obj.interfaces()
        self.assertIsNone(self.obj.networks(0,interfaces)[0]['rx_bps'])
        self.put(p/'statistics/rx_bytes',100)
        self.assertIsNone(self.obj.networks(2,interfaces)[0]['rx_bps'])
        self.put(p/'statistics/rx_bytes',300)
        self.assertEqual(self.obj.networks(4,interfaces)[0]['rx_bps'],100)

    def test_network_UI_is_one_rate_row_without_IP_or_hardware_names(self):
        data=[{'physical':True,'name':'eth0','addresses':['10.0.0.1'],'rx_bps':100,'tx_bps':20},{'physical':False,'name':'VPN','addresses':['198.18.0.1'],'rx_bps':999,'tx_bps':999}]
        output=network_rows(data)
        self.assertEqual(len(output.splitlines()),1);self.assertIn('总速率',output)
        for hidden in ['10.0.0.1','198.18.0.1','VPN','eth0']:self.assertNotIn(hidden,output)

    def test_one_failed_metric_does_not_abort_other_metrics(self):
        with patch.object(self.obj,'disks',side_effect=PermissionError),patch.object(self.obj,'cpu_memory',side_effect=ValueError),patch('conky_tree.run',return_value=None):data=self.obj.sample()
        self.assertIn('gpus',data);self.assertIn('networks',data)
        self.assertEqual(data['diagnostics'],{'disks':'PermissionError','cpu_memory':'ValueError'})
        self.assertIsNone(data['memory_used'])
        output=render(data)
        self.assertNotIn('${mem}',output);self.assertIn('不可用',output)


if __name__=='__main__':unittest.main()
