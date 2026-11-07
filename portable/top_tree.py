"""Measured five-column tree renderer. No telemetry or installed-layout changes."""
import ctypes
import ctypes.util
import math
import re
import time
from dataclasses import dataclass
from pathlib import Path

from classic import gpu_rows, memory_gb, percent, speed, temperature
from conky_tree import clean, network_total

FONT_SIZE = 7.5
FONT = f'Noto Sans CJK SC:bold:size={FONT_SIZE}'
SIZE_RATIO = FONT_SIZE / 10
VARIABLES = {
    '${uptime}': '9999d 23h 59m 59s',
    '${kernel}': '6.14.0-36-generic',
    '${fs_used /}': '9999.9GiB', '${fs_size /}': '9999.9GiB',
    '${fs_used_perc /}': '100',
}


def visible(text):
    def substitute(match):
        token = match.group()
        if token.startswith('${color'):
            return ''
        if token in VARIABLES:
            return VARIABLES[token]
        raise ValueError('Unexpected Conky variable: ' + token)
    return re.sub(r'\$\{[^}]+\}', substitute, text)


class XftMeasure:
    """Use the same Xft font resolution and DPI as Conky, via existing libs."""
    def __init__(self):
        self.x = ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
        self.f = ctypes.CDLL(ctypes.util.find_library('Xft') or 'libXft.so.2')
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XDefaultScreen.argtypes = [ctypes.c_void_p]
        self.x.XDefaultScreen.restype = ctypes.c_int
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.f.XftFontOpenName.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p]
        self.f.XftFontOpenName.restype = ctypes.c_void_p
        self.f.XftFontClose.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        class Extents(ctypes.Structure):
            _fields_ = [('width',ctypes.c_ushort),('height',ctypes.c_ushort),
                        ('x',ctypes.c_short),('y',ctypes.c_short),
                        ('xOff',ctypes.c_short),('yOff',ctypes.c_short)]
        self.extents_type = Extents
        self.f.XftTextExtentsUtf8.argtypes = [ctypes.c_void_p,ctypes.c_void_p,
                                              ctypes.c_char_p,ctypes.c_int,ctypes.POINTER(Extents)]
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError('X11/XWayland display unavailable')
        self.font = self.f.XftFontOpenName(self.display,self.x.XDefaultScreen(self.display),FONT.encode())
        if not self.font:
            self.x.XCloseDisplay(self.display)
            raise RuntimeError('Cannot resolve the existing Conky font')
        self.cache = {}

    def __call__(self, text):
        text = visible(text)
        if text not in self.cache:
            if len(self.cache)>=8192:self.cache.clear()
            raw = text.encode('utf-8'); value = self.extents_type()
            self.f.XftTextExtentsUtf8(self.display,self.font,raw,len(raw),ctypes.byref(value))
            self.cache[text] = max(value.xOff, value.width-value.x)
        return self.cache[text]

    def close(self):
        if self.display:
            self.f.XftFontClose(self.display,self.font)
            self.x.XCloseDisplay(self.display)
            self.display = None


def wrap(text, width, measure):
    """Wrap actual glyph widths; expressions remain atomic and never execute."""
    lines = []; line = ''
    for token in re.findall(r'\$\{[^}]+\}|.', text):
        if measure(line+token)>width:
            if not line or measure(token)>width:
                raise RuntimeError('Column too narrow for an unchanged data field')
            lines.append(line); line = ''
        line += token
    return lines + ([line] if line else []) or ['']


def compact_gpu(gpus):
    # Reuse the accepted state/scope rules; remove only visual punctuation.
    return [re.sub(r'^< (.*?) > (.*)$',r'\2  \1',row).removeprefix('[ ').removesuffix(' ]')
            for row in gpu_rows(gpus)]


