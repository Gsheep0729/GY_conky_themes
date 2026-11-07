#!/usr/bin/env python3
"""Unprivileged Linux desktop telemetry. Standard library only."""
import argparse
import concurrent.futures
import glob
import ipaddress
import json
import math
import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

DEFAULTS = {
    'monitor_index': 0, 'expected_connector': 'eDP-1', 'start_delay': 30,
    'sample_seconds': 2, 'gpu_seconds': 5, 'gpu_battery_seconds': 10,
    'public_ip': False, 'gpu_roles': {},
    'layout': 'classic',
}

def read(path, default=None):
    try:
        return Path(path).read_text(errors='replace').strip()
    except OSError:
        return default

def number(path):
    try:
        return int(read(path))
    except (TypeError, ValueError):
        return None

def run(args, timeout=2):
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True,
                              timeout=timeout).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None

def atomic(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False) + '\n')
    tmp.chmod(0o600)
    tmp.replace(path)

def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(value)
    tmp.chmod(0o600)
    tmp.replace(path)

def config(path):
    out = DEFAULTS.copy()
    if Path(path).exists():
        data = json.loads(Path(path).read_text())
        if not isinstance(data, dict):
            raise ValueError('config must be an object')
        out.update(data)
    if not isinstance(out['monitor_index'], int) or out['monitor_index'] < 0:
        raise ValueError('monitor_index must be a nonnegative integer')
    for k in ['sample_seconds', 'gpu_seconds', 'gpu_battery_seconds']:
        if not isinstance(out[k], (int, float)) or not 1 <= out[k] <= 300:
            raise ValueError('invalid interval: ' + k)
    if out.get('layout') != 'classic':
        raise ValueError('Only the original classic layout is supported by this candidate')
    return out

def clean(value, limit=45):
    # Hardware strings must never become Conky expressions or extra lines.
    value = re.sub(r'[\x00-\x1f\x7f]', ' ', str(value)).replace('$', '＄')
    return value if len(value) <= limit else value[:limit-1] + '…'

def rate(previous, current, seconds):
    if previous is None or current is None or seconds <= 0 or current < previous:
        return None
    return (current - previous) / seconds

def network_total(networks):
    physical=[n for n in networks if n.get('physical',n.get('kind') in ['Wi-Fi','有线'])]
    result={'interface_count':len(physical),'scope':'physical interfaces'}
    for field in ['rx_bps','tx_bps']:
        values=[n.get(field) for n in physical]
        result[field]=sum(values) if values and all(isinstance(v,(int,float)) and math.isfinite(v) and v>=0 for v in values) else None
    return result

def engine_delta(previous, current, seconds):
    totals = {}
    valid = set()
    invalid = set()
    for key in previous.keys() & current.keys():
        old, _ = previous[key]
        new, caps = current[key]
        for engine in old.keys() & new.keys():
            capacity = caps.get(engine, 1)
            if capacity <= 0 or new[engine] < old[engine] or seconds <= 0:
                invalid.add((key[0], engine))
                continue
            k = (key[0], engine)
            totals[k] = totals.get(k, 0) + (new[engine]-old[engine]) / (seconds*1e9*capacity)*100
            valid.add(k)
    return {k: (round(min(100, totals[k]), 2) if k not in invalid and 0 <= totals[k] <= 100.5 else None)
            for k in valid | invalid}

def topology(gpus):
    roles = {g.get('role') for g in gpus}
    if 'integrated' in roles and 'discrete' in roles:
        return '双 GPU 可见'
    if gpus and roles == {'integrated'}:
        return '仅核显可见'
    if gpus and roles == {'discrete'}:
        return '仅独显可见'
    return f'{len(gpus)} 个 GPU 可见' if gpus else '未枚举图形设备'

def proc_start(proc):
    text = read(Path(proc)/'stat')
    try:
        return text.rsplit(')', 1)[1].split()[19]
    except (AttributeError, IndexError):
        return None

