"""Modules implemented by this installer; OLM catalog discovery is separate."""
import json
MODULES = {
    'core': {'description': 'Three-node compact OpenShift cluster (required)', 'requires': []},
    'virtualization': {'description': 'OpenShift Virtualization operator and HyperConverged', 'requires': ['core']},
    'storage': {'description': 'Dedicated disks and Hostpath CSI', 'requires': ['virtualization']},
}
def selected(c):
    value=c.get('modules',{}).get('selected')
    if value is None:
        value=['core']
        if c.get('virtualization',{}).get('enabled'): value.append('virtualization')
        if c.get('storage',{}).get('enabled'): value.append('storage')
    assert isinstance(value,list) and all(isinstance(x,str) for x in value), 'modules.selected must be a list'
    assert len(value)==len(set(value)) and set(value)<=set(MODULES), 'Unknown or duplicate module'
    assert 'core' in value, 'core is required'
    for name in value:
        assert set(MODULES[name]['requires'])<=set(value), name+' has missing dependencies'
    return value
def normalize(c):
    chosen=selected(c)
    c['virtualization']['enabled']='virtualization' in chosen
    c.setdefault('storage',{})['enabled']='storage' in chosen
    return c
def listing(c=None):
    chosen=selected(c) if c else []
    return [{'name':k, **v, 'selected':k in chosen} for k,v in MODULES.items()]
if __name__=='__main__':
    print(json.dumps(listing(),indent=2))
