#!/usr/bin/env python3
"""Cache the bundled user font once, then exec the normal 30-second launcher."""
import hashlib,json,os,subprocess,sys
from pathlib import Path


def main():
    os.umask(0o077)
    base=Path(__file__).resolve().parent
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
    os.execv(sys.executable,[sys.executable,str(base/'start.py')])


if __name__=='__main__':
    try:main()
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:
        message='Conky字体/启动检查失败：'+str(error)
        print(message,file=sys.stderr)
        try:subprocess.run(['notify-send','Conky未启动',message],timeout=3,check=False)
        except (OSError,subprocess.SubprocessError):pass
        sys.exit(1)