class DrmSampler:
    def __init__(self, proc='/proc', uid=None):
        self.proc = Path(proc)
        self.uid = os.getuid() if uid is None else uid
        self.paths = []
        self.discovered = -100
        self.previous = {}
        self.when = None
        self.client_counts = {}

    @staticmethod
    def parse(text):
        fields = {k:v.strip() for k,v in (line.split(':',1) for line in text.splitlines()
                  if line.startswith('drm-') and ':' in line)}
        pdev, client = fields.get('drm-pdev'), fields.get('drm-client-id')
        if not pdev or not client:
            return None
        counters, capacities = {}, {}
        for k,v in fields.items():
            if k.startswith('drm-engine-capacity-') and v.isdigit():
                capacities[k[len('drm-engine-capacity-'):]] = int(v)
            elif k.startswith('drm-engine-') and re.fullmatch(r'\d+ ns',v):
                counters[k[len('drm-engine-'):]] = int(v.split()[0])
        return (pdev, fields.get('drm-driver','?'), client), (counters, capacities)

    def sample(self, now):
        denied = 0
        if now-self.discovered >= 10:
            self.paths = []
            for proc in self.proc.iterdir():
                if not proc.name.isdigit():
                    continue
                try:
                    if proc.stat().st_uid != self.uid:
                        continue
                    start = proc_start(proc)
                    if start is None:
                        continue
                    for fd in (proc/'fdinfo').iterdir():
                        text = read(fd)
                        if text and 'drm-driver:' in text:
                            self.paths.append((fd, proc, start))
                except PermissionError:
                    denied += 1
                except OSError:
                    pass
            self.discovered = now
        clients = {}
        for fd, proc, start in self.paths:
            if proc_start(proc) != start:
                continue
            text = read(fd)
            if text is None:
                continue
            parsed = self.parse(text)
            if parsed:
                clients[parsed[0]] = parsed[1]
        self.client_counts = {}
        for pdev, driver, client in clients:
            self.client_counts[pdev] = self.client_counts.get(pdev, 0) + 1
        seconds = now-self.when if self.when is not None else 0
        values = engine_delta(self.previous, clients, seconds) if seconds else {}
        # Hold the previous high-water mark when counters temporarily roll back.
        held = {}
        for key,(new,caps) in clients.items():
            old = self.previous.get(key, ({},{}))[0]
            held[key] = ({e:max(n,old.get(e,n)) for e,n in new.items()},caps)
        self.previous, self.when = held, now
        by_device = {}
        for (pdev,engine),value in values.items():
            by_device.setdefault(pdev,{})[engine] = value
        return by_device, len(clients), denied

