"""Dedicated raw data disks and HPP. Existing foreign disks are never formatted."""
import json, os, re, shlex, shutil, time
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml

DEFAULTS=dict(enabled=True,disk_gib=80,target='vdb',mount_path='/var/hpvolumes',
              pool_name='vm-storage',storage_class='hostpath-csi',reclaim_policy='Retain',
              default=True,adopt_existing_disks=False,minimum_host_free_gib=100,
              timeout_seconds=3600,smoke_test=True)

def settings(lab):
    c={**DEFAULTS,**lab.c.get('storage',{})}
    assert c['target']=='vdb','This version supports dedicated vdb data disks only'
    assert c['mount_path']=='/var/hpvolumes','This version supports /var/hpvolumes only'
    assert isinstance(c['disk_gib'],int) and c['disk_gib']>=10
    assert c['reclaim_policy'] in ['Retain','Delete']
    for k in ['pool_name','storage_class']: assert re.fullmatch(r'[a-z0-9][a-z0-9-]*',c[k])
    return c

def attachments(xml):
    result={}
    for disk in ET.fromstring(xml).findall('./devices/disk'):
        target=disk.find('target'); source=disk.find('source')
        if target is not None and source is not None:
            result[target.get('dev')]=source.get('file',source.get('dev'))
    return result

def disk_xml(path):
    root=ET.Element('disk',type='file',device='disk')
    ET.SubElement(root,'driver',name='qemu',type='raw',cache='none',io='native')
    ET.SubElement(root,'source',file=str(path))
    ET.SubElement(root,'target',dev='vdb',bus='virtio')
    return ET.tostring(root,encoding='unicode')

def guest_script(size,allow_format):
    return f'''set -euo pipefail
expected={size}
allow_format={1 if allow_format else 0}
device=/dev/vdb
path=/var/hpvolumes
unit=/etc/systemd/system/var-hpvolumes.mount
test -b "$device"
test "$(blockdev --getsize64 "$device")" = "$expected"
test "$(lsblk -nr -o NAME "$device" | wc -l)" -eq 1
fstype=$(blkid -s TYPE -o value "$device" || true)
if [ -z "$fstype" ]; then
  test "$allow_format" = 1 || {{ echo 'STOP: adopted disk has no filesystem'; exit 1; }}
  test -z "$(wipefs --noheadings --output TYPE "$device")"
  test -z "$(lsblk -nr -o MOUNTPOINTS "$device" | tr -d '[:space:]')"
  mkfs.xfs "$device"
else
  test "$fstype" = xfs || {{ echo 'STOP: expected XFS'; exit 1; }}
fi
uuid=$(blkid -s UUID -o value "$device")
test -n "$uuid"
if mountpoint -q "$path"; then
  test "$(findmnt -n -o UUID --target "$path")" = "$uuid"
else
  test -z "$(lsblk -nr -o MOUNTPOINTS "$device" | tr -d '[:space:]')"
  mkdir -p "$path"
  test -z "$(ls -A "$path")"
fi
tmp=$(mktemp)
cat > "$tmp" <<EOF
[Unit]
Description=Local storage for OpenShift Virtualization
Before=kubelet.service
[Mount]
What=/dev/disk/by-uuid/$uuid
Where=/var/hpvolumes
Type=xfs
Options=defaults
[Install]
WantedBy=multi-user.target
EOF
# Adoption requires the mounted filesystem already proven above; never formats it.
install -m 0644 "$tmp" "$unit"
rm -f "$tmp"
systemctl daemon-reload
systemctl enable --now var-hpvolumes.mount
findmnt /var/hpvolumes
df -h /var/hpvolumes
'''

