import unittest,tempfile,os,sys,json,tarfile,hashlib,contextlib,io
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from root_session_start import legacy_instances

class RootReplacementTest(unittest.TestCase):
    def test_only_exact_old_configuration_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            commands={1:['/usr/bin/conky','-c','/root/.config/conky/manjaro_conkyrc'],2:['/usr/bin/conky','--config=/root/.config/conky/manjaro_conkyrc'],3:['/usr/bin/conky','-c','/run/user/0/conky-classic-tree/conky.conf'],4:['/usr/bin/conky','-c','/root/other.conf'],5:['/usr/bin/python3','x.py','-c','/root/.config/conky/manjaro_conkyrc']}
            for pid,args in commands.items():
                p=base/str(pid);p.mkdir();(p/'cmdline').write_bytes(b'\0'.join(a.encode() for a in args)+b'\0')
            self.assertEqual(set(legacy_instances(base,os.getuid(),'/root/.config/conky/manjaro_conkyrc')),{1,2})
            self.assertEqual(legacy_instances(base,os.getuid()+1,'/root/.config/conky/manjaro_conkyrc'),[])

class RootRollbackTest(unittest.TestCase):
    def test_rollback_locates_only_its_target_root_and_restores_exact_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'target';(target/'etc').mkdir(parents=True);(target/'etc/os-release').write_text('ID=manjaro\n')
            here=target/'root/.local/state/conky-root-replacement/test';here.mkdir(parents=True)
            code=(Path(__file__).resolve().parents[1]/'rollback_root.py').read_text()
            script=here/'rollback.py';script.write_text(code)
            records={}
            paths=['root/.config/conky/manjaro_conkyrc','root/.config/conky/start_conky.sh','root/.config/autostart/start_conky.sh.desktop']
            with tarfile.open(here/'before-root-and-mjr.tar.gz','w:gz') as tf:
                for i,rel in enumerate(paths):
                    p=target/rel;p.parent.mkdir(parents=True,exist_ok=True);data=('original-'+str(i)).encode();p.write_bytes(data);tf.add(p,arcname=rel)
                    records[rel]={'sha256':hashlib.sha256(data).hexdigest(),'mode':0o600,'uid':os.getuid(),'gid':os.getgid()}
                    p.write_bytes(b'new version')
            (here/'legacy-files.json').write_text(json.dumps(records))
            with patch('os.geteuid',return_value=0),contextlib.redirect_stdout(io.StringIO()):
                exec(compile(code,str(script),'exec'),{'__file__':str(script),'__name__':'__main__'})
            for rel,meta in records.items():self.assertEqual(hashlib.sha256((target/rel).read_bytes()).hexdigest(),meta['sha256'])

if __name__=='__main__':unittest.main()
