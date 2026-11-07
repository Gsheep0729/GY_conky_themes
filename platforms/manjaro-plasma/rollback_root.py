#!/usr/bin/python3
from pathlib import Path
import os,sys,json,tarfile,hashlib
here=Path(__file__).resolve().parent
root=here.parents[4]
if os.geteuid()!=0:raise SystemExit('Run as administrator/root')
if 'ID=manjaro' not in (root/'etc/os-release').read_text():raise SystemExit('Not the reviewed Manjaro filesystem')
records=json.loads((here/'legacy-files.json').read_text())
with tarfile.open(here/'before-root-and-mjr.tar.gz') as tf:
    for rel,meta in records.items():
        member=tf.getmember(rel);data=tf.extractfile(member).read()
        if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise SystemExit('Backup checksum mismatch')
        p=root/rel;temp=p.with_name(p.name+'.conky-rollback.tmp');temp.write_bytes(data);os.chmod(temp,meta['mode']);os.chown(temp,meta['uid'],meta['gid']);temp.replace(p)
for rel,meta in records.items():
    if hashlib.sha256((root/rel).read_bytes()).hexdigest()!=meta['sha256']:raise SystemExit('Restore verification failed')
print('Original root Conky configuration, startup script and original autostart restored. Re-login to use it. New source/fonts/logs retained; mistaken mjr deployment remains retired.')
