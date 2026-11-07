#!/usr/bin/env python3
"""Keep the accepted template's visual style; replace unsafe hardware commands."""
import argparse
import json
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
    return '—' if value is None else f'{value:.1f}%'


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
        name = g.get('name', 'GPU')
        match = re.search(r'\[([^\]]+)\]', name)
        if match:
            name = match[1]
        if g.get('vendor') == '0x8086' and 'intel' not in name.lower():
            name = 'Intel ' + name
        values.append('< ' + fit(name, 32) + ' · ' + fit(g.get('driver') or '无驱动', 8) + ' >')
        if g.get('role') == 'discrete':
            state = g.get('state')
            status = '驱动未接管' if not g.get('driver') else '活动' if state == 'active' else '挂起，不主动查询' if state == 'suspended' else '电源状态不可读'
            if state == 'active' and g.get('driver') and g.get('utilization') is None:
                status += ' · 遥测不可用'
            active = bool(g.get('driver')) and state == 'active'
            values.append('状态：' + status)
            values.append('< ' + percent(g.get('utilization') if active else None) + ' > 负载 · ' +
                          temperature(g.get('temperature') if active else None))
            used, total, power = (g.get(k) if active else None for k in ['memory_used', 'memory_total', 'power'])
            memory = f'{used:.0f}/{total:.0f} MiB' if used is not None and total is not None else '—'
            values.append('显存 ' + memory + ' · 功耗 ' + (f'{power:.1f} W' if power is not None else '—'))
    if not any(g.get('role') == 'discrete' for g in gpus):
        values.append('独显：未枚举')
    elif not any(g.get('role') == 'integrated' for g in gpus):
        values.append('核显：未枚举')
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
    prefix, rest = body.split('# --- CPU ---\n', 1)
    prefix = re.sub(r'\$\{execi 1000 [^\n]+?\}', lambda _: fit(static.get('os', '系统信息不可用'), 36), prefix)
    _, rest = rest.split('# --- GPU ---\n', 1)
    _, rest = rest.split('# --- MEMORY ---\n', 1)
    memory, rest = rest.split('# --- DISK ---\n', 1)
    if not data.get('memory_total') or data.get('memory_used') is None:
        memory=memory.replace('${mem}','不可用').replace('${memmax}','不可用').replace('${memperc}','—')
    rest.split('# ---NET---\n', 1)  # Require the expected template boundary.
    # Headers and tree suffixes use the accepted original theme, not a new layout.
    cpu = '${alignr}${color4}CPU SYSTEM${color} ─┤\n'
    cpu_name = re.sub(r'\((?:R|TM)\)', '', static.get('cpu', 'CPU 型号不可读'), flags=re.I)
    cpu_name = re.sub(r'\s+', ' ', cpu_name).strip()
    cpu += rows(['<' + fit(cpu_name, 25) + '>',
                 '< ' + percent(None if stale else data.get('cpu_percent')) + ' > 使用率',
                 '< ' + temperature(None if stale else data.get('sensors', {}).get('cpu_temperature'), cpu=True) + ' > 温度'])
    cpu += '${alignr}│\n${alignr}│\n'
    gpus = data.get('gpus', [])
    if stale:
        gpus = [dict(g, engines={}, utilization=None, temperature=None, power=None, memory_used=None, memory_total=None) for g in gpus]
    gpu = '${alignr}${color4}GPU SYSTEM${color} ─┤\n' + rows(gpu_rows(gpus)) + '${alignr}│\n'
    if stale:
        gpu = gpu.replace('[ ' + topology(gpus) + ' ]', '[ 采集暂停/等待 · ' + topology(gpus) + ' ]')
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
    # The original memory/root filesystem variables and typography remain native.
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
    # All style values are inherited unchanged. Only supervision, buffer size
    # and explicit monitor pinning are runtime changes.
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
