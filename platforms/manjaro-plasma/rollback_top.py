#!/usr/bin/python3
"""Restore only this transaction's previous Manjaro Conky source directory."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import stat


def tree_manifest(base):
    base=Path(base)
    return {str(p.relative_to(base)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                'mode':stat.S_IMODE(p.stat().st_mode)}
            for p in sorted(base.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}


def rollback(here):
    here=Path(here).resolve()
    if os.geteuid()!=0:raise RuntimeError('Run as root/administrator')
    root=here.parents[4]
    if 'ID=manjaro' not in (root/'etc/os-release').read_text():
        raise RuntimeError('Not the reviewed Manjaro filesystem')
    record=json.loads((here/'result.json').read_text())
    dest=root/'root/.config/conky/classic-tree';previous=here/'previous-classic-tree'
    if dest.is_symlink() or previous.is_symlink():raise RuntimeError('Refusing symlinked source directory')
    if tree_manifest(dest)!=record['installed_manifest']:
        raise RuntimeError('Installed files changed since sync; compare before rollback')
    if tree_manifest(previous)!=record['previous_manifest']:
        raise RuntimeError('Previous-source checksum mismatch')
    staging=dest.with_name('classic-tree.rollback-'+here.name)
    quarantine=here/'rolled-back-top-tree'
    if staging.exists() or quarantine.exists():raise RuntimeError('Rollback output already exists')
    shutil.copytree(previous,staging)
    if tree_manifest(staging)!=record['previous_manifest']:
        shutil.rmtree(staging);raise RuntimeError('Restored-source verification failed')
    dest.rename(quarantine)
    try:staging.rename(dest)
    except BaseException:
        quarantine.rename(dest);raise
    print('Previous Conky source restored. Original autostart, fonts and other desktop settings unchanged. Re-login manually.')


if __name__=='__main__':rollback(Path(__file__).resolve().parent)