def blocks(data, stale=False, split_rates=False):
    static=data.get('static',{})
    system=['运行时间 ${uptime}',clean(static.get('os','系统信息不可用'),200),
            '内核 '+clean(static.get('kernel','不可用'),200)]
    gpus=data.get('gpus',[])
    if stale:
        gpus=[dict(g,engines={},utilization=None) for g in gpus]
    loads=['CPU  '+percent(None if stale else data.get('cpu_percent'))]+compact_gpu(gpus)
    if stale:
        loads[1]='采集暂停/等待 · '+loads[1]
    net=network_total([] if stale else data.get('networks',[]))
    def rate(key):
        return '—' if net[key] is None else speed(net[key])+'/s'
    memory=['内存 '+memory_gb(data,stale),'下载 ↓ '+rate('rx_bps'),'上传 ↑ '+rate('tx_bps')]
    disks=[[],[]]
    for i,d in enumerate(data.get('disks',{}).get('devices',[])):
        cells=[clean(d.get('model') or d.get('device','未知硬盘'),200)]
        read='读 '+speed(None if stale else d.get('read_bps'))+'/s'
        write='写 '+speed(None if stale else d.get('write_bps'))+'/s'
        cells += [read,write] if split_rates else [read+'  '+write]
        cells += ['温度 '+temperature(None if stale else d.get('temperature'))]
        if i>=2:
            cells.insert(0,'硬盘 '+str(i+1))
        disks[i%2].extend(cells)
    if not any(disks):
        disks[0]=['硬盘信息：不可用']
    if not disks[1]:
        disks[1]=['无第二块硬盘']
    root=('根分区 ${fs_used /}/${fs_size /} (${fs_used_perc /}%)'
          if data.get('disks',{}).get('root_total') else '根分区 不可用')
    return [system,loads,memory,*disks],root


@dataclass
class Layout:
    widths: list
    gap: int
    branch: int
    width: int
    split_rates: bool
    scale: float


def layout(data, available, scale, measure):
    groups,_=blocks(data)
    titles=['系统','CPU / GPU','内存 / 网络','硬盘 1','硬盘 2']
    reserves=[['运行时间 ${uptime}'],['CPU  100.0%','核显渲染（本用户）  100.0%',
                '核显（驱动未接管）  不可用','独显占用  不可用'],
              ['内存 ≈9999.99 GB / 9999.99 GB','下载 ↓ 999.9GiB/s','上传 ↑ 999.9GiB/s'],
              ['读 999.9GiB/s  写 999.9GiB/s','温度 不可用'],
              ['读 999.9GiB/s  写 999.9GiB/s','温度 不可用']]
    gap=round(12*scale*SIZE_RATIO);branch=measure('├─ ')+round(5*scale*SIZE_RATIO)
    widths=[math.ceil(max(measure(s) for s in [titles[i],*g,*reserves[i]])+branch)
            for i,g in enumerate(groups)]
    limit=available-gap*4
    floors=[math.ceil(100*scale*SIZE_RATIO+branch)]*3+[math.ceil(measure('写 999.9GiB/s')+branch)]*2
    # First wrap disk models/combined rates, then other long text if necessary.
    for i in [3,4,2,1,0]:
        excess=sum(widths)-limit
        if excess<=0:break
        widths[i]-=min(excess,max(0,widths[i]-floors[i]))
    if sum(widths)>limit:
        raise RuntimeError('Five readable columns do not fit this monitor; font unchanged')
    split=any(measure(reserves[i][0])>widths[i]-branch for i in [3,4])
    return Layout(widths,gap,branch,sum(widths)+4*gap,split,scale)


def render(data, spec, measure, now=None):
    stale=not data or (time.time() if now is None else now)-data.get('sample_unix',0)>15
    groups,root=blocks(data,stale,spec.split_rates)
    titles=['系统','CPU / GPU','内存 / 网络','硬盘 1','硬盘 2']
    columns=[]
    for i,items in enumerate(groups):
        content=[part for s in items for part in wrap(s,spec.widths[i]-spec.branch,measure)]
        columns.append([titles[i],*content])
    # All columns are branches of ONE common trunk; do not terminate the
    # first three early, or the result becomes five unrelated small trees.
    trunk_row=max(len(col) for col in columns)
    lines=[[] for _ in range(trunk_row+2)]
    starts=[];x=0
    for w in spec.widths:
        starts.append(x);x+=w+spec.gap
    def at(row,x,text):
        lines[row].append((x,text))
    stems=starts[:]
    for i,col in enumerate(columns):
        stem=stems[i]
        for y,text in enumerate(col):
            at(y,stem,'┌─' if y==0 else '├─')
            at(y,stem+spec.branch,('${color4}'+text+'${color}') if y==0 else text)
        for y in range(len(col),trunk_row):at(y,stem,'│')
    # Left-hand stems and right-facing branches follow left-aligned text.
    # All five stems still join one trunk; the final root-filesystem branch
    # belongs to the common tree, not to either physical drive.
    step=measure('─')
    for left,right in zip(stems,stems[1:]):
        hop=max(1,step-round(2*spec.scale*SIZE_RATIO))
        pos=left+step
        while pos<right:
            at(trunk_row,min(pos,right-step),'─');pos+=hop
    for i,stem in enumerate(stems):
        at(trunk_row,stem,'├' if i==0 else '┘' if i==len(stems)-1 else '┴')
    # Bridge Noto's line-gap without changing baselines or window height.
    bridge_offset=round(FONT_SIZE)
    bridge=f'${{voffset -{bridge_offset}}}│${{voffset {bridge_offset}}}'
    for y in range(1,trunk_row+1):
        for stem in stems:at(y,stem,bridge)
    root_lines=wrap(root,spec.width-spec.branch,measure)
    while len(lines)<trunk_row+1+len(root_lines):lines.append([])
    for offset,text in enumerate(root_lines):
        at(trunk_row+1+offset,stems[0],bridge)
        at(trunk_row+1+offset,stems[0],'└─' if offset==len(root_lines)-1 else '├─')
        at(trunk_row+1+offset,stems[0]+spec.branch,text)
    output='\n'.join(''.join('${goto '+str(round(x/spec.scale))+'}'+text for x,text in sorted(row,key=lambda item:item[0])) for row in lines)+'\n'
    if re.search(r'\$\{(?:exec|texec|lua|curl)',output):
        raise ValueError('Unexpected executable Conky expression')
    return output


