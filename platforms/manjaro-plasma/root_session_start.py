#!/usr/bin/env python3
"""Replacement for the pre-existing root Conky entry, explicitly authorized."""
import hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path


def legacy_instances(procroot,uid,config):
    result=[]
    for p in Path(procroot).iterdir():
        if not p.name.isdigit():continue
        try:
            if p.stat().st_uid!=uid:continue
            args=[x.decode(errors='replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
            if not args or Path(args[0]).name!='conky':continue
            paths=[]
            for i,value in enumerate(args[1:],1):
                if value in ['-c','--config'] and i+1<len(args):paths.append(args[i+1])
                elif value.startswith('--config='):paths.append(value.split('=',1)[1])
            if str(config) in paths:result.append(int(p.name))
        except OSError:continue
    return result


def main():
    os.umask(0o077);base=Path(__file__).resolve().parent
    font_dir=Path.home()/'.local/share/fonts/conky-noto-cjk';font=font_dir/'NotoSansCJK-Bold.ttc'
    state=Path.home()/'.local/state/conky-classic-tree';state.mkdir(parents=True,exist_ok=True)
    stamp=state/'font-cache-ready.json';digest=hashlib.sha256(font.read_bytes()).hexdigest()
    try:ready=json.loads(stamp.read_text()).get('sha256')==digest
    except (OSError,ValueError):ready=False
    if not ready:
        subprocess.run(['fc-cache','-f',str(font_dir)],check=True,timeout=30,stdout=subprocess.DEVNULL)
        family=subprocess.check_output(['fc-match','-f','%{family}','Noto Sans CJK SC:bold'],text=True,timeout=5)
        if 'Noto Sans CJK SC' not in family:raise RuntimeError('Noto CJK SC font did not resolve')
        stamp.write_text(json.dumps({'sha256':digest})+'\n')
    time.sleep(30)
    # KDE may restore the exact legacy Conky command from its old session.
    # Retire only that configured instance, never another monitor/app/profile.
    for pid in legacy_instances('/proc',os.getuid(),Path.home()/'.config/conky/manjaro_conkyrc'):
        handle=None
        try:
            handle=os.pidfd_open(pid)
            if pid in legacy_instances('/proc',os.getuid(),Path.home()/'.config/conky/manjaro_conkyrc'):
                signal.pidfd_send_signal(handle,signal.SIGTERM)
        except ProcessLookupError:pass
        finally:
            if handle is not None:os.close(handle)
    os.execv(sys.executable,[sys.executable,str(base/'top_start.py'),'--delay','0','--xwayland-backend'])


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        print('Conky replacement start failed: '+str(error),file=sys.stderr)
        try:subprocess.run(['notify-send','Conky未启动',str(error)],check=False,timeout=3)
        except (OSError,subprocess.SubprocessError):pass
        sys.exit(1)
