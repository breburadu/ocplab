#!/usr/bin/env python3
"""Explicit, locked migration from v1: add new options without changing cluster identity."""
import argparse, fcntl, hashlib, json, os, shutil, time
from pathlib import Path
from storage import DEFAULTS
from lab import write
p=argparse.ArgumentParser()
p.add_argument('config',nargs='?',default='config/lab.json')
p.add_argument('--adopt-storage',action='store_true',help='Validate/reuse the already attached and mounted XFS vdb disks')
p.add_argument('--settings',help='JSON object: modules, exposure, waits, timeouts only; identities and network stay unchanged')
a=p.parse_args(); os.umask(0o077)
path=Path(a.config).resolve(); old=json.loads(path.read_text()); work=Path(old['work_dir'])
assert work.is_dir(),'Existing installation work directory not found'
with open(work/'automation.lock','a') as handle:
    try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: raise SystemExit('A stage is active. Wait for it to finish; config unchanged.')
    lock=work/'state/config.sha256'
    def digest(c): return hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
    assert lock.exists() and lock.read_text().strip()==digest(old),'Config does not match existing lock. No migration performed.'
    new=json.loads(json.dumps(old))
    new['virtualization'].setdefault('fix_catalog_permissions',True)
    new.setdefault('storage',dict(DEFAULTS))
    if a.adopt_storage: new['storage']['adopt_existing_disks']=True
    if a.settings:
        changes=json.loads(Path(a.settings).read_text())
        assert isinstance(changes,dict) and set(changes)<=set(['modules','exposure','waits','timeouts']), 'Only operational settings can be migrated'
        for key,value in changes.items():
            assert isinstance(value,dict), key+' must be an object'
            new[key]={**new.get(key,{}),**value}
        from modules import normalize
        normalize(new)
        from lab import valid_config
        valid_config(new)
    from storage import settings
    class Config: c=new
    settings(Config())
    backup=work/'backups'/('automation-upgrade-'+str(time.time_ns())); backup.mkdir(parents=True)
    shutil.copy2(path,backup/'lab.json'); shutil.copy2(lock,backup/'config.sha256')
    # Both originals are saved; interruption between writes fails closed on next invocation.
    write(path,json.dumps(new,indent=2)+'\n'); write(lock,digest(new)+'\n')
    print('Added options and requested operational settings. Existing network, identity, release, paths and resources preserved.')
    print('Backup: '+str(backup))
    print('Run only the relevant stage (expose, storage, etc.) then validate; do not rerun the full installation.')