def make_config(template, state, spec, monitor_index, gap_x, gap_y, preview=True, xwayland_backend=False):
    settings=Path(template).read_text().split('conky.text = [=[',1)[0]
    settings=re.sub(r'^\s*(?:minimum_height|minimum_width|maximum_width|gap_x|gap_y|uppercase)\s*=.*?,[^\n]*\n','\n',settings,flags=re.M)
    settings=re.sub(r"^\s*font\s*=\s*'[^']*',", "\n    font = '"+FONT+"',", settings, flags=re.M)
    settings=re.sub(r'background\s*=\s*true','background = false',settings,count=1)
    settings=re.sub(r'text_buffer_size\s*=\s*4096','text_buffer_size = 65536',settings,count=1)
    window_class="ConkyTopPreview" if preview else "ConkyTopTree"
    additions=(f"\n    xinerama_head = {monitor_index},\n    own_window_class = '{window_class}',"
               f"\n    minimum_width = {math.ceil(spec.width/spec.scale)},\n    maximum_width = {math.ceil(spec.width/spec.scale)},"
               f"\n    gap_x = {round(gap_x/spec.scale)},\n    gap_y = {round(gap_y/spec.scale)},\n    uppercase = false,"
               "\n    border_inner_margin = 0,\n    border_outer_margin = 0,\n    border_width = 0,\n    draw_borders = false,")
    if xwayland_backend:additions+='\n    out_to_x = true,\n    out_to_wayland = false,'
    settings=settings.replace('conky.config = {','conky.config = {'+additions,1)
    path=str(state)
    if any(c in path for c in '\n\r{}[]'):raise ValueError('Unsupported runtime path')
    return settings+'conky.text = [=[\n${catp '+path+'}]=]\n'


def geometry(head, resources, workareas, desktop):
    match=re.search(r'Xft\.dpi[^\d]*(\d+(?:\.\d+)?)',resources or '')
    scale=float(match.group(1))/96 if match else 1
    if not .5<=scale<=4:raise RuntimeError('Invalid font DPI')
    top=head['y'];reason='workarea unavailable; retained original 20px top offset'
    payload=(workareas or '').partition('=')[2]
    values=[int(x) for x in re.findall(r'-?\d+',payload)]
    areas=[values[i:i+4] for i in range(0,len(values)-3,4)]
    index=re.search(r'=\s*(\d+)',desktop or '')
    area=areas[int(index.group(1))] if index and int(index.group(1))<len(areas) else None
    if area is None and areas and all(a==areas[0] for a in areas):area=areas[0]
    valid=(area and area[0]<=head['x'] and area[0]+area[2]>=head['x']+head['width']
           and head['y']<=area[1]<head['y']+head['height'])
    if valid:
        top=area[1]+round(4*scale);reason='verified workarea + 4 logical pixels'
    else:top+=20
    return {'scale':scale,'gap_x':round(15*scale),'gap_y':top-head['y'],
            'target_top':top,'workarea':area if valid else None,'position_reason':reason}

