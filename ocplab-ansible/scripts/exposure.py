"""LAN listeners and stable TCP publication of VM and pod Services."""
import ipaddress, json, re, shutil, socket
from pathlib import Path
import yaml

def settings(c):
    x=c.get('exposure',{})
    result={'lan_ips':[], 'allowed_cidrs':[], 'dns_enabled':True,
            'upstream_dns':['1.1.1.1','1.0.0.1'], 'tcp_forwards':[], 'services':[], **x}
    for ip in result['lan_ips']:
        a=ipaddress.ip_address(ip); assert a.version==4 and not a.is_unspecified and not a.is_loopback
    assert len(set(result['lan_ips']))==len(result['lan_ips'])
    for cidr in result['allowed_cidrs']: assert ipaddress.ip_network(cidr).version==4
    for ip in result['upstream_dns']:
        a=ipaddress.ip_address(ip)
        assert a.version==4 and not a.is_loopback and not a.is_unspecified and ip not in result['lan_ips'], 'Upstream DNS must not point back at a lab listener'
    assert result['upstream_dns'], 'Explicit upstream DNS is required to avoid resolver loops'
    assert c['network']['gateway'] not in result['upstream_dns']
    assert not result['lan_ips'] or result['allowed_cidrs'], 'Set exposure.allowed_cidrs for LAN access'
    ports={53,80,443,6443,22623,c['registry']['port'],c['http_port']}
    names=set()
    for item in result['tcp_forwards']+result['services']:
        assert re.fullmatch(r'[a-z][a-z0-9-]{0,39}',item['name']), 'Unsafe proxy name'
        assert item['name'] not in names; names.add(item['name'])
        port=item['listen_port']; assert isinstance(port,int) and 1024<=port<=65535 and port not in ports, 'Duplicate/reserved listener'
        ports.add(port)
    for item in result['tcp_forwards']:
        assert re.fullmatch(r'[a-zA-Z0-9.-]+',item['host'])
        assert 1<=int(item['port'])<=65535
    for item in result['services']:
        for key in ['namespace','service']:
            assert re.fullmatch(r'[a-z0-9][a-z0-9.-]*',item[key])
        assert isinstance(item['port'],int) and 1<=item['port']<=65535
    return result

def proxy_text(lab):
    x=settings(lab.c); text=''
    entries=[]
    mapping={n['name']:n['ip'] for n in lab.nodes}
    for item in x['tcp_forwards']:
        host=mapping.get(item['host'],item['host'])
        # Resolve before rendering; never put unchecked text into HAProxy syntax.
        ip=socket.gethostbyname(host)
        entries.append((item['name'],item['listen_port'],[(ip,item['port'])]))
    path=lab.w/'published-services.json'
    if path.exists():
        cached=json.loads(path.read_text())
        for item in x['services']:
            key=item['name']
            match=next((v for v in cached if v['config']==item),None)
            if match: entries.append((key,item['listen_port'],[(n['ip'],match['node_port']) for n in lab.c['nodes']]))
    for name,port,backends in entries:
        text+='frontend published_'+name+'\n'
        for ip in [lab.gw]+x['lan_ips']: text+='    bind '+ip+':'+str(port)+'\n'
        text+='    default_backend published_'+name+'_nodes\nbackend published_'+name+'_nodes\n    balance roundrobin\n    option tcp-check\n'
        for i,(ip,p) in enumerate(backends): text+='    server backend'+str(i)+' '+ip+':'+str(p)+' check\n'
    return text

def publish(lab):
    from lab import write
    x=settings(lab.c); results=[]
    for item in x['services']:
        ns=item['namespace']
        obj=json.loads(lab.ocmd('-n',ns,'get','service',item['service'],'-o','json'))
        spec=obj['spec']
        assert spec.get('selector'), 'Only selector-backed Services can be published'
        port=next((p for p in spec['ports'] if p['port']==item['port']),None)
        assert port and port.get('protocol','TCP')=='TCP', 'Only TCP Service ports supported'
        name='lab-proxy-'+item['name']
        old=lab.ocmd('-n',ns,'get','service',name,'--ignore-not-found','-o','json')
        if old:
            assert json.loads(old)['metadata'].get('labels',{}).get('ocplab-managed')=='service-proxy', 'Refusing foreign Service takeover'
        service={'apiVersion':'v1','kind':'Service','metadata':{'name':name,'namespace':ns,'labels':{'ocplab-managed':'service-proxy'}},
          'spec':{'type':'NodePort','externalTrafficPolicy':'Cluster','selector':spec['selector'],
          'ports':[{'name':'tcp','port':item['port'],'targetPort':port.get('targetPort',item['port']),'protocol':'TCP'}]}}
        path=lab.w/'exposure'/(name+'.yaml')
        write(path,yaml.safe_dump(service)); lab.ocmd('apply','-f',path)
        actual=json.loads(lab.ocmd('-n',ns,'get','service',name,'-o','json'))
        results.append({'config':item,'node_port':actual['spec']['ports'][0]['nodePort']})
        print('Published Service '+ns+'/'+item['service']+' through '+name,flush=True)
    write(lab.w/'published-services.json',json.dumps(results))
    setup(lab)
    lab.haproxy(False)
    lab.mark('expose')

