#!/usr/bin/env python3
"""Interactive leaf-by-leaf configuration. No secrets are embedded."""
import json, os
from pathlib import Path
base=Path(__file__).resolve().parents[1]
p=base/'config/lab.json'
c=json.loads((p if p.exists() else base/'config/lab.example.json').read_text())
def edit(value, path=''):
    if isinstance(value, dict):
        return {k:edit(v, f'{path}.{k}'.strip('.')) for k,v in value.items()}
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return [edit(v,f'{path}[{i}]') for i,v in enumerate(value)]
    answer=input(f'{path} [{json.dumps(value)}]: ').strip()
    if not answer: return value
    if isinstance(value,str): return answer
    return json.loads(answer)
print('Enter keeps a value. Booleans: true/false. Lists: JSON arrays. Ctrl+C cancels.')
c=edit(c)
with open(p,'w',opener=lambda path,flags:os.open(path,flags,0o600)) as f:
    json.dump(c,f,indent=2); f.write('\n')
print(f'Saved {p}. Run ./run.sh preflight')
