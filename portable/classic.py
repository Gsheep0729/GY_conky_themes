#!/usr/bin/env python3
"""Keep the accepted template's visual style; replace unsafe hardware commands."""
import argparse
import json
import math
import re
import time
import unicodedata
from pathlib import Path
from conky_tree import clean, human, topology, network_total

TEMPLATE = Path(__file__).with_name('original-template.conf')
TREE = ' ─┤   │'
END = ' ─┘   │'


def fit(value, cells=34):
    value = clean(value, 200)
    result = ''
    for ch in value:
        width = 2 if unicodedata.east_asian_width(ch) in 'WF' else 1
        if cells < width:
            return result + '…'
        result += ch
        cells -= width
    return result


def percent(value):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=100:
        return '不可用'
    return f'{value:.1f}%'


def memory_gb(data, stale=False):
    if stale:
        return '不可用'
    def capacity(value, minimum):
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or value<minimum:
            return '不可用'
        return f'{value/1_000_000_000:.2f} GB'
    used=capacity(data.get('memory_used'),0)
    total=capacity(data.get('memory_total'),1)
    if used!='不可用' and data.get('memory_method')=='legacy estimate':
        used='≈'+used
    return used+' / '+total


def speed(value):
    # Match the old compact rate columns; long B/s strings widen every row.
    return human(value).replace(' ', '')


def temperature(value, cpu=False):
    if value is None:
        return '不可用'
    color = '${color3}' if value > (70 if cpu else 50) else '${color2}' if not cpu and value > 40 else '${color}'
    return color + f'{value:.0f}°C' + '${color}'


def rows(values):
    return '\n'.join('${alignr}' + value + (END if i == len(values)-1 else TREE)
                     for i, value in enumerate(values)) + '\n'


def gpu_rows(gpus):
    values = ['[ ' + topology(gpus) + ' ]']
    for g in gpus:
        if g.get('role') != 'discrete':
            label = '核显' if g.get('role') == 'integrated' else 'GPU'
            value = g.get('utilization')
            if value is not None:
                label += '忙碌率'
            else:
                value = g.get('engines', {}).get('render')
                label += '渲染（本用户）'
            if not g.get('driver'):
                value = None
                label = ('核显' if g.get('role') == 'integrated' else 'GPU') + '（驱动未接管）'
            values.append('< ' + percent(value) + ' > ' + label)
            continue
        if g.get('driver') and g.get('state')=='suspended':
            values.append('独显：挂起')
        else:
            value=g.get('utilization') if g.get('driver') and g.get('state')=='active' else None
            values.append('< '+percent(value)+' > 独显占用')
    if not gpus:
        values.append('占用率：不可用')
    return values


def network_rows(networks):
    total=network_total(networks)
    def value(field):
        v=total[field]
        return '—' if v is None else speed(v)+'/s'
    return rows(['< '+value('rx_bps')+'↓ '+value('tx_bps')+'↑ > 总速率'])


def render(data, template=None):
    source = (TEMPLATE if template is None else Path(template)).read_text()
    body = source.split('conky.text = [=[\n', 1)[1].rsplit(']=]', 1)[0]
    stale = not data or time.time() - data.get('sample_unix', 0) > 15
    static = data.get('static', {})
    # Preserve the accepted uptime typography, but omit the wall clock/date.
    uptime=next(line for line in body.splitlines() if '${uptime}' in line)
    prefix=uptime+'\n${alignr}└────────┐\n'
    prefix+='${alignr}'+fit(static.get('os','系统信息不可用'),36)+' ─┤\n'
    prefix+='${alignr}< ${kernel} > 内核版本 ─┘   │\n${alignr}│\n'
    cpu = '${alignr}${color4}CPU SYSTEM${color} ─┤\n'
    cpu += rows(['< '+percent(None if stale else data.get('cpu_percent'))+' > 使用率'])
    cpu += '${alignr}│\n'
    gpus = data.get('gpus', [])
    if stale:
        gpus = [dict(g, engines={}, utilization=None, temperature=None, power=None, memory_used=None, memory_total=None) for g in gpus]
    gpu = '${alignr}${color4}GPU SYSTEM${color} ─┤\n' + rows(gpu_rows(gpus)) + '${alignr}│\n'
    if stale:
        gpu = gpu.replace('[ ' + topology(gpus) + ' ]', '[ 采集暂停/等待 · ' + topology(gpus) + ' ]')
    memory='${alignr}${color4}MEMORY INFO${color} ─┤\n'
    memory+=rows(['< '+memory_gb(data,stale)+' > 已用/总量'])+'${alignr}│\n'
    disks = data.get('disks', {}).get('devices', [])
    disk = '${alignr}${color4}HARD DISK${color} ─┤\n'
    disk_values = []
    for i, d in enumerate(disks, 1):
        disk_values.append('硬盘' + str(i) + '：' + fit(d.get('model') or d['device'], 35))
        disk_values.append('< ' + speed(None if stale else d.get('read_bps')) + ' >读,< ' +
                           speed(None if stale else d.get('write_bps')) + ' >写,< ' +
                           temperature(None if stale else d.get('temperature')) + ' > 温度')
    if not disks:
        disk_values.append('硬盘信息：不可用')
    # Root filesystem values and all disk rows retain the previous display.
    if data.get('disks',{}).get('root_total'):
        disk_values.append('< ${fs_used /}/${fs_size /} (${fs_used_perc /}%) > 根分区')
    else:
        disk_values.append('< 不可用 > 根分区')
    disk += rows(disk_values) + '${alignr}│\n'
    network = '${alignr}${color4}NETWORK INFO${color} ─┤\n'
    network += network_rows([] if stale else data.get('networks', []))
    network += '${alignr}───────────────────────────┘\n'
    combined = prefix + cpu + gpu + memory + disk + network
    # Comments in a template are filtered at startup; they must not become text
    # when the same body is loaded with Conky's catp variable.
    result = '\n'.join(line for line in combined.splitlines() if not line.lstrip().startswith('#')) + '\n'
    if re.search(r'\$\{(?:exec|texec|lua|curl)', result):
        raise ValueError('A legacy external command survived the classic conversion')
    return result


def make_config(cfg, head, base, state):
    source = (Path(base)/'original-template.conf').read_text()
    settings = source.split('conky.text = [=[', 1)[0]
    settings = re.sub(r'background\s*=\s*true', 'background = false', settings, count=1)
    # The compact window follows content height; remaining visual settings
    # continue to come from the accepted original template.
    settings=re.sub(r'^\s*minimum_height\s*=\s*700,\s*$', '', settings, flags=re.M)
    settings = re.sub(r'text_buffer_size\s*=\s*4096', 'text_buffer_size = 16384', settings, count=1)
    settings = settings.replace('conky.config = {', 'conky.config = {\n    xinerama_head = ' + str(cfg['monitor_index']) + ',', 1)
    path = str(Path(state).with_suffix('.text'))
    if any(ch in path for ch in ['\n', '\r', '}', '[', ']']):
        raise ValueError('Unsupported runtime path')
    return settings + 'conky.text = [=[\n${catp ' + path + '}]=]\n'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--state', required=True)
    args = p.parse_args()
    try:
        data = json.loads(Path(args.state).read_text())
    except (OSError, ValueError):
        data = {}
    print(render(data), end='')
