#!/usr/bin/env python3
"""Standalone top-tree supervisor: one private collector and one Conky."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from conky_tree import atomic, atomic_text, config, run
from start import monitors, validate_monitor
from top_tree import FONT, XftMeasure, geometry, layout, make_config, render


def load_fresh(path, now=None):
    try:
        data=json.loads(Path(path).read_text())
        age=(time.time() if now is None else now)-data.get('sample_unix',0)
        if 0<=age<=15:return data
    except (OSError,ValueError,TypeError,AttributeError):pass
    return None


def stop_children(children):
    for child in reversed(children):
        if child.poll() is None:child.terminate()
    for child in children:
        try:child.wait(timeout=4)
        except subprocess.TimeoutExpired:child.kill();child.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=Path(__file__).parent/'config.local.json')
    parser.add_argument('--delay',type=int)
    parser.add_argument('--xwayland-backend',action='store_true',help='Explicit backend for the reviewed Manjaro Conky build')
    parser.add_argument('--check',action='store_true',help='Collect fresh data and generate the config, without opening Conky')
    args=parser.parse_args();os.umask(0o077)
    cfg=config(args.config);base=Path(__file__).resolve().parent
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/'conky-classic-tree'
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=(runtime/'instance.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('Conky Classic/Top Tree is already running');return
    if not shutil.which('conky'):raise RuntimeError('Conky is not installed')
    stop=False;children=[];measure=None
    def requested(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    delay=cfg['start_delay'] if args.delay is None else args.delay
    until=time.monotonic()+max(0,delay)
    while not stop and time.monotonic()<until:time.sleep(.2)
    if stop:return
    head=validate_monitor(cfg,monitors())
    geo=geometry(head,run(['xprop','-root','RESOURCE_MANAGER']),
                 run(['xprop','-root','_NET_WORKAREA']),run(['xprop','-root','_NET_CURRENT_DESKTOP']))
    state=runtime/'stats.json';text=runtime/'top.text';generated=runtime/'conky.conf'
    logdir=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'conky-classic-tree'
    logdir.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (logdir/'runtime.log').open('a') as log:
        try:
            state.unlink(missing_ok=True)
            collector=subprocess.Popen([sys.executable,str(base/'conky_tree.py'),'collect',
                '--config',str(args.config),'--state',str(state)],stdout=log,stderr=log)
            children.append(collector)
            deadline=time.monotonic()+15;data=None
            while not stop and collector.poll() is None and time.monotonic()<deadline:
                data=load_fresh(state)
                if data is not None:break
                time.sleep(.2)
            if stop:return
            if data is None:raise RuntimeError('No fresh sample from standalone collector')
            measure=XftMeasure()
            spec=layout(data,head['width']-2*geo['gap_x'],geo['scale'],measure)
            atomic_text(text,render(data,spec,measure))
            generated.write_text(make_config(base/'original-template.conf',text,spec,cfg['monitor_index'],
                geo['gap_x'],geo['gap_y'],preview=False,xwayland_backend=args.xwayland_backend))
            atomic(runtime/'layout.json',dict(spec.__dict__,**{k:v for k,v in geo.items() if k!='scale'},
                monitor=head,font=FONT,standalone=True))
            if args.check:
                print(json.dumps({'status':'standalone-configuration-generated','collector':collector.pid,
                    'config':str(generated),'font':FONT,'width_pixels':spec.width},ensure_ascii=False));return
            conky=subprocess.Popen(['conky','-c',str(generated)],stdout=log,stderr=log)
            children.append(conky)
            atomic(runtime/'processes.json',{'launcher':os.getpid(),'collector':collector.pid,
                'conky':conky.pid,'monitor':head,'layout':'top-tree-7.5pt'})
            checked=time.monotonic()
            while not stop and all(p.poll() is None for p in children):
                data=load_fresh(state)
                if data is None:raise RuntimeError('Collector cache stale/unreadable; stopped to avoid stale readings')
                atomic_text(text,render(data,spec,measure))
                if time.monotonic()-checked>10:
                    if validate_monitor(cfg,monitors())!=head:
                        raise RuntimeError('Display geometry changed; restart after checking fixed monitor')
                    checked=time.monotonic()
                until=time.monotonic()+cfg['sample_seconds']
                while not stop and time.monotonic()<until:time.sleep(.2)
            if not stop and any(p.poll() not in [None,0] for p in children):
                raise RuntimeError('Conky/collector exited; see '+str(logdir/'runtime.log'))
        finally:
            stop_children(children)
            (runtime/'processes.json').unlink(missing_ok=True)
            if measure:measure.close()


if __name__=='__main__':
    try:main()
    except (OSError,RuntimeError,ValueError) as error:
        print('Top Conky: '+str(error),file=sys.stderr)
        run(['notify-send','Conky未启动',str(error)],timeout=3)
        sys.exit(1)
