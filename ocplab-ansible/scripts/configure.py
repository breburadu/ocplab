#!/usr/bin/env python3
"""Interactive configuration with read-only assessment and explicit module choice."""
import argparse, json, os
from pathlib import Path
from hardware import assess
from modules import listing, selected, normalize
base=Path(__file__).resolve().parents[1]
def edit(value,path=''):
    if isinstance(value,dict): return {k:edit(v,f'{path}.{k}'.strip('.')) for k,v in value.items()}
    if isinstance(value,list) and value and isinstance(value[0],dict):
        return [edit(v,f'{path}[{i}]') for i,v in enumerate(value)]
    answer=input(f'{path} [{json.dumps(value)}]: ').strip()
    if not answer: return value
    return answer if isinstance(value,str) else json.loads(answer)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',default=str(base/'config/lab.json'))
    parser.add_argument('--list-modules',action='store_true'); a=parser.parse_args()
    if a.list_modules: print(json.dumps(listing(),indent=2)); return
    p=Path(a.config); c=json.loads((p if p.exists() else base/'config/lab.example.json').read_text())
    if (Path(c['work_dir'])/'state/config.sha256').exists():
        raise SystemExit('Existing installation: use upgrade_config.py and its --settings file; setup will not rewrite locked configuration.')
    if input('Assess local hardware first? [Y/n]: ').strip().lower()!='n':
        report=assess(c['disk_dir']); print(json.dumps(report,indent=2))
        if input('Apply suggested CPU/RAM/disk sizes? [y/N]: ').strip().lower()=='y':
            for node in c['nodes']: node.update(report['suggestion']['per_node'])
            c['bootstrap'].update(report['suggestion']['bootstrap'])
            c['storage']['disk_gib']=report['suggestion']['per_node_data_disk_gib']
            # Never enable overcommit implicitly, even when the recommendation cannot fit.
            c['allow_memory_overcommit']=False
    print(json.dumps(listing(c),indent=2))
    choice=input('Modules, comma separated ['+','.join(selected(c))+']: ').strip()
    c.setdefault('modules',{})['selected']=[s.strip() for s in choice.split(',')] if choice else selected(c)
    normalize(c)
    print('Edit configuration: Enter keeps values; true/false booleans; JSON lists. Ctrl+C cancels.')
    c=edit(c)
    normalize(c)
    from lab import valid_config, write
    valid_config(c)
    write(p,json.dumps(c,indent=2)+'\n')
    print(f'Saved {p}. Run ./run.sh preflight {p}')
if __name__=='__main__': main()
