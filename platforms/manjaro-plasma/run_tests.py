#!/usr/bin/env python3
"""Build the profile in a temporary directory and run base + Plasma tests."""
from pathlib import Path
import tempfile,shutil,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_profile import adapted_launcher
profile=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='conky-plasma-tests-') as tmp:
    target=Path(tmp)/'source'
    shutil.copytree(profile.parents[1]/'portable',target,ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['plasma_compat.py','session_start.py']:
        shutil.copy2(profile/name,target/name)
    shutil.copy2(profile/'test_plasma.py',target/'tests/test_plasma.py')
    p=target/'start.py';p.write_text(adapted_launcher(p.read_text()))
    sys.exit(subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-q'],cwd=target).returncode)