def setup(lab):
    from lab import write, run
    from host import firewall
    x=settings(lab.c)
    local=json.loads(run(['ip','-j','-4','address','show']))
    ips={a['local'] for link in local for a in link.get('addr_info',[]) if 'local' in a}
    assert set(x['lan_ips'])<=ips, 'Every exposure.lan_ips address must be assigned locally (reserve DHCP leases)'
    ports=[('tcp',p) for p in [80,443,6443]+[i['listen_port'] for i in x['tcp_forwards']+x['services']]]
    if x['dns_enabled'] and x['lan_ips']: ports += [('udp',53),('tcp',53)]
    firewall(lab,ports)
    # Own table only; preserve libvirt, Podman and site firewall tables.
    if x['lan_ips']:
        nft=shutil.which('nft'); assert nft, 'nftables package required'
        lines=['add table inet ocplab_access','flush table inet ocplab_access',
               'add chain inet ocplab_access input { type filter hook input priority -10; policy accept; }']
        addrs='{ '+', '.join(x['lan_ips'])+' }'; sources='{ '+', '.join(x['allowed_cidrs']+[lab.net['cidr']]+[ip+'/32' for ip in x['lan_ips']])+' }'
        for proto in ['tcp','udp']:
            numbers=sorted(set(p for pro,p in ports if pro==proto))
            if numbers:
                lines.append('add rule inet ocplab_access input ip daddr '+addrs+' '+proto+' dport { '+', '.join(map(str,numbers))+' } ip saddr != '+sources+' drop')
        path=Path('/etc/ocplab-access.nft'); write(path,'\n'.join(lines)+'\n',0o600)
        run([nft,'-c','-f',path])
        write('/etc/systemd/system/ocplab-access.service','[Unit]\nDescription=LAN ACL for lab listeners\nBefore=haproxy.service ocplab-lan-dns.service\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart='+nft+' -f '+str(path)+'\nExecReload='+nft+' -f '+str(path)+'\n[Install]\nWantedBy=multi-user.target\n',0o644)
        run(['systemctl','daemon-reload']); run(['systemctl','enable','--now','ocplab-access'])
        run(['systemctl','reload','ocplab-access'])
    if x['dns_enabled'] and x['lan_ips']:
        answer=x['lan_ips'][0]
        config='port=53\nbind-dynamic\nno-hosts\nno-resolv\ndomain-needed\nbogus-priv\npid-file=/run/ocplab-lan-dns.pid\nlog-facility=-\n'
        config+=''.join('listen-address='+ip+'\n' for ip in x['lan_ips'])
        config+=''.join('server='+ip+'\n' for ip in x['upstream_dns'])
        config+='local=/'+lab.domain+'/\nhost-record=api.'+lab.domain+','+answer+'\naddress=/apps.'+lab.domain+'/'+answer+'\n'
        write('/etc/ocplab-lan-dns.conf',config,0o644)
        binary=shutil.which('dnsmasq'); assert binary
        write('/etc/systemd/system/ocplab-lan-dns.service','[Unit]\nDescription=OpenShift LAN DNS\nAfter=network-online.target ocplab-access.service\nWants=network-online.target\n[Service]\nType=simple\nExecStartPre='+binary+' --test --conf-file=/etc/ocplab-lan-dns.conf\nExecStart='+binary+' --keep-in-foreground --conf-file=/etc/ocplab-lan-dns.conf\nRestart=on-failure\nRestartSec=5\n[Install]\nWantedBy=multi-user.target\n',0o644)
        run(['systemctl','daemon-reload']); run(['systemctl','enable','ocplab-lan-dns'])
        run(['systemctl','restart','ocplab-lan-dns'])
    elif Path('/etc/systemd/system/ocplab-lan-dns.service').exists():
        run(['systemctl','disable','--now','ocplab-lan-dns'])
