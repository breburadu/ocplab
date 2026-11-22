"""Distribution adapters. No global firewall flush or SELinux disable."""
import json, os, re, shutil, socket
from pathlib import Path
from hardware import distro

def profile():
    d=distro()
    assert d['family'], 'Supported hosts: Debian, Ubuntu, RHEL, Fedora (and RHEL derivatives)'
    assert os.uname().machine=='x86_64', 'The release artifacts currently target x86_64'
    deb=d['family']=='debian'
    return dict(**d,qemu_owner='libvirt-qemu:kvm' if deb else 'qemu:qemu',
        chrony_service='chrony' if deb else 'chronyd',
        chrony_conf='/etc/chrony/chrony.conf' if deb else '/etc/chrony.conf',
        ca_path='/usr/local/share/ca-certificates/ocplab-auto.crt' if deb else '/etc/pki/ca-trust/source/anchors/ocplab-auto.crt',
        ca_command='update-ca-certificates' if deb else 'update-ca-trust')

def libvirt_start(run):
    if run(['systemctl','is-active','libvirtd.service'],check=False).returncode==0:
        run(['systemctl','enable','libvirtd.service']); return
    modular=run(['systemctl','show','virtqemud.socket','-p','LoadState','--value'],check=False).stdout.strip()=='loaded'
    units=['virtqemud.socket','virtnetworkd.socket','virtstoraged.socket','virtnodedevd.socket','virtnwfilterd.socket','virtsecretd.socket','virtinterfaced.socket','virtproxyd.socket'] if modular else ['libvirtd.service']
    for unit in units:
        if run(['systemctl','show',unit,'-p','LoadState','--value'],check=False).stdout.strip()=='loaded':
            run(['systemctl','enable','--now',unit])
    if modular:
        for unit in ['virtnetworkd.service','virtqemud.service']:
            run(['systemctl','enable','--now',unit])
    run(['virsh','--connect','qemu:///system','list'])

def emulator(run):
    import xml.etree.ElementTree as ET
    root=ET.fromstring(run(['virsh','--connect','qemu:///system','capabilities']))
    for guest in root.findall('guest'):
        arch=guest.find('arch')
        if arch is not None and arch.get('name')=='x86_64' and arch.find("domain[@type='kvm']") is not None:
            domain=arch.find("domain[@type='kvm']")
            value=domain.findtext('emulator') or arch.findtext('emulator')
            if value: return value
    raise RuntimeError('No x86_64 KVM emulator in libvirt capabilities')

def chrony(lab):
    from lab import write, run
    p=Path(profile()['chrony_conf']); old=p.read_text()
    block='\n# BEGIN OCPLAB AUTO\nallow '+lab.net['cidr']+'\n'+''.join('pool '+x+' iburst\n' for x in lab.c['ntp_upstreams'])+'# END OCPLAB AUTO\n'
    old=re.sub(r'\n# BEGIN OCPLAB AUTO.*?# END OCPLAB AUTO\n','\n',old,flags=re.S)
    write(p,old+block,0o644)
    run(['systemctl','enable','--now',profile()['chrony_service']])
    run(['systemctl','restart',profile()['chrony_service']])

def selinux(lab):
    from lab import run
    if not shutil.which('getenforce') or run(['getenforce'])=='Disabled': return
    # Targeted persistent labels for boot assets. Libvirt labels VM disks itself.
    expression=str(lab.w/'http')+'(/.*)?'
    result=run(['semanage','fcontext','-a','-t','httpd_sys_content_t',expression],check=False)
    if result.returncode: run(['semanage','fcontext','-m','-t','httpd_sys_content_t',expression])
    run(['restorecon','-RF',lab.w/'http'])
    run(['setsebool','-P','haproxy_connect_any','on'])
    port=lab.c['http_port']
    labels=run(['semanage','port','-l'])
    matches=[]
    for line in labels.splitlines():
        fields=line.split()
        if len(fields)<3 or fields[1]!='tcp': continue
        for span in ''.join(fields[2:]).split(','):
            nums=span.split('-')
            if all(n.isdigit() for n in nums) and int(nums[0])<=port<=int(nums[-1]):
                matches.append(fields[0])
    specific=[m for m in matches if m not in ('port_t','reserved_port_t','unreserved_port_t')]
    if not any(m in ('http_port_t','http_cache_port_t') for m in specific):
        assert not specific, 'HTTP port already labeled '+','.join(specific)+'; choose a different http_port'
        run(['semanage','port','-a','-t','http_port_t','-p','tcp',str(port)])