class Collector:
    def __init__(self, cfg, sysroot='/sys', procroot='/proc', etcroot='/etc'):
        self.cfg, self.sys, self.proc, self.etc = cfg, Path(sysroot), Path(procroot), Path(etcroot)
        self.drm = DrmSampler(procroot)
        self.cache, self.times, self.old = {}, {}, {}
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.ip_future = None
        self.static = self.static_info()

    def due(self, key, seconds, fn, now):
        if now-self.times.get(key,-1e12) >= seconds:
            try:
                self.cache[key] = fn()
            except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
                self.cache[key] = {'error':type(error).__name__}
            self.times[key] = now
        return self.cache.get(key)

    def static_info(self):
        os_release = read(self.etc/'os-release') or read(self.etc.parent/'usr/lib/os-release','')
        match = re.search(r'^PRETTY_NAME=(.*)$',os_release,re.M)
        cpu_info=read(self.proc/'cpuinfo','')
        cpu=None
        for key in ['model name','Hardware','Model','Processor']:
            cpu=re.search(r'^'+re.escape(key)+r'\s*:\s*(\S[^\n]*)$',cpu_info,re.M)
            if cpu and not cpu[1].strip().isdigit():break
            cpu=None
        return {'os':match[1].strip('"') if match else platform.system(),
                'kernel':platform.release(), 'arch':platform.machine(),
                'hostname':platform.node(), 'cpu':cpu[1] if cpu else platform.machine()+' CPU（型号不可读）'}

    def battery(self):
        batteries = []
        supplies = []
        for p in (self.sys/'class/power_supply').glob('*'):
            kind = read(p/'type')
            if kind=='Battery':
                batteries.append({'name':p.name,'capacity':number(p/'capacity'),'status':read(p/'status')})
            elif (p/'online').exists():
                supplies.append(number(p/'online'))
        on_battery = any(b['status']=='Discharging' for b in batteries) and not any(s==1 for s in supplies)
        return {'on_battery':on_battery,'batteries':batteries}

    def cpu_memory(self, now):
        # guest/guest_nice are already included in user/nice. Older kernels
        # may omit iowait/irq/softirq/steal; absent trailing fields are zero.
        line=next((l for l in read(self.proc/'stat','').splitlines() if re.match(r'^cpu\s',l)),None)
        usage=None
        if line:
            try:
                counters=list(map(int,line.split()[1:9]))
                if len(counters)<4 or any(x<0 for x in counters):raise ValueError('invalid CPU counters')
                counters += [0]*(8-len(counters));total=sum(counters);idle=counters[3]+counters[4]
                old=self.old.get('cpu')
                if old and total>old[0] and 0<=idle-old[1]<=total-old[0]:
                    usage=100*(1-(idle-old[1])/(total-old[0]))
                self.old['cpu']=(total,idle)
            except ValueError:self.old.pop('cpu',None)
        else:self.old.pop('cpu',None)
        mem={}
        for line in read(self.proc/'meminfo','').splitlines():
            key,_,val=line.partition(':')
            try:
                value=int(val.split()[0])*1024
                if value>=0:mem[key]=value
            except (ValueError,IndexError):pass
        total=mem.get('MemTotal') or None;used=None;method='unavailable'
        if total and total>0:
            available=mem.get('MemAvailable');method='MemAvailable'
            if available is None and 'MemFree' in mem:
                available=mem['MemFree']+mem.get('Buffers',0)+mem.get('Cached',0)+mem.get('SReclaimable',0)-mem.get('Shmem',0)
                method='legacy estimate'
            if available is not None:used=max(0,min(total,total-available))
        try:
            uptime=float(read(self.proc/'uptime','').split()[0])
            if not math.isfinite(uptime) or uptime<0:uptime=None
        except (ValueError,IndexError):uptime=None
        return {'cpu_percent':round(usage,1) if usage is not None else None,
                'memory_total':total,'memory_used':used,'memory_method':method,
                'uptime_seconds':uptime}

    def sensors(self):
        out=[]
        for p in (self.sys/'class/hwmon').glob('hwmon*'):
            chip=read(p/'name','unknown')
            for temp in p.glob('temp*_input'):
                value=number(temp)
                stem=temp.name[:-len('_input')]
                if value is None or not -273150<=value<=300000 or number(p/(stem+'_fault'))==1 or number(p/(stem+'_enable'))==0:
                    continue
                out.append({'chip':chip,'device':str((p/'device').resolve()),
                            'label':read(temp.with_name(temp.name.replace('_input','_label')),temp.stem),
                            'celsius':value/1000})
        # Common ARM/SoC and x86 package thermal zones, never arbitrary ACPI
        # motherboard zones. Only use these if a known CPU hwmon is absent.
        for p in (self.sys/'class/thermal').glob('thermal_zone*'):
            kind=read(p/'type','');value=number(p/'temp')
            if kind in ['cpu-thermal','cpu_thermal','x86_pkg_temp','soc_thermal'] and value is not None and -273150<=value<=300000:
                out.append({'chip':'cpu_thermal','device':str(p.resolve()),'label':kind,'celsius':value/1000})
        return out

    def cpu_temperature(self, sensors):
        if not isinstance(sensors,list):return None
        choices=[s for s in sensors if s['chip'] in ['coretemp','k10temp','zenpower']]
        packages=[s['celsius'] for s in choices if s['label'].startswith('Package id ')]
        if packages:return max(packages)
        for label in ['Tdie','Tctl']:
            values=[s['celsius'] for s in choices if s['label']==label]
            if values:return max(values)
        if choices:return max(s['celsius'] for s in choices)
        return max((s['celsius'] for s in sensors if s['chip']=='cpu_thermal'),default=None)

    def disks(self, now, sensors):
        counters={}
        for line in read(self.proc/'diskstats','').splitlines():
            fields=line.split()
            if len(fields)>=14:
                try:
                    values=(int(fields[5])*512,int(fields[9])*512)
                    if all(v>=0 for v in values):counters[fields[2]]=values
                except ValueError:continue
        result=[];present=set()
        for p in sorted((self.sys/'block').glob('*')):
            if not re.fullmatch(r'nvme\d+n\d+|sd[a-z]+|vd[a-z]+|xvd[a-z]+|hd[a-z]+|mmcblk\d+',p.name):continue
            size=number(p/'size')
            if not size or size<0:continue
            present.add('disk:'+p.name)
            device=(p/'device').resolve(); model=read(p/'device/model') or read(p/'device/name') or p.name
            stable=read(p/'wwid') or read(p/'device/wwid') or read(p/'device/serial') or str(p.resolve())
            # diskseq changes even when a reattached drive reuses the old name.
            identity=(stable,number(p/'diskseq'),str(p.resolve()),size)
            temp=None
            for s in sensors if isinstance(sensors,list) else []:
                sensor_device=Path(s['device'])
                if sensor_device==device or sensor_device in device.parents:
                    if s['chip']=='nvme' and s['label']=='Composite':temp=s['celsius'];break
                    if s['chip'] in ['drivetemp']:temp=s['celsius']
            cur=counters.get(p.name);old=self.old.get('disk:'+p.name)
            speeds=[None,None]
            if cur and old and len(old)>2 and old[2]==identity:
                speeds=[rate(old[0][i],cur[i],now-old[1]) for i in range(2)]
            if cur:self.old['disk:'+p.name]=(cur,now,identity)
            else:self.old.pop('disk:'+p.name,None)
            result.append({'device':p.name,'model':model,'stable_id':stable,'bytes':size*512,'temperature':temp,
                           'read_bps':speeds[0],'write_bps':speeds[1]})
        for key in list(self.old):
            if key.startswith('disk:') and key not in present:self.old.pop(key,None)
        # Stable model/identity ordering keeps hardware labels steady across
        # a reboot that swaps nvme0/nvme1. Do not sum dm/md and their members.
        result.sort(key=lambda d:(d['model'].casefold(),d['stable_id']))
        root_total=root_used=None
        try:
            rootfs=os.statvfs('/');root_total=rootfs.f_blocks*rootfs.f_frsize
            root_used=(rootfs.f_blocks-rootfs.f_bfree)*rootfs.f_frsize
        except OSError:pass
        return {'devices':result,'root_total':root_total,'root_used':root_used}

    def interfaces(self):
        out=[]
        for p in (self.sys/'class/net').glob('*'):
            physical=(p/'device').exists();wireless=(p/'wireless').exists()
            # Sum physical ports once, without loopback/TUN/veth/bridge/bond
            # aggregates. No ip, ifconfig, NetworkManager or network requests.
            if not physical:continue
            out.append({'name':p.name,'kind':'Wi-Fi' if wireless else '有线','physical':True,
                        'state':read(p/'operstate','unknown'),'ifindex':number(p/'ifindex'),
                        'identity':str((p/'device').resolve()),'addresses':[]})
        return out

    def networks(self, now, interfaces):
        out=[];present=set()
        for entry in interfaces if isinstance(interfaces,list) else []:
            interface=self.sys/'class/net'/entry['name']
            if not interface.exists():continue
            key='net:'+entry['name'];present.add(key)
            identity=(number(interface/'ifindex'),str((interface/'device').resolve()))
            p=interface/'statistics'
            cur=tuple(v if v is not None and v>=0 else None for v in [number(p/'rx_bytes'),number(p/'tx_bytes')])
            old=self.old.get('net:'+entry['name']);speeds=[None,None]
            if old and len(old)>2 and old[2]==identity:
                speeds=[rate(old[0][i],cur[i],now-old[1]) for i in range(2)]
            self.old[key]=(cur,now,identity)
            out.append(dict(entry,rx_bps=speeds[0],tx_bps=speeds[1]))
        for key in list(self.old):
            if key.startswith('net:') and key not in present:self.old.pop(key,None)
        return out

    def gpu_devices(self):
        names={}
        pci=run(['lspci','-Dmm'])
        if pci:
            import shlex
            for line in pci.splitlines():
                parts=shlex.split(line)
                if len(parts)>=4:names[parts[0]]=parts[3]
        out=[]
        for dev in sorted((self.sys/'bus/pci/devices').glob('*')):
            cls=read(dev/'class','')
            if not cls.startswith('0x03'):continue
            vendor=read(dev/'vendor','')
            role=self.cfg.get('gpu_roles',{}).get(dev.name)
            if not role:
                role='integrated' if vendor=='0x8086' and dev.name.endswith('00:02.0') else 'discrete' if vendor=='0x10de' else 'unknown'
            out.append({'pci':dev.name,'vendor':vendor,'role':role,'name':names.get(dev.name,'GPU '+read(dev/'device','?')),
                        'driver':(dev/'driver').resolve().name if (dev/'driver').exists() else None})
        return out

    def gpu_snapshot(self, now, devices, sensors):
        bydev,clients,denied=self.drm.sample(now)
        result=[]
        for base in devices if isinstance(devices,list) else []:
            gpu=dict(base);dev=self.sys/'bus/pci/devices'/base['pci']
            state=read(dev/'power/runtime_status','unknown');gpu['state']=state
            gpu.update(engines=bydev.get(base['pci'],{}),scope='本用户客户端',clients=clients,
                       unreadable=denied,temperature=None,utilization=None,memory_used=None,memory_total=None,power=None)
            gpu['clients'] = self.drm.client_counts.get(base['pci'], 0)
            if base['driver'] and state=='active':
                for s in sensors if isinstance(sensors,list) else []:
                    if base['pci'] in s['device'] and s['chip'] in ['amdgpu','nouveau','i915','xe']:
                        gpu['temperature']=s['celsius'];break
                if base['vendor']=='0x1002':
                    value=number(dev/'gpu_busy_percent')
                    if value is not None and 0<=value<=100:gpu['utilization']=value;gpu['scope']='设备忙碌率'
                if base['vendor']=='0x10de':
                    # Never query a runtime-suspended or unbound discrete GPU.
                    output=self.due('nvidia:'+base['pci'],10,lambda:run(['nvidia-smi','--id='+base['pci'],
                                '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw',
                                '--format=csv,noheader,nounits'],timeout=2),now)
                    if output:
                        values=output.splitlines()[0].split(',')
                        for key,value in zip(['utilization','memory_used','memory_total','temperature','power'],values):
                            try:
                                value=float(value.strip())
                                if math.isfinite(value) and value>=0 and (key!='utilization' or value<=100):gpu[key]=value
                            except ValueError:pass
                        gpu['scope']='NVIDIA 驱动遥测'
            else:
                # A later resume must not reuse a pre-suspend telemetry value.
                self.times.pop('nvidia:'+base['pci'], None)
                self.cache.pop('nvidia:'+base['pci'], None)
            result.append(gpu)
        return result

    def public_address(self, now):
        if not self.cfg.get('public_ip'):return {'status':'默认关闭','address':None}
        if self.ip_future and self.ip_future.done():
            value=self.ip_future.result();self.ip_future=None
            try:value=str(ipaddress.ip_address(value or ''))
            except ValueError:value=None
            self.cache['public_ip']={'address':value,'status':'正常' if value else '查询不可用'}
        if self.ip_future is None and now-self.times.get('public_ip',-1e12)>=600:
            self.ip_future=self.pool.submit(run,['curl','--fail','--silent','--connect-timeout','2','--max-time','3','https://api.ipify.org'],4)
            self.times['public_ip']=now
        return self.cache.get('public_ip',{'status':'查询中','address':None})

    def sample(self):
        now=time.monotonic();errors={}
        def component(name,fn,fallback):
            try:
                value=fn()
                if isinstance(value,dict) and 'error' in value:
                    errors[name]=value['error'];return fallback
                return value
            except (OSError,ValueError,KeyError,IndexError,TypeError,ArithmeticError) as error:
                errors[name]=type(error).__name__;return fallback
        battery=component('battery',lambda:self.due('battery',10,self.battery,now),{})
        sensors=component('sensors',lambda:self.due('sensors',5,self.sensors,now),[])
        devices=component('gpu_devices',lambda:self.due('devices',30,self.gpu_devices,now),[])
        gpu_interval=self.cfg['gpu_battery_seconds'] if battery.get('on_battery') else self.cfg['gpu_seconds']
        # Intel sampling keeps its own cadence even on dual-GPU machines.
        # NVIDIA queries are separately cached for at least ten seconds.
        gpus=component('gpu',lambda:self.due('gpu',gpu_interval,lambda:self.gpu_snapshot(now,devices,sensors),now),[])
        interfaces=component('interfaces',lambda:self.due('interfaces',5,self.interfaces,now),[])
        networks=component('networks',lambda:self.networks(now,interfaces),[])
        result={'schema_version':1,'sample_unix':time.time(),'static':self.static,'battery':battery,
                'sensors':{'cpu_temperature':component('cpu_temperature',lambda:self.cpu_temperature(sensors),None)},
                'disks':component('disks',lambda:self.disks(now,sensors),{'devices':[],'root_total':None,'root_used':None}),
                'networks':networks,'network_total':network_total(networks),
                'gpus':gpus if isinstance(gpus,list) else [],
                'public_ip':component('public_ip',lambda:self.public_address(now),{'status':'不可用','address':None}),
                'diagnostics':errors}
        result.update(component('cpu_memory',lambda:self.cpu_memory(now),{'cpu_percent':None,'memory_total':None,'memory_used':None,'uptime_seconds':None}))
        return result

