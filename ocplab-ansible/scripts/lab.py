#!/usr/bin/env python3
"""Staged host-side operations, invoked by Ansible. No secret values in command arguments."""
import argparse, base64, hashlib, ipaddress, json, os, re, shlex, shutil
import subprocess, sys, tarfile, time, uuid, threading
from pathlib import Path
import xml.etree.ElementTree as ET
import yaml
from modules import normalize, listing
import host
import exposure


def run(args, *, check=True, capture=True, timeout=180, input=None):
    print(f"[{time.strftime('%H:%M:%S')}] RUN {Path(str(args[0])).name} (arguments/content withheld)", flush=True)
    p = subprocess.run([str(x) for x in args], text=True, input=input,
                       stdout=subprocess.PIPE if capture else None,
                       stderr=subprocess.PIPE if capture else None, timeout=timeout)
    print(f"[{time.strftime('%H:%M:%S')}] EXIT {Path(str(args[0])).name}: {p.returncode}", flush=True)
    if check and p.returncode:
        # Do not echo command payloads, since stdin/configs can contain secrets.
        raise RuntimeError(f'{args[0]} failed (exit {p.returncode}): {(p.stderr or "")[-1800:]}')
    return (p.stdout or '').strip() if check else p


def write(path, value, mode=0o600):
    """Atomic writes outside watched manifest paths; fsync before rename."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = value.encode() if isinstance(value, str) else value
    tmp = path.with_name('.' + path.name + '.tmp')
    with open(tmp, 'wb') as f:
        os.fchmod(f.fileno(), mode); f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def sha(path):
    h = hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text())


def valid_config(c):
    exposure.settings(c)
    for key,default in [('poll_seconds',30),('diagnostic_seconds',120),('api_seconds',900)]:
        value=c.get('waits',{}).get(key,default)
        assert isinstance(value,int) and 1<=value<=86400, 'Invalid waits.'+key
    from modules import selected
    selected(c)
    assert len(c['nodes']) == 3, 'Exactly three control-plane/worker nodes required'
    assert re.fullmatch(r'4\.\d+\.\d+', c['release']), 'Pin an exact release'
    for x in [c['cluster_name'], c['base_domain'], c['registry']['hostname'], c['network']['name']]:
        assert re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9.-]*',x), f'Unsafe name {x}'
    uuid.UUID(c['network']['uuid'])
    nets=[ipaddress.ip_network(c['network']['cidr']),ipaddress.ip_network(c['cluster_cidr']),ipaddress.ip_network(c['service_cidr'])]
    assert all(not a.overlaps(b) for i,a in enumerate(nets) for b in nets[i+1:]), 'CIDRs overlap'
    ns=[c['bootstrap']]+c['nodes']
    for field in ['name','ip','mac']:
        assert len(set(x[field] for x in ns))==4, f'Duplicate {field}'
    for n in ns:
        assert re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9-]*',n['name'])
        assert ipaddress.ip_address(n['ip']) in nets[0]
        assert re.fullmatch(r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',n['mac'])
        assert n['memory_mib']>=16384 and n['vcpus']>=4 and n['disk_gib']>=100
    assert c['network']['gateway'] not in [n['ip'] for n in ns]
    for k in ['gateway','dhcp_start','dhcp_end']:
        assert ipaddress.ip_address(c['network'][k]) in nets[0]
    lo,hi=[int(ipaddress.ip_address(c['network'][k])) for k in ['dhcp_start','dhcp_end']]
    assert lo<=hi
    assert all(not lo<=int(ipaddress.ip_address(n['ip']))<=hi for n in ns)
    assert c['disk_format'] in ['raw','qcow2']
    assert not c.get('storage',{}).get('enabled',False) or c['virtualization']['enabled'], 'Storage stage requires virtualization.enabled=true'
    for k in ['work_dir','disk_dir','pull_secret_file','ssh_private_key']:
        assert Path(c[k]).is_absolute() and not re.search(r'\s',c[k]), f'{k}: absolute path without spaces required'
    assert c['work_dir'] not in ['/','/root','/etc','/var']
    assert c['disk_dir'] not in ['/','/var','/var/lib/libvirt/images']


class Lab:
    def __init__(self,c):
        c=normalize(json.loads(json.dumps(c)))
        valid_config(c); self.c=c; self.w=Path(c['work_dir']); self.net=c['network']
        self.gw=self.net['gateway']; self.reg=f"{c['registry']['hostname']}:{c['registry']['port']}"
        self.domain=f"{c['cluster_name']}.{c['base_domain']}"
        self.nodes=[c['bootstrap']]+c['nodes']; self.ins=self.w/'install'
        self.oc='/usr/local/sbin/oc'; self.inst='/usr/local/sbin/openshift-install'
        self.secret=self.w/'secrets/pull-secret.json'; self.key=Path(c['ssh_private_key'])
        self.state=self.w/'state'; self.state.mkdir(parents=True,exist_ok=True); os.chmod(self.w,0o700)
    def mark(self,name): write(self.state/name,time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()))
    def require(self,name): assert (self.state/name).exists(),f'Complete {name} phase first'
    def logrun(self,args,name,timeout):
        d=self.w/'logs'; d.mkdir(exist_ok=True)
        path=d/(name+'-'+str(time.time_ns())+'.log')
        print(f'SUBTASK {name}: {path}', flush=True)
        with open(path,'w') as f:
            os.chmod(path,0o600)
            proc=subprocess.Popen([str(x) for x in args],stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT,text=True,bufsize=1)
            def drain():
                for line in proc.stdout:
                    # Install-complete can print kubeadmin credentials.
                    if re.search(r'password|--password|token=',line,re.I):
                        line='[credential-bearing output omitted]\n'
                    f.write(line); f.flush(); print(line,end='',flush=True)
            reader=threading.Thread(target=drain,daemon=True); reader.start()
            try: code=proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.terminate()
                try: proc.wait(timeout=10)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
                reader.join(); proc.stdout.close(); raise
            reader.join(); proc.stdout.close()
        if code: raise RuntimeError(f'Stage failed; inspect {path}. No resources were deleted.')
        print(f'SUBTASK {name} completed',flush=True)
    def vir(self,*args,**kw): return run(['virsh','--connect','qemu:///system',*args],**kw)
    def exists(self,name): return self.vir('dominfo',name,check=False).returncode==0
    def ocmd(self,*args,**kw):
        return run([self.oc,'--kubeconfig='+str(self.ins/'auth/kubeconfig'),'--request-timeout=30s',*args],**kw)
    def ssh(self,n,cmd,**kw):
        return run(['ssh','-i',self.key,'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
          '-o','StrictHostKeyChecking=accept-new','-o','UserKnownHostsFile='+str(self.w/'known_hosts'),
          '-o','ConnectTimeout=5','core@'+n['ip'],cmd],**kw)
    def download(self,url,path,digest=None):
        path=Path(path)
        if path.exists() and digest and sha(path)==digest:
            print(f'CACHE verified: {path}',flush=True); return
        tmp=path.with_suffix(path.suffix+'.part'); path.parent.mkdir(parents=True,exist_ok=True)
        print(f'Downloading {url} -> {path}',flush=True)
        self.logrun(['curl','-fL','--retry','5',url,'-o',tmp],'download',7200)
        if digest: assert sha(tmp)==digest,f'Checksum mismatch: {path}'
        os.replace(tmp,path); os.chmod(path,0o644)
    def preflight(self):
        assert os.geteuid()==0,'Run as root'
        print('Detected host: '+host.profile()['name'],flush=True)
        assert Path('/dev/kvm').exists(),'/dev/kvm missing'
        assert self.c['host_faults_remediated'], ('Set host_faults_remediated=true only after investigating the observed QEMU '
          'double-free crash and guest corruption; this automation cannot diagnose or repair the host hardware.')
        for n in self.nodes:
            if self.exists(n['name']):
                assert (self.state/('owned-'+n['name'])).exists(),f"Existing unmanaged VM {n['name']}; refusing takeover"
        for k in ['pull_secret_file']:
            assert Path(self.c[k]).is_file(),f'Missing {k}'
        assert json.loads(Path(self.c['pull_secret_file']).read_text()).get('auths'),'Invalid pull secret'
        total=int(re.search(r'MemTotal:\s+(\d+)',Path('/proc/meminfo').read_text())[1])//1024
        requested=sum(n['memory_mib'] for n in self.nodes)+4096
        assert total>=requested or self.c['allow_memory_overcommit'], 'Insufficient RAM; explicit lab overcommit required'
        assert shutil.disk_usage(self.w).free>50*1024**3,'Less than 50 GiB free'
        if Path('/sys/module/kvm_intel/parameters/nested').exists() and self.c['virtualization']['enabled']:
            assert Path('/sys/module/kvm_intel/parameters/nested').read_text().strip() in ['Y','1'],'Nested KVM disabled'
        for module in ['kvm_intel','kvm_amd']:
            nested=Path('/sys/module')/module/'parameters/nested'
            if nested.exists() and self.c['virtualization']['enabled']:
                assert nested.read_text().strip() in ['Y','1'], 'Nested KVM disabled'
        print(f'Preflight OK. Physical RAM {total} MiB; configured VM+host budget {requested} MiB.')
        self.mark('preflight')
    def network_xml(self):
        n=self.net; root=ET.Element('network',{'xmlns:dnsmasq':'http://libvirt.org/schemas/network/dnsmasq/1.0'})
        ET.SubElement(root,'name').text=n['name']; ET.SubElement(root,'uuid').text=n['uuid']
        if not n['isolate_guests']: ET.SubElement(root,'forward',{'mode':'nat'})
        ET.SubElement(root,'bridge',{'name':n['bridge'],'stp':'on','delay':'0'})
        dns=ET.SubElement(root,'dns')
        for ip in exposure.settings(self.c)['upstream_dns']: ET.SubElement(dns,'forwarder',{'addr':ip})
        host=ET.SubElement(dns,'host',{'ip':self.gw})
        for name in ['api.'+self.domain,'api-int.'+self.domain,self.c['registry']['hostname']]: ET.SubElement(host,'hostname').text=name
        for node in self.nodes:
            h=ET.SubElement(dns,'host',{'ip':node['ip']}); ET.SubElement(h,'hostname').text=node['name']+'.'+self.c['base_domain']
        net=ipaddress.ip_network(n['cidr']); ip=ET.SubElement(root,'ip',{'address':self.gw,'netmask':str(net.netmask)})
        dh=ET.SubElement(ip,'dhcp'); ET.SubElement(dh,'range',{'start':n['dhcp_start'],'end':n['dhcp_end']})
        for node in self.nodes: ET.SubElement(dh,'host',{'mac':node['mac'],'name':node['name'],'ip':node['ip']})
        opts=ET.SubElement(root,'dnsmasq:options')
        for v in [f'address=/apps.{self.domain}/{self.gw}',f'local=/apps.{self.domain}/']:
            ET.SubElement(opts,'dnsmasq:option',{'value':v})
        return ET.tostring(root,encoding='unicode')
    def haproxy(self,bootstrap=True):
        text='''global
    log /dev/log local0
    user haproxy
    group haproxy
    daemon
    maxconn 4096
defaults
    mode tcp
    log global
    option tcplog
    timeout connect 10s
    timeout client 4h
    timeout server 4h
    timeout check 5s
'''
        for name,port in [('api',6443),('mcs',22623),('http',80),('https',443)]:
            text+=f'frontend ocp_{name}\n    bind {self.gw}:{port}\n    default_backend ocp_{name}_nodes\nbackend ocp_{name}_nodes\n    balance roundrobin\n    option tcp-check\n'
            if port!=22623:
                binds=''.join(f'    bind {ip}:{port}\n' for ip in exposure.settings(self.c)['lan_ips'])
                text=text.replace(f'    bind {self.gw}:{port}\n',f'    bind {self.gw}:{port}\n'+binds)
            nodes=(self.nodes if bootstrap and port in [6443,22623] else self.c['nodes'])
            for n in nodes: text+=f"    server {n['name']} {n['ip']}:{port} check inter 5s fall 3 rise 2\n"
        text+=exposure.proxy_text(self)
        candidate=self.w/'haproxy.cfg'; write(candidate,text)
        run(['haproxy','-c','-f',candidate]); write('/etc/haproxy/haproxy.cfg',text,0o644)
        run(['systemctl','reload-or-restart','haproxy'])
    def prepare(self):
        self.preflight(); assert self.c['manage_host_services'],'manage_host_services must be true'
        host.libvirt_start(run)
        for s in ['nginx','haproxy']: run(['systemctl','enable',s])
        write(self.w/'qemu-emulator',host.emulator(run))
        # Never replace an existing unowned network or mutate live network leases.
        xml=self.network_xml(); netfile=self.w/'network.xml'
        old=self.vir('net-dumpxml',self.net['name'],check=False)
        if old.returncode==0:
            assert (self.state/'network').exists(),'Existing network is not owned by this project'
            assert netfile.read_text()==xml,'Network settings changed: migrate manually; no live recreation'
        else:
            write(netfile,xml); self.vir('net-define',netfile); self.mark('network')
        info=self.vir('net-info',self.net['name'])
        if not re.search(r'Active:\s+yes',info): self.vir('net-start',self.net['name'])
        self.vir('net-autostart',self.net['name'])
        backup=self.w/'backups'; backup.mkdir(exist_ok=True)
        for src in ['/etc/haproxy/haproxy.cfg','/etc/nginx/sites-enabled/default']:
            if Path(src).exists() and not (backup/Path(src).name).exists(): shutil.copy2(src,backup/Path(src).name)
        write(self.secret,Path(self.c['pull_secret_file']).read_bytes())
        self.key.parent.mkdir(parents=True,exist_ok=True)
        if not self.key.exists(): run(['ssh-keygen','-t','ed25519','-N','','-f',self.key])
        if not Path(str(self.key)+'.pub').exists(): write(str(self.key)+'.pub',run(['ssh-keygen','-y','-f',self.key])+'\n',0o644)
        os.chmod(self.key,0o600)
        # Expose only public installation assets, never the working directory.
        pub=self.w/'http'; pub.mkdir(exist_ok=True); pub.chmod(0o755)
        target=Path('/var/www/ocplab-auto'); target.mkdir(exist_ok=True)
        if run(['mountpoint','-q',target],check=False).returncode:
            run(['mount','--bind',pub,target]); run(['mount','-o','remount,bind,ro',target])
        entry=f'{pub} {target} none bind,ro 0 0'
        fstab=Path('/etc/fstab').read_text()
        if entry not in fstab: write('/etc/fstab',fstab+'\n'+entry+'\n',0o644)
        write('/etc/nginx/conf.d/ocplab-auto.conf',f'''server {{
 listen {self.gw}:{self.c['http_port']};
 root {target};
 autoindex off;
 allow {self.net['cidr']};
 deny all;
 location / {{ try_files $uri =404; }}
}}
''',0o644)
        Path('/etc/nginx/sites-enabled/default').unlink(missing_ok=True)
        Path('/etc/nginx/sites-enabled/ocplab-auto').unlink(missing_ok=True)
        host.nginx_default(self)
        host.selinux(self)
        write('/etc/systemd/system/nginx.service.d/ocplab-auto.conf',f'[Unit]\nAfter=network-online.target libvirtd.service virtnetworkd.service\nWants=network-online.target\nRequiresMountsFor={target}\n[Service]\nRestart=on-failure\nRestartSec=10\n',0o644)
        write('/etc/systemd/system/haproxy.service.d/ocplab-auto.conf','[Unit]\nAfter=network-online.target libvirtd.service virtnetworkd.service\nWants=network-online.target\n[Service]\nRestart=on-failure\nRestartSec=10\n',0o644)
        run(['systemctl','daemon-reload'])
        run(['nginx','-t']); run(['systemctl','restart','nginx'])
        host.chrony(self)
        hosts=Path('/etc/hosts').read_text()
        hosts=re.sub(r'\n# BEGIN OCPLAB AUTO.*?# END OCPLAB AUTO\n','\n',hosts,flags=re.S)
        records=[f'{self.gw} api.{self.domain} api-int.{self.domain} {self.c["registry"]["hostname"]}']
        records += [f'{n["ip"]} {n["name"]} {n["name"]}.{self.c["base_domain"]}' for n in self.nodes]
        write('/etc/hosts',hosts+'\n# BEGIN OCPLAB AUTO\n'+'\n'.join(records)+'\n# END OCPLAB AUTO\n',0o644)
        host.resolver(self)
        exposure.setup(self)
        self.haproxy(not (self.state/'bootstrap-complete').exists())
        self.registry(); self.tools(); self.mark('prepare')
    def registry(self):
        r=self.c['registry']; d=self.w/'registry'
        for sub in ['ca','certs','data']: (d/sub).mkdir(parents=True,exist_ok=True)
        if not (d/'ca/ca.crt').exists():
            run(['openssl','req','-x509','-newkey','rsa:4096','-nodes','-keyout',d/'ca/ca.key','-out',d/'ca/ca.crt','-days','3650','-subj','/CN=OCP Lab CA','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign'])
        if not (d/'certs/registry.crt').exists():
            run(['openssl','req','-new','-newkey','rsa:3072','-nodes','-keyout',d/'certs/registry.key','-out',d/'certs/registry.csr','-subj','/CN='+r['hostname']])
            write(d/'certs/extensions',f'basicConstraints=critical,CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\nsubjectAltName=DNS:{r["hostname"]},IP:{self.gw}\n')
            run(['openssl','x509','-req','-in',d/'certs/registry.csr','-CA',d/'ca/ca.crt','-CAkey',d/'ca/ca.key','-CAcreateserial','-out',d/'certs/registry.crt','-days','825','-extfile',d/'certs/extensions'])
        for f in [d/'ca/ca.key',d/'certs/registry.key']: f.chmod(0o600)
        write(host.profile()['ca_path'],(d/'ca/ca.crt').read_bytes(),0o644)
        write('/etc/containers/certs.d/'+self.reg+'/ca.crt',(d/'ca/ca.crt').read_bytes(),0o644)
        run([host.profile()['ca_command']])
        run(['podman','pull',r['image']],timeout=1800)
        image=run(['podman','image','inspect',r['image'],'--format','{{.Id}}'])
        write(self.w/'registry-image-id',image+'\n')
        unit=f'''[Unit]
Description=OCP lab TLS mirror (anonymous access)
After=network-online.target libvirtd.service
Wants=network-online.target libvirtd.service
StartLimitIntervalSec=0
[Service]
Restart=always
RestartSec=10
ExecStartPre=/usr/sbin/ip address show {self.net['bridge']}
ExecStart=/usr/bin/podman run --rm --name {r['container']} -p {self.gw}:{r['port']}:5000 -v {d}/data:/var/lib/registry:Z -v {d}/certs:/certs:ro,Z -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/registry.crt -e REGISTRY_HTTP_TLS_KEY=/certs/registry.key {image}
ExecStop=/usr/bin/podman stop -t 30 {r['container']}
TimeoutStartSec=120
TimeoutStopSec=60
[Install]
WantedBy=multi-user.target
'''
        # Existing foreign container is never deleted.
        if run(['podman','container','exists',r['container']],check=False).returncode==0:
            assert Path('/etc/systemd/system/'+r['unit']).exists(),'Registry container name already in use'
        write('/etc/systemd/system/'+r['unit'],unit,0o644)
        run(['systemctl','daemon-reload']); run(['systemctl','enable','--now',r['unit']])
        for _ in range(30):
            p=run(['curl','-fsS','--max-time','5','https://'+self.reg+'/v2/'],check=False)
            if p.returncode==0: break
            time.sleep(2)
        else: raise RuntimeError('TLS registry check failed')
    def tools(self):
        d=self.w/'downloads'; d.mkdir(exist_ok=True)
        url=self.c['tools_url']+'/'+self.c['release']; sums=d/'sha256sum.txt'
        self.download(url+'/sha256sum.txt',sums)
        hashes={line.split()[1].lstrip('*'):line.split()[0] for line in sums.read_text().splitlines() if len(line.split())==2}
        files={f'openshift-client-linux-{self.c["release"]}.tar.gz':['oc','kubectl'],f'openshift-install-linux-{self.c["release"]}.tar.gz':['openshift-install'],'oc-mirror.tar.gz':['oc-mirror']}
        for archive,bins in files.items():
            assert archive in hashes,'Archive missing from published checksum list'
            self.download(url+'/'+archive,d/archive,hashes[archive])
            with tarfile.open(d/archive) as t:
                for binary in bins:
                    members=[m for m in t.getmembers() if Path(m.name).name==binary and (m.isfile() or m.islnk() or m.issym())]
                    assert len(members)==1,f'Unexpected archive members for {binary}'
                    write('/usr/local/sbin/'+binary,t.extractfile(members[0]).read(),0o755)
        version=run([self.inst,'version']); assert self.c['release'] in version and self.c['release_digest'] in version,'Installer/release digest mismatch'
        print(version)
    def mirror(self):
        self.require('prepare'); v=self.c['virtualization']; minor='.'.join(self.c['release'].split('.')[:2])
        conf={'apiVersion':'mirror.openshift.io/v2alpha1','kind':'ImageSetConfiguration','mirror':{'platform':{'architectures':['amd64'],'channels':[{'name':'stable-'+minor,'minVersion':self.c['release'],'maxVersion':self.c['release']}],'graph':False}}}
        if v['enabled']: conf['mirror']['operators']=[{'catalog':v['catalog'],'packages':[{'name':v['package'],'channels':[{'name':v['channel'],'minVersion':v['version'],'maxVersion':v['version']}]}]}]
        d=self.w/'mirror'; d.mkdir(exist_ok=True); write(d/'imageset.yaml',yaml.safe_dump(conf))
        args=['/usr/local/sbin/oc-mirror','--v2','--config',d/'imageset.yaml','--authfile',self.secret,'--workspace','file://'+str(d/'workspace'),'--cache-dir',d/'cache','--parallel-images',self.c['mirror_parallel_images'],'--parallel-layers',self.c['mirror_parallel_layers'],'--retry-times',self.c['mirror_retries'],'--image-timeout',self.c['image_timeout'],'docker://'+self.reg]
        self.logrun(args,'mirror',self.c['timeouts']['mirror_seconds']); self.mark('mirror')
    def assets(self):
        self.require('prepare')
        meta=json.loads(run([self.inst,'coreos','print-stream-json']))
        write(self.w/'downloads/rhcos-stream.json',json.dumps(meta,indent=2))
        metal=meta['architectures']['x86_64']['artifacts']['metal']; d=self.w/'http/rhcos'; d.mkdir(parents=True,exist_ok=True); d.chmod(0o755)
        for kind,x in metal['formats']['pxe'].items(): self.download(x['location'],d/kind,x['sha256'])
        # Explicitly stage the raw install image + signature for fully local installs.
        x=metal['formats']['raw.gz']['disk']; self.download(x['location'],d/'metal.raw.gz',x['sha256'])
        # SHA-256 checked above. Lab PXE uses coreos.inst.insecure for absent signatures.
        self.mark('assets')
    def digest_mappings(self):
        path=self.w/'mirror/workspace/working-dir/cluster-resources/idms-oc-mirror.yaml'
        result=[]
        for obj in yaml.safe_load_all(path.read_text()):
            for entry in (obj or {}).get('spec',{}).get('imageDigestMirrors',[]):
                result.append({**entry,'sourcePolicy':'NeverContactSource'})
        assert any(e['source']=='quay.io/openshift-release-dev/ocp-release' for e in result)
        return result
    def ignition(self):
        self.require('mirror'); self.require('assets')
        if (self.state/'ignition').exists():
            assert time.time()-(self.state/'ignition').stat().st_mtime<12*3600,'Ignition is older than 12 hours. Use a new work directory for a new cluster.'
            print('Ignition already generated; preserving cluster identity.'); return
        assert not self.ins.exists(),'Install directory exists without completion marker. Preserve/diagnose it; do not regenerate blindly.'
        self.ins.mkdir(mode=0o700)
        c=self.c
        conf={'apiVersion':'v1','baseDomain':c['base_domain'],'metadata':{'name':c['cluster_name']},'platform':{'none':{}},
          'compute':[{'name':'worker','replicas':0,'architecture':'amd64','hyperthreading':'Enabled'}],
          'controlPlane':{'name':'master','replicas':3,'architecture':'amd64','hyperthreading':'Enabled'},
          'networking':{'networkType':'OVNKubernetes','machineNetwork':[{'cidr':self.net['cidr']}],'clusterNetwork':[{'cidr':c['cluster_cidr'],'hostPrefix':c['host_prefix']}],'serviceNetwork':[c['service_cidr']]},
          'pullSecret':self.secret.read_text(),'sshKey':Path(str(self.key)+'.pub').read_text().strip(),
          'additionalTrustBundle':(self.w/'registry/ca/ca.crt').read_text(),'imageDigestSources':self.digest_mappings()}
        text=yaml.safe_dump(conf,sort_keys=False); write(self.ins/'install-config.yaml',text); write(self.w/'backups/install-config.yaml',text)
        self.logrun([self.inst,'create','manifests','--dir',self.ins],'manifests',1800)
        scheduler=self.ins/'manifests/cluster-scheduler-02-config.yml'; s=load_yaml(scheduler); s['spec']['mastersSchedulable']=True; write(scheduler,yaml.safe_dump(s))
        chrony=f'server {self.gw} iburst\ndriftfile /var/lib/chrony/drift\nmakestep 1.0 3\nrtcsync\n'
        file={'path':'/etc/chrony.conf','mode':420,'overwrite':True,'contents':{'source':'data:text/plain;base64,'+base64.b64encode(chrony.encode()).decode()}}
        mc={'apiVersion':'machineconfiguration.openshift.io/v1','kind':'MachineConfig','metadata':{'name':'99-master-chrony','labels':{'machineconfiguration.openshift.io/role':'master'}},'spec':{'config':{'ignition':{'version':'3.2.0'},'storage':{'files':[file]}}}}
        write(self.ins/'openshift/99-master-chrony.yaml',yaml.safe_dump(mc))
        # Disable upstream Operator catalogs at installation time.
        write(self.ins/'manifests/cluster-marketplace-config.yaml',yaml.safe_dump({'apiVersion':'config.openshift.io/v1','kind':'OperatorHub','metadata':{'name':'cluster'},'spec':{'disableAllDefaultSources':True}}))
        self.logrun([self.inst,'create','ignition-configs','--dir',self.ins],'ignition',1800)
        b=json.loads((self.ins/'bootstrap.ign').read_text()); fs=b.setdefault('storage',{}).setdefault('files',[])
        fs[:]=[x for x in fs if x.get('path')!='/etc/chrony.conf']; fs.append(file)
        write(self.ins/'bootstrap.ign',json.dumps(b))
        for name in ['bootstrap','master']:
            data=(self.ins/(name+'.ign')).read_bytes(); obj=json.loads(data); assert obj.get('ignition')
            write(self.w/'http/ignition'/f'{name}.ign',data,0o644)
        (self.w/'http/ignition').chmod(0o755); self.mark('ignition')
    def domain_xml(self,n,install=False):
        d=ET.Element('domain',{'type':'kvm'}); ET.SubElement(d,'name').text=n['name']
        ET.SubElement(d,'memory',{'unit':'MiB'}).text=str(n['memory_mib'])
        ET.SubElement(d,'vcpu').text=str(n['vcpus'])
        osel=ET.SubElement(d,'os'); ET.SubElement(osel,'type',{'arch':'x86_64','machine':self.c['machine']}).text='hvm'
        if install:
            ET.SubElement(osel,'kernel').text=str(Path(self.c['disk_dir'])/'boot/kernel')
            ET.SubElement(osel,'initrd').text=str(Path(self.c['disk_dir'])/'boot/initramfs')
            url=f'http://{self.gw}:{self.c["http_port"]}'
            role='bootstrap' if n['name']==self.c['bootstrap']['name'] else 'master'
            ET.SubElement(osel,'cmdline').text=(f'console=tty0 console=ttyS0,115200n8 rd.neednet=1 ip=dhcp '
              f'coreos.live.rootfs_url={url}/rhcos/rootfs coreos.inst.install_dev=/dev/vda '
              f'coreos.inst.image_url={url}/rhcos/metal.raw.gz '
              f'coreos.inst.ignition_url={url}/ignition/{role}.ign coreos.inst.insecure '
              'coreos.inst.console=ttyS0,115200n8')
        else: ET.SubElement(osel,'boot',{'dev':'hd'})
        features=ET.SubElement(d,'features'); ET.SubElement(features,'acpi'); ET.SubElement(features,'apic')
        ET.SubElement(d,'cpu',{'mode':'host-passthrough','check':'none'})
        ET.SubElement(d,'clock',{'offset':'utc'})
        ET.SubElement(d,'on_poweroff').text='destroy'
        ET.SubElement(d,'on_reboot').text='destroy' if install else 'restart'
        ET.SubElement(d,'on_crash').text='preserve'
        dev=ET.SubElement(d,'devices'); ET.SubElement(dev,'emulator').text=(self.w/'qemu-emulator').read_text().strip() if (self.w/'qemu-emulator').exists() else '/usr/bin/qemu-system-x86_64'
        disk=ET.SubElement(dev,'disk',{'type':'file','device':'disk'})
        ET.SubElement(disk,'driver',{'name':'qemu','type':self.c['disk_format'],'cache':'none','io':'native'})
        ET.SubElement(disk,'source',{'file':str(self.disk(n))}); ET.SubElement(disk,'target',{'dev':'vda','bus':'virtio'})
        iface=ET.SubElement(dev,'interface',{'type':'network'}); ET.SubElement(iface,'mac',{'address':n['mac']})
        ET.SubElement(iface,'source',{'network':self.net['name']}); ET.SubElement(iface,'model',{'type':'virtio'})
        serial=ET.SubElement(dev,'serial',{'type':'pty'}); ET.SubElement(serial,'target',{'port':'0'})
        console=ET.SubElement(dev,'console',{'type':'pty'}); ET.SubElement(console,'target',{'type':'serial','port':'0'})
        ET.SubElement(dev,'memballoon',{'model':'virtio'})
        return ET.tostring(d,encoding='unicode')
    def disk(self,n): return Path(self.c['disk_dir'])/(n['name']+'.'+self.c['disk_format'])
    def crash_guard(self):
        for n in self.nodes:
            path=Path('/var/log/libvirt/qemu')/(n['name']+'.log')
            if path.exists():
                assert not re.search(r'double free or corruption|reason=crashed|Repairing cluster',path.read_text(errors='replace')),f'QEMU fault in {path}; preserve evidence and repair host before continuing'
    def vms(self):
        self.require('ignition'); self.preflight(); self.crash_guard()
        assert time.time()-(self.state/'ignition').stat().st_mtime<12*3600,'Ignition expired for new nodes'
        boot=Path(self.c['disk_dir'])/'boot'; boot.mkdir(parents=True,exist_ok=True)
        Path(self.c['disk_dir']).chmod(0o755); boot.chmod(0o755)
        for kind in ['kernel','initramfs']: write(boot/kind,(self.w/'http/rhcos'/kind).read_bytes(),0o644)
        for n in self.nodes:
            owned=self.state/('owned-'+n['name']); installed=self.state/('installed-'+n['name'])
            disk=self.disk(n); self.crash_guard()
            if not owned.exists():
                assert not self.exists(n['name']) and not disk.exists(),f'Existing VM or disk {n["name"]}; no overwrite allowed'
                run(['qemu-img','create','-f',self.c['disk_format'],disk,str(n['disk_gib'])+'G'])
                run(['chown',host.profile()['qemu_owner'],disk]); os.chmod(disk,0o600)
                xml=self.w/(n['name']+'-install.xml'); write(xml,self.domain_xml(n,True))
                self.vir('define',xml); self.mark('owned-'+n['name']); self.vir('start',n['name'])
            if not installed.exists():
                # Restart a never-started installation only; never rerun installer on an existing disk automatically.
                deadline=time.time()+self.c['timeouts']['vm_install_seconds']
                while time.time()<deadline:
                    state=self.vir('domstate',n['name']).strip(); self.crash_guard()
                    if state=='shut off': break
                    time.sleep(10)
                else: raise RuntimeError('Installation did not reach shutdown: '+n['name'])
                # Inspect the installed disk offline, read-only; a crash must never count as install completion.
                self.inspect_installed_disk(n)
                domain=ET.fromstring(self.domain_xml(n,False))
                ET.SubElement(domain,'uuid').text=self.vir('domuuid',n['name']).strip()
                xml=self.w/(n['name']+'-disk.xml'); write(xml,ET.tostring(domain,encoding='unicode'))
                self.vir('define',xml); self.mark('installed-'+n['name'])
            state=self.vir('domstate',n['name'])
            if state=='shut off': self.vir('start',n['name'])
            else: assert state=='running',f'Unexpected domain state: {state}'
            if n!=self.c['bootstrap']: self.vir('autostart',n['name'])
            deadline=time.time()+600
            while time.time()<deadline:
                if self.ssh(n,'test -e /etc/os-release',check=False,timeout=15).returncode==0: break
                time.sleep(10)
            else: raise RuntimeError('Installed node SSH unavailable: '+n['name'])
            print('Disk boot and SSH verified: '+n['name'])
        self.mark('vms')
    def inspect_installed_disk(self,n):
        # virt-filesystems uses libguestfs without mounting/modifying guest filesystems.
        result=run(['virt-filesystems','--format='+self.c['disk_format'],'-a',self.disk(n),'--filesystems','--long'],timeout=600)
        assert 'xfs' in result,'Expected RHCOS filesystem missing; inspect console before recovery'
        # guestfish read-only mounted root resolves physical root path; partition 4 is the RHCOS root.
        # No format assumptions beyond standard RHCOS partition/filesystem check here.
        # Installed Ignition is checked using /boot/ignition/config.ign on boot partition.
        ignition=run(['guestfish','--ro','--format='+self.c['disk_format'],'-a',self.disk(n),'-m','/dev/sda3','cat','/ignition/config.ign'],timeout=600)
        assert json.loads(ignition).get('ignition'),'Installed Ignition missing'
        role='bootstrap' if n==self.c['bootstrap'] else 'master'
        assert json.loads(ignition)==json.loads((self.ins/(role+'.ign')).read_text()),'Installed Ignition differs from source'
    def progress(self,namespace=None):
        checks=[('operators',('get','co')),('nodes',('get','nodes'))]
        if namespace:
            checks=[('pods',('-n',namespace,'get','pods','-o','wide')),
                    ('events',('-n',namespace,'get','events','--field-selector=type=Warning','--sort-by=.lastTimestamp'))]
        for title,args in checks:
            try:
                p=self.ocmd(*args,check=False,timeout=45)
                print(title+':\n'+(p.stdout or p.stderr or '')[-6000:],flush=True)
            except subprocess.TimeoutExpired:
                print(title+': API query timed out; continuing wait',flush=True)
    def wait_for(self,description,check,timeout,namespace=None):
        deadline=time.monotonic()+timeout
        interval=self.c.get('waits',{}).get('poll_seconds',30)
        diagnostic=self.c.get('waits',{}).get('diagnostic_seconds',120)
        next_diagnostic=0; last='not ready'
        while time.monotonic()<deadline:
            try:
                if check():
                    print(description+': ready',flush=True); return
            except (RuntimeError,subprocess.TimeoutExpired,ConnectionError) as exc:
                last=str(exc)[-800:]
            if time.monotonic()>=next_diagnostic:
                print(f'WAIT {description}; remaining {int(deadline-time.monotonic())}s; {last}',flush=True)
                self.progress(namespace); next_diagnostic=time.monotonic()+diagnostic
            time.sleep(min(interval,max(0,deadline-time.monotonic())))
        self.progress(namespace)
        raise RuntimeError(description+' timed out; last error: '+last+'; resources retained, rerun the same phase')
    def installer_wait(self,event,timeout):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                self.logrun([self.inst,'wait-for',event,'--dir',self.ins,'--log-level=info'],event,max(1,int(deadline-time.monotonic())))
                return
            except (RuntimeError,subprocess.TimeoutExpired):
                self.crash_guard(); self.progress()
                if time.monotonic()>=deadline: raise
                print('Installer wait ended; retrying within configured overall deadline',flush=True)
                time.sleep(min(30,max(0,deadline-time.monotonic())))
        raise RuntimeError(event+' deadline exceeded')
    def complete(self):
        self.require('vms'); self.crash_guard()
        if not (self.state/'bootstrap-complete').exists():
            self.installer_wait('bootstrap-complete',self.c['timeouts']['bootstrap_seconds'])
            self.mark('bootstrap-complete')
        self.haproxy(False)
        self.wait_for('permanent API',lambda:self.ocmd('get','--raw=/readyz').strip()=='ok',
                      self.c.get('waits',{}).get('api_seconds',900))
        if self.vir('domstate',self.c['bootstrap']['name'])=='running':
            self.vir('shutdown',self.c['bootstrap']['name'])
        if self.c['image_registry_emptydir']:
            def registry_ready():
                self.ocmd('patch','configs.imageregistry.operator.openshift.io','cluster','--type=merge','-p',json.dumps({'spec':{'managementState':'Managed','replicas':1,'storage':{'emptyDir':{}}}}))
                return True
            self.wait_for('image registry configuration',registry_ready,900)
        self.installer_wait('install-complete',self.c['timeouts']['cluster_seconds'])
        self.mark('complete')
    def expose(self):
        self.require('complete')
        exposure.publish(self)
    def modules(self):
        print(json.dumps(listing(self.c),indent=2))
        if self.c.get('modules',{}).get('list_catalog_packages',False):
            print(self.ocmd('get','packagemanifests','-A','-o','custom-columns=NAME:.metadata.name,CATALOG:.status.catalogSource,CHANNEL:.status.defaultChannel'))
    def fix_catalog(self,cat):
        image=cat['spec']['image']
        if image.endswith('-permissions-fixed'):
            print('Catalog already references permissions-fixed image',flush=True)
            return cat
        assert re.fullmatch(r'[A-Za-z0-9._:/@-]+',image),'Unsafe catalog reference'
        self.logrun(['podman','pull',image],'catalog-pull',1800)
        image_id=run(['podman','image','inspect',image,'--format','{{.Id}}'])
        source=image.split('@')[0]
        target=source+'-permissions-fixed' if ':' in source.rsplit('/',1)[-1] else source+':permissions-fixed'
        d=self.w/'catalog-permissions-fix'; d.mkdir(exist_ok=True)
        write(d/'Containerfile',f'FROM {image_id}\nUSER 0\nRUN chmod -R a+rX /configs\nUSER 1001\n')
        self.logrun(['podman','build','--pull=never','-t',target,d],'catalog-build',1800)
        run(['podman','run','--rm','--entrypoint','/bin/sh',target,'-ec','id; test -r /configs; test -x /configs; ls /configs >/dev/null'])
        self.logrun(['podman','push',target],'catalog-push',1800)
        cat['spec']['image']=target
        return cat
    def storage(self):
        if not self.c.get('storage',{}).get('enabled',True):
            print('Storage disabled'); return
        self.require('virtualization')
        from storage import provision
        provision(self)
    def virtualization(self):
        self.require('complete'); v=self.c['virtualization']
        if not v['enabled']: return
        # KVM must actually be exposed in every guest, not merely enabled on the host.
        for n in self.c['nodes']: self.ssh(n,'test -c /dev/kvm')
        resources=self.w/'mirror/workspace/working-dir/cluster-resources'
        for file in ['idms-oc-mirror.yaml','itms-oc-mirror.yaml']:
            if (resources/file).exists(): self.ocmd('apply','-f',resources/file)
        catalogs=list(resources.glob('cs-*.yaml')); assert len(catalogs)==1,'Expected one filtered CatalogSource'
        cat=load_yaml(catalogs[0])
        if v.get('fix_catalog_permissions',True):
            cat=self.fix_catalog(cat)
            write(catalogs[0],yaml.safe_dump(cat,sort_keys=False))
        self.ocmd('apply','-f',catalogs[0])
        self.ocmd('patch','operatorhub.config.openshift.io','cluster','--type=merge','-p','{"spec":{"disableAllDefaultSources":true}}')
        name=cat['metadata']['name']; ns=v['namespace']
        docs=[{'apiVersion':'v1','kind':'Namespace','metadata':{'name':ns}},
          {'apiVersion':'operators.coreos.com/v1','kind':'OperatorGroup','metadata':{'name':'cnv','namespace':ns},'spec':{'targetNamespaces':[ns]}},
          {'apiVersion':'operators.coreos.com/v1alpha1','kind':'Subscription','metadata':{'name':v['package'],'namespace':ns},'spec':{'channel':v['channel'],'name':v['package'],'source':name,'sourceNamespace':cat['metadata']['namespace'],'installPlanApproval':'Manual'}}]
        path=self.w/'virtualization.yaml'; write(path,yaml.safe_dump_all(docs)); self.ocmd('apply','-f',path)
        deadline=time.time()+self.c['timeouts']['operator_seconds']; csv=None
        while time.time()<deadline:
            sub=json.loads(self.ocmd('-n',ns,'get','subscription',v['package'],'-o','json'))
            print('Subscription conditions: '+json.dumps(sub.get('status',{}).get('conditions',[])),flush=True)
            plan=sub.get('status',{}).get('installPlanRef',{}).get('name')
            if plan:
                ip=json.loads(self.ocmd('-n',ns,'get','installplan',plan,'-o','json'))
                csvs=ip['spec']['clusterServiceVersionNames']; expected='kubevirt-hyperconverged-operator.v'+v['version']
                assert expected in csvs and len(csvs)==1,'Unexpected InstallPlan; review dependencies/version manually'
                self.ocmd('-n',ns,'patch','installplan',plan,'--type=merge','-p','{"spec":{"approved":true}}')
                csv=sub.get('status',{}).get('installedCSV')
                if csv:
                    phase=self.ocmd('-n',ns,'get','csv',csv,'-o','jsonpath={.status.phase}')
                    print(f'CSV {csv}: {phase}',flush=True)
                    if phase=='Succeeded': break
            time.sleep(15)
        else: raise RuntimeError('Virtualization CSV timeout; inspect Subscription/InstallPlan')
        hco={'apiVersion':'hco.kubevirt.io/v1beta1','kind':'HyperConverged','metadata':{'name':v['hco_name'],'namespace':ns},'spec':{}}
        path=self.w/'hyperconverged.yaml'; write(path,yaml.safe_dump(hco)); self.ocmd('apply','-f',path)
        run([self.oc,'--kubeconfig='+str(self.ins/'auth/kubeconfig'),'-n',ns,'wait','hyperconverged/'+v['hco_name'],'--for=condition=Available','--timeout='+str(self.c['timeouts']['operator_seconds'])+'s'],timeout=self.c['timeouts']['operator_seconds']+60)
        self.mark('virtualization')
    def validate(self):
        self.require('complete'); self.crash_guard()
        nodes=json.loads(self.ocmd('get','nodes','-o','json'))['items']
        for n in self.c['nodes']:
            obj=next(x for x in nodes if x['metadata']['name']==n['name'])
            assert any(x['type']=='Ready' and x['status']=='True' for x in obj['status']['conditions']),n['name']+' not Ready'
            assert 'node-role.kubernetes.io/worker' in obj['metadata']['labels']
        cos=json.loads(self.ocmd('get','co','-o','json'))['items']; bad=[]
        for co in cos:
            cond={x['type']:x['status'] for x in co['status']['conditions']}
            if cond.get('Available')!='True' or cond.get('Degraded')=='True' or cond.get('Progressing')=='True': bad.append(co['metadata']['name'])
        assert not bad,'Operators not settled: '+','.join(bad)
        for n in self.c['nodes']:
            for filename in ['kube-apiserver-pod.yaml','etcd-pod.yaml']:
                text=self.ssh(n,'sudo cat /etc/kubernetes/manifests/'+filename)
                obj=yaml.safe_load(text)
                assert isinstance(obj,dict) and obj.get('kind')=='Pod',f'Malformed manifest on {n["name"]}'
            self.ssh(n,'chronyc tracking')
        if self.c['virtualization']['enabled']:
            self.require('virtualization')
            v=self.c['virtualization']
            h=json.loads(self.ocmd('-n',v['namespace'],'get','hyperconverged',v['hco_name'],'-o','json'))
            conditions={x['type']:x['status'] for x in h.get('status',{}).get('conditions',[])}
            assert conditions.get('Available')=='True' and conditions.get('Degraded')!='True','HyperConverged is not healthy'
        if self.c.get('storage',{}).get('enabled',False):
            from storage import verify
            verify(self)
        report={'time':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'release':self.c['release'],'nodes':[n['name'] for n in self.c['nodes']], 'isolation_configured':self.net['isolate_guests'],'virtualization_installed':self.c['virtualization']['enabled'],'storage_configured':(self.state/'storage').exists(),'storage_note':'Hostpath volumes are node-local; requested sizes are not enforced quotas.'}
        write(self.w/'validation.json',json.dumps(report,indent=2)); print(json.dumps(report,indent=2))
        self.mark('validate')
    def diagnostics(self):
        d=self.w/'diagnostics'/str(int(time.time())); d.mkdir(parents=True)
        for name,args in [('memory',['free','-h']),('domains',['virsh','list','--all']),('kernel',['journalctl','-k','-b','--no-pager']),('iostat',['iostat','-xz','1','3'])]:
            p=run(args,check=False); write(d/(name+'.txt'),p.stdout+p.stderr)
        for n in self.nodes:
            path=Path('/var/log/libvirt/qemu')/(n['name']+'.log')
            if path.exists(): shutil.copy2(path,d/path.name)
        print('Evidence saved to '+str(d)+'. No repair or deletion performed.')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',required=True)
    parser.add_argument('phase',choices=['preflight','prepare','mirror','assets','ignition','vms','complete','virtualization','storage','expose','modules','validate','diagnostics'])
    args=parser.parse_args(); os.umask(0o077)
    c=json.loads(Path(args.config).read_text()); lab=Lab(c)
    # Prevent simultaneous runs modifying cluster state.
    import fcntl
    with open(lab.w/'automation.lock','w') as f:
        try: fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Another stage is still running. Check pgrep -af lab.py and lslocks. Ctrl+C on Ansible does not stop an async job. Never delete automation.lock.')
        logs=lab.w/'logs'; logs.mkdir(exist_ok=True)
        logpath=logs/(args.phase+'-'+str(time.time_ns())+'.log')
        logfile=open(logpath,'a',buffering=1); os.chmod(logpath,0o600)
        write(logs/'active-stage.path',str(logpath)+'\n')
        class Tee:
            def __init__(self,original): self.original=original
            def write(self,data): self.original.write(data); logfile.write(data); return len(data)
            def flush(self): self.original.flush(); logfile.flush()
        sys.stdout=Tee(sys.stdout); sys.stderr=Tee(sys.stderr)
        print(f'STAGE START {args.phase}; PID {os.getpid()}; log {logpath}',flush=True)
        # Prerequisites must pass BEFORE establishing the immutable config lock.
        try:
            if args.phase=='prepare': lab.preflight()
            lock=lab.state/'config.sha256'
            fingerprint=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest()
            if args.phase not in ['preflight','diagnostics','modules']:
                if lock.exists():
                    if lock.read_text().strip()!=fingerprint:
                        # Recover only the exact historical consent-only lock failure.
                        previous=dict(c); previous['host_faults_remediated']=False
                        old=hashlib.sha256(json.dumps(previous,sort_keys=True).encode()).hexdigest()
                        markers={p.name for p in lab.state.iterdir()}-{'preflight','config.sha256'}
                        assert args.phase=='prepare' and not markers and c['host_faults_remediated'] and lock.read_text().strip()==old, 'Configuration changed. Do not reset the lock. See README upgrade procedure.'
                        write(lock,fingerprint+'\n')
                else: write(lock,fingerprint+'\n')
            getattr(lab,args.phase)()
            print(f'STAGE SUCCESS {args.phase}',flush=True)
        except Exception as exc:
            print(f'STAGE FAILED {args.phase}: {exc}',flush=True); raise

if __name__=='__main__':
    try: main()
    except Exception as exc:
        print('STOP: '+str(exc),file=sys.stderr); sys.exit(1)
