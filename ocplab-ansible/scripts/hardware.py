#!/usr/bin/env python3
"""Read-only hardware assessment; uses only Python's standard library."""
import argparse, json, os, platform, re, shutil
from pathlib import Path

def distro(path='/etc/os-release'):
    values={}
    for line in Path(path).read_text().splitlines():
        if '=' in line and not line.startswith('#'):
            k,v=line.split('=',1); values[k]=v.strip('"\'')
    ident=values.get('ID','')
    family='debian' if ident in ('debian','ubuntu') else 'redhat' if ident in ('rhel','fedora','centos','rocky','almalinux') else None
    return {'id':ident,'version':values.get('VERSION_ID',''), 'family':family,'name':values.get('PRETTY_NAME',ident)}

def recommend(ram_mib,cpus,free_gib,kvm=True):
    # Never pretend that fewer/smaller masters implement this UPI topology.
    reserve=4096; minimum=4*16384+reserve
    fit=ram_mib>=minimum and free_gib>=660 and cpus>=8 and kvm
    node_ram=16384 if ram_mib<102400 else 24576 if ram_mib<135168 else 32768
    return {'topology':'three compact control-plane/worker nodes + temporary bootstrap',
      'fits_without_memory_overcommit':ram_mib>=minimum,
      'recommended_for_this_automation':fit,
      'minimum_peak_ram_mib':minimum,'host_reserve_mib':reserve,
      'bootstrap':{'memory_mib':16384,'vcpus':4,'disk_gib':100},
      'per_node':{'memory_mib':node_ram,'vcpus':4 if cpus<24 else 8,'disk_gib':120},
      'per_node_data_disk_gib':80,
      'disk_budget_gib':800,
      'notes':['Peak RAM includes bootstrap. Four 16 GiB VMs plus host need 68 GiB.',
               '8 logical CPUs imply CPU overcommit; 16+ is preferable.',
               'Disk budget: 460 GiB OS + 240 GiB data + 100 GiB reserve; mirrors require additional space.',
               'Below minimum: use a larger host or a separate single-node installation workflow; this installer never silently shrinks masters.']}
def assess(path='/var/lib/libvirt/images'):
    p=Path(path).resolve()
    while not p.exists(): p=p.parent
    mem=Path('/proc/meminfo').read_text()
    ram=int(re.search(r'MemTotal:\s+(\d+)',mem)[1])//1024
    available=int(re.search(r'MemAvailable:\s+(\d+)',mem)[1])//1024
    nested={}
    for name in ('kvm_intel','kvm_amd'):
        f=Path('/sys/module')/name/'parameters/nested'
        if f.exists(): nested[name]=f.read_text().strip()
    free=shutil.disk_usage(p).free//1024**3
    cpu=Path('/proc/cpuinfo').read_text()
    r={'os':distro(),'architecture':platform.machine(),'logical_cpus':os.cpu_count() or 1,
       'ram_mib':ram,'available_ram_mib':available,'disk_path':str(p),'free_disk_gib':free,
       'kvm_device':Path('/dev/kvm').exists(),'cpu_virtualization_flag':bool(re.search(r'\b(vmx|svm)\b',cpu)),
       'nested_kvm':nested}
    r['suggestion']=recommend(ram,r['logical_cpus'],free,r['kvm_device'])
    r['suggestion']['recommended_for_this_automation'] &= free>=r['suggestion']['disk_budget_gib'] and r['architecture']=='x86_64' and bool(r['os']['family'])
    return r
def main():
    p=argparse.ArgumentParser(); p.add_argument('--disk-path',default='/var/lib/libvirt/images')
    a=p.parse_args(); print(json.dumps(assess(a.disk_path),indent=2))
if __name__=='__main__': main()