def human(value, suffix='B'):
    if value is None:return '—'
    for unit in ['', 'Ki','Mi','Gi','Ti']:
        if abs(value)<1024:return f'{value:.1f} {unit}{suffix}'
        value/=1024
    return f'{value:.1f} Pi{suffix}'

def pct(value):
    return '等待/不可用' if value is None else f'{value:.1f}%'

def temp(value):
    return '不可用' if value is None else f'{value:.0f}°C'

def gpu_lines(gpus):
    lines=['拓扑：'+topology(gpus)]
    for gpu in gpus:
        lines.append('├─ '+clean(gpu['name'],36)+' · '+clean(gpu.get('driver') or '无驱动',12))
        if not gpu.get('driver'):
            lines.extend(['│  状态：驱动未接管','│  负载/温度：不可用'])
        elif gpu['role']=='discrete':
            active=gpu.get('state')=='active'
            lines.append('│  状态：'+('活动' if active else '挂起，不主动查询' if gpu.get('state')=='suspended' else '状态不可读'))
            lines.append('│  负载 '+pct(gpu.get('utilization'))+' · 温度 '+temp(gpu.get('temperature')) if active else '│  负载 — · 温度 —')
            memory=f"{gpu.get('memory_used'):.0f}/{gpu.get('memory_total'):.0f} MiB" if gpu.get('memory_used') is not None and gpu.get('memory_total') is not None else '—'
            power=f"{gpu['power']:.1f} W" if gpu.get('power') is not None else '—'
            lines.append('│  显存 '+memory+' · 功耗 '+power)
        else:
            engines=gpu.get('engines',{})
            if gpu.get('utilization') is not None:
                lines.append('│  设备忙碌率 '+pct(gpu['utilization']))
            else:
                lines.append('│  渲染 '+pct(engines.get('render'))+' · 视频 '+pct(engines.get('video')))
                lines.append('│  计算 '+pct(engines.get('compute'))+' · 复制 '+pct(engines.get('copy')))
            lines.append('│  范围：'+gpu.get('scope','不可用'))
    if not any(g.get('role')=='discrete' for g in gpus):lines.append('└─ 独显：未枚举')
    elif not any(g.get('role')=='integrated' for g in gpus):lines.append('└─ 核显：未枚举')
    return lines