def provision(lab):
    from lab import write, run
    c=settings(lab)
    if not c['enabled']: print('Storage disabled'); return
    diskdir=Path(lab.c['disk_dir']); size=c['disk_gib']*1024**3
    # Budget all not-yet-created raw files, plus a configurable host reserve.
    missing=sum(not (diskdir/(n['name']+'-data.raw')).exists() for n in lab.c['nodes'])
    assert shutil.disk_usage(diskdir).free >= missing*size+c['minimum_host_free_gib']*1024**3, 'Insufficient host storage budget for data disks plus reserve'
    for n in lab.c['nodes']:
        print('STORAGE node '+n['name'],flush=True)
        assert lab.vir('domstate',n['name']).strip()=='running'
        disk=diskdir/(n['name']+'-data.raw'); marker=lab.state/('data-disk-'+n['name'])
        for flag in [[],['--inactive']]:
            attached=attachments(lab.vir('dumpxml',n['name'],*flag))
            assert 'vdb' not in attached or attached['vdb']==str(disk),'vdb points at a different disk'
        if not disk.exists():
            assert not marker.exists(),'Owned disk missing; refusing recreation'
            write(marker,json.dumps({'path':str(disk),'size':size,'format_allowed':True}))
            run(['qemu-img','create','-f','raw',disk,str(c['disk_gib'])+'G'])
            run(['chown',__import__('host').profile()['qemu_owner'],disk]); os.chmod(disk,0o600)
        elif not marker.exists():
            assert c['adopt_existing_disks'],'Existing data disk: set storage.adopt_existing_disks=true after verifying its identity'
            assert disk.stat().st_size==size,'Unexpected data disk size'
            # Require both attachment and an existing mounted XFS filesystem before adoption.
            assert attachments(lab.vir('dumpxml',n['name'])).get('vdb')==str(disk)
            lab.ssh(n,'sudo bash -ec '+shlex.quote('test "$(findmnt -n -o SOURCE --mountpoint /var/hpvolumes)" = /dev/vdb; test "$(findmnt -n -o FSTYPE --mountpoint /var/hpvolumes)" = xfs'))
            write(marker,json.dumps({'path':str(disk),'size':size,'format_allowed':False}))
        identity=json.loads(marker.read_text())
        assert identity['path']==str(disk) and identity['size']==size and disk.stat().st_size==size
        xml=lab.w/(n['name']+'-data.xml'); write(xml,disk_xml(disk))
        for mode,flags in [('config',['--inactive']),('live',[])]:
            if attachments(lab.vir('dumpxml',n['name'],*flags)).get('vdb') is None:
                lab.vir('attach-device',n['name'],xml,'--'+mode)
        deadline=time.time()+300
        while lab.ssh(n,'test -b /dev/vdb',check=False).returncode:
            assert time.time()<deadline,'vdb did not appear'; time.sleep(3)
        print(lab.ssh(n,'sudo bash -s',input=guest_script(size,identity['format_allowed']),timeout=c['timeout_seconds']))
        # After successful format/mount, later runs must never format this disk again.
        identity['format_allowed']=False; write(marker,json.dumps(identity))
    hpp={'apiVersion':'hostpathprovisioner.kubevirt.io/v1beta1','kind':'HostPathProvisioner','metadata':{'name':'hostpath-provisioner'},'spec':{'imagePullPolicy':'IfNotPresent','storagePools':[{'name':c['pool_name'],'path':c['mount_path']}],'workload':{'nodeSelector':{'node-role.kubernetes.io/worker':''}}}}
    annotations={'storageclass.kubernetes.io/is-default-class':'true','storageclass.kubevirt.io/is-default-virt-class':'true'} if c['default'] else {}
    sc={'apiVersion':'storage.k8s.io/v1','kind':'StorageClass','metadata':{'name':c['storage_class'],'annotations':annotations},'provisioner':'kubevirt.io.hostpath-provisioner','reclaimPolicy':c['reclaim_policy'],'volumeBindingMode':'WaitForFirstConsumer','parameters':{'storagePool':c['pool_name']}}
    existing=json.loads(lab.ocmd('get','storageclass','-o','json'))['items']
    for x in existing:
        if x['metadata']['name']!=c['storage_class'] and c['default']:
            assert not any(x['metadata'].get('annotations',{}).get(k)=='true' for k in annotations),'Another default StorageClass exists'
    old=lab.ocmd('get','hostpathprovisioner','hostpath-provisioner','--ignore-not-found','-o','json')
    if old: assert json.loads(old)['spec']['storagePools']==hpp['spec']['storagePools'],'Existing HPP pool differs; refusing overwrite'
    path=lab.w/'storage/hostpath.yaml'; write(path,yaml.safe_dump_all([hpp,sc],sort_keys=False))
    lab.ocmd('apply','--dry-run=server','-f',path); lab.ocmd('apply','-f',path)
    def ready():
        ds=json.loads(lab.ocmd('-n',lab.c['virtualization']['namespace'],'get','daemonset','hostpath-provisioner-csi','-o','json'))['status']
        return ds.get('desiredNumberScheduled')==len(lab.c['nodes']) and ds.get('numberReady')==len(lab.c['nodes'])
    lab.wait_for('Hostpath CSI rollout',ready,c['timeout_seconds'],lab.c['virtualization']['namespace'])
    lab.wait_for('storage validation',lambda:verify(lab) is None,c['timeout_seconds'],lab.c['virtualization']['namespace'])
    if c['smoke_test']: smoke(lab,c)
    lab.mark('storage')

