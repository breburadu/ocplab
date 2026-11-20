#!/usr/bin/env python3
"""Follow the currently active engine and Ansible logs across stage transitions."""
import json, sys, time
from pathlib import Path
root=Path(json.loads(Path(sys.argv[1]).read_text())['work_dir'])/'logs'
positions={}; handles={}
print('Following current Ansible task and engine/subtask output. Ctrl+C stops this viewer only.',flush=True)
try:
    while True:
        for name in ['active-ansible.path','active-stage.path']:
            pointer=root/name
            value=pointer.read_text().strip() if pointer.exists() else ''
            if not value: continue
            path=Path(value)
            if not path.exists(): continue
            if handles.get(name)!=value:
                handles[name]=value; print(f'\n===== {name}: {path} =====',flush=True)
            with path.open(errors='replace') as f:
                f.seek(positions.get(value,0)); data=f.read(); positions[value]=f.tell()
            if data: print(data,end='',flush=True)
        time.sleep(1)
except KeyboardInterrupt:
    print('\nLog viewer stopped; installer continues in its own Screen window.')