def render(data):
    align='${alignr}'
    def section(title):return align+'${color4}'+title+'${color} ─┤\n'
    def rows(items):
        return '\n'.join(align+v+(' ─┘   │' if i==len(items)-1 else ' ─┤   │') for i,v in enumerate(items))+'\n'
    if not data:return align+'等待首次采样…\n'
    age=time.time()-data.get('sample_unix',0)
    if age>15:return align+'采集已暂停（数据超过 15 秒），请检查诊断日志\n'
    info=data['static'];uptime=int(data.get('uptime_seconds',0));days,rem=divmod(uptime,86400);hours,rem=divmod(rem,3600)
    out=align+'┌───────────────────────────┐\n'
    out+=section('SYSTEM INFO')+rows([clean(info['os'])+' · '+clean(info['arch']),
        '内核 '+clean(info['kernel']),f'运行 {days}天 {hours:02d}:{rem//60:02d}'])
    out+=section('CPU SYSTEM')+rows([clean(info['cpu'],39),
        '使用率 '+pct(data.get('cpu_percent'))+' · 温度 '+temp(data.get('sensors',{}).get('cpu_temperature'))])
    gpu_rows=[]
    for text in gpu_lines(data.get('gpus',[])):
        text=re.sub(r'^[├└]─\s*|^│\s*','',text)
        # Use the readable device name, not the PCI generation codename.
        text=re.sub(r'^.*\[([^\]]+)\](\s*·.*)$', r'\1\2', text)
        gpu_rows.append(text)
    out+=section('GPU SYSTEM')+rows(gpu_rows)
    total=data.get('memory_total');used=data.get('memory_used');percent=100*used/total if total and used is not None else None
    out+=section('MEMORY INFO')+rows([human(used)+' / '+human(total)+' · '+pct(percent)])
    disk=data.get('disks',{});lines=[]
    for d in disk.get('devices',[]):
        lines.extend([clean(d['model'],35)+' · '+d['device'],
                      '读 '+human(d.get('read_bps'),'B/s')+' · 写 '+human(d.get('write_bps'),'B/s')+' · '+temp(d.get('temperature'))])
    lines.append('根分区 '+human(disk.get('root_used'))+' / '+human(disk.get('root_total')))
    out+=section('HARD DISK')+rows(lines)
    lines=['主机 '+clean(info['hostname'])]
    for n in data.get('networks',[]):
        address=', '.join(n.get('addresses',[])) or '未连接'
        lines.extend([n['kind']+' '+clean(n['name'],24)+(' *' if n.get('default_route') else ''),
                      clean(address,42),
                      '↓ '+human(n.get('rx_bps'),'B/s')+' · ↑ '+human(n.get('tx_bps'),'B/s')])
    ip=data.get('public_ip',{});lines.append('公网 IP：'+clean(ip.get('address') or ip.get('status','默认关闭')))
    return out+section('NETWORK INFO')+rows(lines)+align+'└───────────────────────────┘\n'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['collect','render','once'])
    parser.add_argument('--config',default=str(Path(__file__).parent/'config.local.json'))
    parser.add_argument('--state',required=True)
    args=parser.parse_args();os.umask(0o077)
    if args.action=='render':
        try:data=json.loads(Path(args.state).read_text())
        except (OSError,ValueError):data={}
        from classic import render as render_classic
        print(render_classic(data),end='');return
    cfg=config(args.config);collector=Collector(cfg);alive=True
    def stop(*_):
        nonlocal alive
        alive=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while alive:
            start=time.monotonic()
            try:
                data=collector.sample()
                atomic(args.state,data)
                if cfg['layout']=='classic':
                    from classic import render as render_classic
                    atomic_text(Path(args.state).with_suffix('.text'),render_classic(data))
            except Exception as error:
                print('collector error: '+type(error).__name__+': '+str(error),file=sys.stderr,flush=True)
            if args.action=='once':break
            remaining=cfg['sample_seconds']-(time.monotonic()-start)
            end=time.monotonic()+max(.1,remaining)
            while alive and time.monotonic()<end:time.sleep(min(.2,max(.01,end-time.monotonic())))
    finally:collector.pool.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__':main()