def verify(lab):
    c=settings(lab)
    if not c['enabled']: return
    for n in lab.c['nodes']:
        out=lab.ssh(n,'findmnt -n -o SOURCE,FSTYPE --mountpoint /var/hpvolumes')
        assert out.split()==['/dev/vdb','xfs'],'Storage mount is missing or wrong on '+n['name']
    ds=json.loads(lab.ocmd('-n',lab.c['virtualization']['namespace'],'get','daemonset','hostpath-provisioner-csi','-o','json'))['status']
    assert ds.get('desiredNumberScheduled')==3 and ds.get('numberReady')==3,'HPP not Ready on all three nodes'
    sc=json.loads(lab.ocmd('get','storageclass',c['storage_class'],'-o','json'))
    assert sc['provisioner']=='kubevirt.io.hostpath-provisioner'
    print('Storage mounts and HPP verified on all three nodes',flush=True)

def smoke(lab,c):
    from lab import write
    ns='ocplab-storage-test'
    image=lab.ocmd('-n',lab.c['virtualization']['namespace'],'get','deployment','hco-operator','-o','jsonpath={.spec.template.spec.containers[0].image}')
    pvc={'apiVersion':'v1','kind':'PersistentVolumeClaim','metadata':{'name':'storage-check','namespace':ns},'spec':{'storageClassName':c['storage_class'],'accessModes':['ReadWriteOnce'],'volumeMode':'Filesystem','resources':{'requests':{'storage':'1Gi'}}}}
    pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':'storage-check','namespace':ns},'spec':{'restartPolicy':'Never','containers':[{'name':'check','image':image,'command':['/bin/sh','-ec'],'args':['printf "ocplab-storage-ok\\n" > /data/check.txt; sync; cat /data/check.txt; df -h /data'],'securityContext':{'allowPrivilegeEscalation':False,'capabilities':{'drop':['ALL']},'seccompProfile':{'type':'RuntimeDefault'}},'volumeMounts':[{'name':'data','mountPath':'/data'}]}],'volumes':[{'name':'data','persistentVolumeClaim':{'claimName':'storage-check'}}]}}
    path=lab.w/'storage/smoke.yaml'; write(path,yaml.safe_dump_all([{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}},pvc,pod]))
    lab.ocmd('apply','-f',path)
    def ready():
        phase=lab.ocmd('-n',ns,'get','pod','storage-check','-o','jsonpath={.status.phase}')
        print('Storage smoke pod: '+phase,flush=True)
        if phase=='Failed':
            lab.progress(ns)
            raise AssertionError('Storage smoke pod failed; inspect logs/events; resources retained')
        return phase=='Succeeded'
    lab.wait_for('storage smoke test',ready,c['timeout_seconds'],ns)
    output=lab.ocmd('-n',ns,'logs','storage-check'); print(output)
    assert 'ocplab-storage-ok' in output
