#!/usr/bin/env python3
"""Explicit user-only installation, with a non-clobbering autostart rollback."""
import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from datetime import datetime
from conky_tree import DEFAULTS


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['install','uninstall'])
    p.add_argument('--monitor-index',type=int,default=0)
    p.add_argument('--connector',default='eDP-1')
    a=p.parse_args();os.umask(0o077)
    home=Path.home();source=Path(__file__).resolve().parent
    dest=home/'.config/conky/classic-tree';state=home/'.local/state/conky-classic-tree'
    auto=home/'.config/autostart/conky-classic-tree.desktop';manifest_path=state/'install.json'
    if a.action=='uninstall':
        manifest=json.loads(manifest_path.read_text())
        if auto.exists() and digest(auto)!=manifest['autostart_sha256']:
            raise RuntimeError('Autostart was edited after installation; compare it with the manifest before rollback')
        for record in manifest['replaced_autostart']:
            old=Path(record['original']);backup=Path(record['backup'])
            if digest(backup)!=record['sha256']:
                raise RuntimeError('Autostart backup checksum mismatch')
            if old.exists() and digest(old)!=record['sha256']:
                raise RuntimeError('A later autostart exists at '+str(old)+'; refusing to overwrite it')
        for record in manifest['replaced_autostart']:
            shutil.copy2(record['backup'],record['original'])
        auto.unlink(missing_ok=True)
        print('Original autostart restored. Source and logs retained. Stop this launcher before changing a running session.')
        return
    cfg=DEFAULTS.copy();cfg.update(monitor_index=a.monitor_index,expected_connector=a.connector)
    from start import monitors,validate_monitor
    validate_monitor(cfg,monitors())
    if dest.exists() or auto.exists() or manifest_path.exists():
        raise RuntimeError('An installation already exists; retain and compare it before installing again')
    state.mkdir(parents=True,exist_ok=True)
    archive=state/('autostart-before-'+datetime.now().strftime('%Y%m%d-%H%M%S'));archive.mkdir()
    auto.parent.mkdir(parents=True,exist_ok=True)
    replaced=[]
    for old in auto.parent.glob('*.desktop'):
        text=old.read_text(errors='replace')
        if any(line.startswith('Exec=') and 'conky' in line.lower() for line in text.splitlines()):
            backup=archive/old.name;shutil.copy2(old,backup)
            replaced.append({'original':str(old),'backup':str(backup),'sha256':digest(backup)})
    text=None
    try:
        shutil.copytree(source,dest,ignore=shutil.ignore_patterns('__pycache__','tests','config.local.json'))
        (dest/'config.local.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n')
        def quote(value):
            value=str(value).replace('%','%%')
            for char in ['\\','"','`','$']:
                value=value.replace(char,'\\'+char)
            return '"'+value+'"'
        command=' '.join(quote(x) for x in [sys.executable,dest/'start.py'])
        text='[Desktop Entry]\nType=Application\nName=Conky Classic Tree\nComment=Original tree layout, unprivileged telemetry\nExec='+command+'\nTerminal=false\nX-GNOME-Autostart-enabled=true\n'
        auto.write_text(text)
        for record in replaced:
            if digest(record['original'])!=record['sha256']:
                raise RuntimeError('Conky autostart changed during installation')
        manifest={'destination':str(dest),'autostart':str(auto),'autostart_sha256':digest(auto),'replaced_autostart':replaced}
        manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        for record in replaced:Path(record['original']).unlink()
    except Exception:
        for record in replaced:
            old=Path(record['original'])
            if not old.exists():shutil.copy2(record['backup'],old)
        if auto.exists() and text is not None and auto.read_text()==text:auto.unlink()
        if dest.exists():shutil.rmtree(dest)
        manifest_path.unlink(missing_ok=True)
        raise
    print('Installed:',dest)
    print('Doctor:',sys.executable,str(dest/'start.py'),'--doctor')
    print('No running Conky has been stopped or replaced by this install command.')


if __name__=='__main__':main()
