#!/usr/bin/env python3
"""Own exactly one Conky process and its unprivileged telemetry collector."""
import argparse
import ctypes
import ctypes.util
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from conky_tree import config, DEFAULTS, atomic, run

def monitors():
    class Screen(ctypes.Structure):
        _fields_=[('number',ctypes.c_int),('x',ctypes.c_short),('y',ctypes.c_short),
                  ('width',ctypes.c_short),('height',ctypes.c_short)]
    x11=ctypes.CDLL(ctypes.util.find_library('X11') or 'libX11.so.6')
    xi=ctypes.CDLL(ctypes.util.find_library('Xinerama') or 'libXinerama.so.1')
    x11.XOpenDisplay.argtypes=[ctypes.c_char_p];x11.XOpenDisplay.restype=ctypes.c_void_p
    x11.XCloseDisplay.argtypes=[ctypes.c_void_p];x11.XFree.argtypes=[ctypes.c_void_p]
    xi.XineramaQueryScreens.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)]
    xi.XineramaQueryScreens.restype=ctypes.POINTER(Screen)
    display=x11.XOpenDisplay(None)
    if not display:raise RuntimeError('Cannot connect to DISPLAY; X11/XWayland is required')
    try:
        count=ctypes.c_int();screens=xi.XineramaQueryScreens(display,ctypes.byref(count))
        result=[{'index':i,'x':screens[i].x,'y':screens[i].y,'width':screens[i].width,'height':screens[i].height}
                for i in range(count.value)]
        if screens:x11.XFree(screens)
        if not result:raise RuntimeError('No Xinerama screen; run doctor after enabling XWayland')
        return result
    finally:x11.XCloseDisplay(display)

def validate_monitor(cfg, heads):
    import re
    i=cfg['monitor_index']
    if i>=len(heads):raise RuntimeError('Configured monitor index is absent; refusing to move to another screen')
    head=heads[i];connector=cfg.get('expected_connector')
    if connector:
        text=run(['xrandr','--query'])
        if not text:raise RuntimeError('xrandr required to validate configured internal connector')
        line=next((l for l in text.splitlines() if l.startswith(connector+' connected')),None)
        match=re.search(r'(\d+)x(\d+)([+-]\d+)([+-]\d+)',line or '')
        if not match:raise RuntimeError('Configured internal connector is inactive; refusing external-screen fallback')
        w,h,x,y=map(int,match.groups())
        if (head['x'],head['y'],head['width'],head['height'])!=(x,y,w,h):
            raise RuntimeError('Fixed monitor index no longer matches '+connector+'; run doctor and update local config')
    return head

def make_config(cfg, head, base, state):
    from classic import make_config as make_classic_config
    return make_classic_config(cfg, head, base, state)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default=str(Path(__file__).parent/'config.local.json'))
    parser.add_argument('--delay',type=int)
    parser.add_argument('--doctor',action='store_true')
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--preview',action='store_true',help='Temporary side-by-side preview; never installs autostart')
    parser.add_argument('--preview-seconds',type=int,default=300,help='0 keeps a preview until explicitly stopped or logged out')
    args=parser.parse_args();os.umask(0o077)
    cfg=config(args.config);base=Path(__file__).resolve().parent
    if args.doctor:
        print(json.dumps({'session':os.environ.get('XDG_SESSION_TYPE','unknown'),
              'conky':shutil.which('conky'),'python':sys.version.split()[0],
              'monitors':monitors(),'configuration':cfg,
              'warning':'Only actually tested desktop/session combinations are validated'},ensure_ascii=False,indent=2));return
    if cfg['layout']=='top':
        if args.preview:raise RuntimeError('Use preview_top.py for top-layout comparisons')
        from top_start import main as top_main
        top_main();return
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))/('conky-classic-preview' if args.preview else 'conky-classic-tree')
    runtime.mkdir(mode=0o700,parents=True,exist_ok=True)
    lock=(runtime/'instance.lock').open('w')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('Conky Classic Tree is already running');return
    if not shutil.which('conky'):raise RuntimeError('Conky is not installed; see distro package prerequisites')
    stop=False;children=[]
    def requested(*_):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,requested);signal.signal(signal.SIGINT,requested)
    delay=cfg['start_delay'] if args.delay is None else args.delay
    until=time.monotonic()+max(0,delay)
    while not stop and time.monotonic()<until:time.sleep(.2)
    if stop:return
    head=validate_monitor(cfg,monitors());state=runtime/'stats.json';generated=runtime/'conky.conf'
    generated_text=make_config(cfg,head,base,state)
    if args.preview:
        generated_text=generated_text.replace('gap_x = 15,','gap_x = 450,')
        generated_text=generated_text.replace('conky.config = {',"conky.config = {\n    own_window_class = 'ConkyClassicPreview',")
    generated.write_text(generated_text)
    if args.check:
        print(json.dumps({'status':'configuration-generated','monitor':head,'config':str(generated)},ensure_ascii=False));return
    state.unlink(missing_ok=True)
    from conky_tree import atomic_text
    from classic import render as render_classic
    atomic_text(state.with_suffix('.text'),render_classic({}))
    logdir=Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/('conky-classic-preview' if args.preview else 'conky-classic-tree')
    logdir.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (logdir/'runtime.log').open('a') as log:
        try:
            collector=subprocess.Popen([sys.executable,str(base/'conky_tree.py'),'collect','--config',args.config,'--state',str(state)],stdout=log,stderr=log)
            children.append(collector)
            conky=subprocess.Popen(['conky','-c',str(generated)],stdout=log,stderr=log)
            children.append(conky)
            atomic(runtime/'processes.json',{'launcher':os.getpid(),'collector':collector.pid,'conky':conky.pid,'monitor':head})
            launched=time.monotonic()
            checked_monitor=launched
            while not stop and all(p.poll() is None for p in children):
                if args.preview and args.preview_seconds>0 and time.monotonic()-launched>=max(10,args.preview_seconds):break
                if time.monotonic()-launched>20 and (not state.exists() or time.time()-state.stat().st_mtime>15):
                    raise RuntimeError('Collector stopped updating for 15 seconds; stopped this Conky to avoid stale readings')
                if time.monotonic()-checked_monitor>10:
                    validate_monitor(cfg,monitors())
                    checked_monitor=time.monotonic()
                time.sleep(.3)
            if not stop and any(p.poll() not in [None,0] for p in children):
                raise RuntimeError('A child process exited; inspect '+str(logdir/'runtime.log'))
        finally:
            for p in reversed(children):
                if p.poll() is None:p.terminate()
            for p in children:
                try:p.wait(timeout=4)
                except subprocess.TimeoutExpired:p.kill();p.wait()
            (runtime/'processes.json').unlink(missing_ok=True)

if __name__=='__main__':
    try:main()
    except (RuntimeError,ValueError,OSError) as e:
        print('Conky Fedora Tree: '+str(e),file=sys.stderr)
        run(['notify-send','Conky 未启动',str(e)],timeout=3)
        sys.exit(1)
