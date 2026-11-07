#!/usr/bin/env python3
"""Desktop-only top-tree preview, reusing the installed collector's cache."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from conky_tree import atomic, atomic_text, config, run
from start import monitors, validate_monitor
from top_tree import XftMeasure, layout, render, make_config, FONT, geometry



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('/run/user')/str(os.getuid())/'conky-classic-tree/stats.json')
    parser.add_argument('--installed',type=Path,default=Path.home()/'.config/conky/classic-tree')
    parser.add_argument('--stop',action='store_true')
    args=parser.parse_args();os.umask(0o077)
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/'conky-top-preview'
    runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
    manifest=runtime/'processes.json'
    if args.stop:
        if not manifest.exists():print('No top preview is running');return
        pid=json.loads(manifest.read_text())['launcher'];handle=os.pidfd_open(pid)
        try:
            argv=(Path('/proc')/str(pid)/'cmdline').read_bytes().split(b'\0')
            if str(Path(__file__).resolve()).encode() not in argv:
                raise RuntimeError('Preview PID identity mismatch; no signal sent')
            signal.pidfd_send_signal(handle,signal.SIGTERM)
        finally:os.close(handle)
        print('Requested only this top preview to stop');return
    lock=(runtime/'instance.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise RuntimeError('Top preview is already running')
    cfg=config(args.installed/'config.local.json');head=validate_monitor(cfg,monitors())
    data=json.loads(args.source.read_text())
    if time.time()-data.get('sample_unix',0)>15:raise RuntimeError('Formal collector cache is not fresh')
    geo=geometry(head,run(['xprop','-root','RESOURCE_MANAGER']),
                 run(['xprop','-root','_NET_WORKAREA']),run(['xprop','-root','_NET_CURRENT_DESKTOP']))
    measure=XftMeasure();child=None;windows=None;comparison=None
    stop=False
    def requested(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    try:
        spec=layout(data,head['width']-2*geo['gap_x'],geo['scale'],measure)
        state=runtime/'stats.text'
        atomic_text(state,render(data,spec,measure))
        generated=runtime/'conky.conf'
        generated.write_text(make_config(args.installed/'original-template.conf',state,spec,
                                         cfg['monitor_index'],geo['gap_x'],geo['gap_y']))
        atomic(runtime/'layout.json',dict(spec.__dict__,**{k:v for k,v in geo.items() if k!='scale'},monitor=head,source=str(args.source),
                                        font=FONT,telemetry_collectors_added=0))
        child=subprocess.Popen(['conky','-c',str(generated)])
        atomic(manifest,{'launcher':os.getpid(),'conky':child.pid,'source':str(args.source)})
        from preview_windows import Windows, comparison_position
        windows=Windows()
        checked=time.monotonic()
        compare_until=checked+5
        compared=False
        while not stop and child.poll() is None:
            if not compared:
                old=windows.find(('conky','conky'));new=windows.find(('ConkyTopPreview','ConkyTopPreview'))
                if len(old)==1 and len(new)==1:
                    previous=windows.geometry(old[0]);new_geo=windows.geometry(new[0])
                    position=comparison_position(previous,new_geo,head,round(12*geo['scale']))
                    if position:
                        comparison={'window':old[0],'original':previous,'temporary':position}
                        windows.move(old[0],**position)
                        atomic(runtime/'comparison.json',comparison)
                    compared=True
                elif time.monotonic()>compare_until:
                    raise RuntimeError('Comparison windows ambiguous; no original window moved')
            try:data=json.loads(args.source.read_text())
            except (OSError,ValueError):data={}
            atomic_text(state,render(data,spec,measure))
            if time.monotonic()-checked>10:
                validate_monitor(cfg,monitors());checked=time.monotonic()
            until=time.monotonic()+cfg['sample_seconds']
            while not stop and time.monotonic()<until:time.sleep(.2)
        if not stop and child.returncode not in [None,0]:raise RuntimeError('Preview Conky exited')
    finally:
        if child and child.poll() is None:
            child.terminate()
            try:child.wait(timeout=4)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if windows:
            if comparison and comparison['window'] in windows.find(('conky','conky')):
                actual=windows.geometry(comparison['window'])
                if all(actual[k]==comparison['temporary'][k] for k in ['x','y']):
                    original=comparison['original'];windows.move(comparison['window'],original['x'],original['y'])
            windows.close()
        (runtime/'comparison.json').unlink(missing_ok=True)
        manifest.unlink(missing_ok=True);measure.close()


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError) as error:
        print('Top Conky preview: '+str(error),file=sys.stderr)
        sys.exit(1)