def resolver(lab):
    from lab import write, run
    domain=lab.c['base_domain']
    if run(['systemctl','is-active','systemd-resolved'],check=False).returncode==0:
        write('/etc/systemd/resolved.conf.d/ocplab.conf','[Resolve]\nDNS='+lab.gw+'\nDomains=~'+domain+'\n',0o644)
        run(['systemctl','restart','systemd-resolved'])
    elif run(['systemctl','is-active','NetworkManager'],check=False).returncode==0:
        write('/etc/NetworkManager/conf.d/90-ocplab-dns.conf','[main]\ndns=dnsmasq\n',0o644)
        write('/etc/NetworkManager/dnsmasq.d/ocplab.conf','server=/'+domain+'/'+lab.gw+'\n',0o644)
        run(['nmcli','general','reload','conf'])
        run(['nmcli','general','reload','dns-full'])
    else:
        # Preserve upstream service through libvirt DNS, which must use explicit forwarders.
        p=Path('/etc/resolv.conf')
        assert not p.is_symlink(), 'Resolver symlink without a supported manager: configure split DNS for '+domain+' via '+lab.gw
        backup=lab.w/'backups/resolv.conf'
        if not backup.exists(): write(backup,p.read_bytes())
        write(p,'nameserver '+lab.gw+'\n',0o644)
    for name in ['api.'+lab.domain, 'api-int.'+lab.domain, 'dns-check.apps.'+lab.domain,lab.c['registry']['hostname']]:
        assert socket.gethostbyname(name)==lab.gw, 'Host resolver returned unexpected address for '+name

def firewall(lab,ports):
    from lab import run
    if not shutil.which('firewall-cmd') or run(['firewall-cmd','--state'],check=False).returncode:
        print('firewalld inactive: preserve existing firewall; permit configured listeners in your site INPUT policy.',flush=True)
        return
    sources=lab.c.get('exposure',{}).get('allowed_cidrs',[])
    for permanent in [[],['--permanent']]:
        for source in sources:
            for proto,port in ports:
                rule='rule family="ipv4" source address="'+source+'" port port="'+str(port)+'" protocol="'+proto+'" accept'
                run(['firewall-cmd',*permanent,'--add-rich-rule='+rule])
    # Libvirt's bridge zone handles guest DNS/DHCP; allow boot assets, mirror and NTP there.
    zone=run(['firewall-cmd','--get-zone-of-interface='+lab.net['bridge']])
    assert zone and zone!='no zone', 'Libvirt bridge has no firewalld zone'
    for permanent in [[],['--permanent']]:
        for port in [str(lab.c['http_port'])+'/tcp',str(lab.c['registry']['port'])+'/tcp','123/udp','6443/tcp','22623/tcp','80/tcp','443/tcp']:
            run(['firewall-cmd',*permanent,'--zone='+zone,'--add-port='+port])

def nginx_default(lab):
    from lab import write
    p=Path('/etc/nginx/nginx.conf'); original=p.read_text(); result=original
    # Remove packaged default server blocks, preserving global/http settings and includes.
    spans=[]
    for m in re.finditer(r'(?m)^\s*server\s*\{',original):
        start=original.index('{',m.start()); level=1; end=start+1
        while end<len(original) and level:
            if original[end]=='{': level+=1
            if original[end]=='}': level-=1
            end+=1
        assert level==0, 'Unbalanced nginx server block; inspect nginx.conf'
        block=original[m.start():end]
        if re.search(r'listen\s+[^;]*default_server\s*;',block): spans.append((m.start(),end))
    for start,end in reversed(spans): result=result[:start]+result[end:]
    if result!=original:
        backup=lab.w/'backups/nginx.conf'
        if not backup.exists(): write(backup,original)
        write(p,result,0o644)
