#!/usr/bin/env python3
"""WireGuard Manager for Debian/Ubuntu (IPv4, multiple instances)."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path('/etc/wireguard')
DATA = ROOT / 'wg-manager'
STATE = DATA / 'state.json'
EXPORTS = DATA / 'exports'
DELAYED = Path('/usr/local/libexec/wg-quick-delayed')
DELAY_SECONDS = 2
IFACE = re.compile(r'^[a-zA-Z0-9_.-]{1,15}$')
CLIENT = re.compile(r'^[a-zA-Z0-9_-]{1,48}$')


def run(args, *, input_text=None, check=True, display=False):
    return subprocess.run(args, input=input_text, text=True,
                          stdout=None if display else subprocess.PIPE,
                          stderr=None if display else subprocess.PIPE,
                          check=check)


def die(message):
    raise RuntimeError(message)


def ask(label, default=None):
    value = input(f'{label}' + (f' [{default}]' if default is not None else '') + ': ').strip()
    return value if value else default


def yes(label, default=False):
    suffix = 'Y/n' if default else 'y/N'
    val = input(f'{label} [{suffix}]: ').strip().lower()
    return default if not val else val in ('y', 'yes')


def write_file(path, contents, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp = tempfile.mkstemp(prefix='.wg-manager-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w') as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_state():
    if not STATE.exists():
        return {'version': 1, 'instances': {}}
    result = json.loads(STATE.read_text())
    if result.get('version') != 1 or not isinstance(result.get('instances'), dict):
        die('Invalid or unsupported manager state')
    return result


def save_state(state):
    write_file(STATE, json.dumps(state, indent=2) + '\n')


def prerequisites():
    required = {'wg': 'wireguard-tools', 'wg-quick': 'wireguard-tools',
                'ip': 'iproute2', 'iptables': 'iptables', 'qrencode': 'qrencode',
                'sysctl': 'procps', 'systemctl': 'systemd'}
    missing = sorted({pkg for cmd, pkg in required.items() if not shutil.which(cmd)})
    if not missing:
        print('Required executables: OK')
        return
    print('Missing packages: ' + ', '.join(missing))
    if not yes('Install with apt-get?', True):
        die('Required packages are missing')
    run(['apt-get', 'update'], display=True)
    run(['apt-get', 'install', '-y', *missing], display=True)
    if any(not shutil.which(cmd) for cmd in required):
        die('Some required commands remain unavailable')


def ensure_delayed_binary():
    """Build delayed copy, never edit distribution wg-quick."""
    source = Path(shutil.which('wg-quick') or '/usr/bin/wg-quick')
    raw = source.read_text()
    # Match BOTH explicit and auto-MTU branches in wg-quick's set_mtu_up().
    pattern = re.compile(r'(?m)^([ \t]*)(cmd ip link set mtu [^\n]* up dev "\$INTERFACE")\s*$')
    def delay(match):
        return match.group(1) + f'sleep {DELAY_SECONDS}\n' + match.group(1) + match.group(2)
    modified, count = pattern.subn(delay, raw)
    if not count:
        die('Unsupported wg-quick format; cannot add safe activation delay')
    DELAYED.parent.mkdir(parents=True, exist_ok=True)
    # Validate exact generated shell script before replacing installed copy.
    proc = run(['bash', '-n'], input_text=modified, check=False)
    if proc.returncode:
        die('Delayed wg-quick failed bash syntax validation: ' + proc.stderr)
    write_file(DELAYED, modified, 0o755)
    print(f'Delayed wg-quick ready ({DELAY_SECONDS}s; {count} activation branch(es))')


def override_path(name):
    return Path(f'/etc/systemd/system/wg-quick@{name}.service.d/10-manager-delay.conf')


def install_override(name):
    ensure_delayed_binary()
    write_file(override_path(name),
               '[Service]\nExecStart=\n'
               f'ExecStart={DELAYED} up %i\n', 0o644)
    run(['systemctl', 'daemon-reload'])


def remove_override(name):
    p = override_path(name)
    if p.exists():
        p.unlink()
        try:
            p.parent.rmdir()
        except OSError:
            pass
        run(['systemctl', 'daemon-reload'])


def interfaces():
    data = json.loads(run(['ip', '-j', '-4', 'address', 'show']).stdout)
    rows = []
    for d in data:
        if d['ifname'] == 'lo':
            continue
        ips = [f"{a['local']}/{a['prefixlen']}" for a in d.get('addr_info', [])
               if a.get('family') == 'inet']
        rows.append({'name': d['ifname'], 'state': d.get('operstate', '?'), 'ips': ips})
    return rows


def route_egress():
    result = run(['ip', '-j', '-4', 'route', 'get', '1.1.1.1'], check=False)
    if result.returncode == 0:
        try:
            routes = json.loads(result.stdout)
            if routes:
                return routes[0].get('dev')
        except (ValueError, IndexError):
            pass
    return None


def network_overview():
    rows = interfaces()
    uplink = route_egress()
    print('\nDetected interfaces:')
    for row in rows:
        mark = ' [SELECTED INTERNET ROUTE]' if row['name'] == uplink else ''
        print(f"  {row['name']:18} {row['state']:8} {', '.join(row['ips']) or '-'}{mark}")
    return rows, uplink


def parse_subnets(value):
    networks = []
    for item in value.split(','):
        if not item.strip():
            continue
        net = ipaddress.ip_network(item.strip(), strict=False)
        if net.version != 4:
            die('IPv4 routing only in this version')
        networks.append(str(net))
    if not networks:
        die('Specify at least one IPv4 route')
    return list(dict.fromkeys(networks))


def endpoint(value):
    if not value or any(c.isspace() for c in value):
        die('Endpoint must be a hostname or IP without port')
    try:
        addr = ipaddress.ip_address(value)
        return f'[{addr}]' if addr.version == 6 else str(addr)
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9.-]{1,253}', value) or '..' in value or value.startswith('-'):
            die('Invalid endpoint hostname')
        return value


def keys():
    private = run(['wg', 'genkey']).stdout.strip()
    public = run(['wg', 'pubkey'], input_text=private + '\n').stdout.strip()
    return private, public


def fw_rules(name, inst):
    """Managed rules carry a unique comment; never delete unrelated rules."""
    subnet = inst['network']
    comment = f'wgm-{name}'
    rules = []
    for dev in inst['egress']:
        rules += [
            ('filter', 'FORWARD', f'-i {name} -o {dev} -s {subnet}'),
            ('filter', 'FORWARD', f'-i {dev} -o {name} -d {subnet} -m conntrack --ctstate RELATED,ESTABLISHED')
        ]
        # Above filter rules have ACCEPT target.
        rules.append(('nat', 'POSTROUTING', f'-s {subnet} -o {dev}'))
    if not inst['isolate']:
        rules.append(('filter', 'FORWARD', f'-i {name} -o {name}'))
    if inst['open_udp']:
        rules.append(('filter', 'INPUT', f'-p udp --dport {inst["port"]}'))
    result = []
    for table, chain, match in rules:
        target = 'MASQUERADE' if table == 'nat' else 'ACCEPT'
        rule = f'{match} -m comment --comment {comment} -j {target}'
        result.append((table, chain, rule))
    return result


def server_text(name, inst):
    net = ipaddress.ip_network(inst['network'])
    lines = [
        '# Generated by wg-manager. Changes here may be overwritten.',
        '[Interface]',
        f"Address = {inst['address']}/{net.prefixlen}",
        f"ListenPort = {inst['port']}",
        f"PrivateKey = {inst['private']}",
        'SaveConfig = false'
    ]
    rules = fw_rules(name, inst)
    for table, chain, rule in rules:
        prefix = f'iptables -w -t {table}'
        lines.append(f'PostUp = {prefix} -C {chain} {rule} 2>/dev/null || {prefix} -A {chain} {rule}')
    for table, chain, rule in reversed(rules):
        prefix = f'iptables -w -t {table}'
        lines.append(f'PostDown = {prefix} -C {chain} {rule} 2>/dev/null && {prefix} -D {chain} {rule} || true')
    for client, peer in sorted(inst['clients'].items()):
        lines += ['', f'# Client {client}', '[Peer]', f"PublicKey = {peer['public']}",
                  f"AllowedIPs = {peer['ip']}/32"]
    return '\n'.join(lines) + '\n'


def client_text(inst, peer):
    result = ['[Interface]', f"PrivateKey = {peer['private']}", f"Address = {peer['ip']}/32"]
    if peer['dns']:
        result.append('DNS = ' + peer['dns'])
    result += ['', '[Peer]', f"PublicKey = {inst['public']}",
               'AllowedIPs = ' + ', '.join(peer['allowed']),
               f"Endpoint = {endpoint(inst['endpoint'])}:{inst['port']}",
               f"PersistentKeepalive = {peer['keepalive']}"]
    return '\n'.join(result) + '\n'


def get_inst(state, name):
    if name not in state['instances']:
        die(f'No managed instance called {name}')
    return state['instances'][name]


def online(name):
    return run(['wg', 'show', name], check=False).returncode == 0


def sync_conf(name, inst):
    write_file(ROOT / f'{name}.conf', server_text(name, inst))


def enable_forwarding():
    p = Path('/etc/sysctl.d/90-wg-manager-ipv4.conf')
    if p.exists() and 'net.ipv4.ip_forward = 1' not in p.read_text():
        die(f'Unexpected existing sysctl config: {p}')
    write_file(p, 'net.ipv4.ip_forward = 1\n', 0o644)
    run(['sysctl', '-w', 'net.ipv4.ip_forward=1'])


def add_instance(state):
    print('\n== Create WireGuard instance ==')
    name = ask('Interface', f'wg{len(state["instances"])}')
    if not name or not IFACE.fullmatch(name):
        die('Invalid interface name')
    if name in state['instances'] or (ROOT / f'{name}.conf').exists():
        die('Interface already exists in state or on disk; will not overwrite')
    rows, uplink = network_overview()
    default_net = f'10.77.{len(state["instances"])}.0/24'
    net = ipaddress.ip_network(ask('VPN IPv4 subnet', default_net), strict=True)
    if net.version != 4 or net.prefixlen > 30:
        die('VPN subnet must be IPv4 and provide at least two usable addresses')
    for existing in state['instances'].values():
        if net.overlaps(ipaddress.ip_network(existing['network'])):
            die('Overlaps an existing managed VPN subnet')
    for row in rows:
        for addr in row['ips']:
            if net.overlaps(ipaddress.ip_interface(addr).network):
                die(f'Overlaps local interface subnet on {row["name"]}')
    address = ipaddress.ip_address(ask('Server tunnel IP', str(next(net.hosts()))))
    if address.version != 4 or address not in net or address in (net.network_address, net.broadcast_address):
        die('Invalid server tunnel IP')
    used_ports = {x['port'] for x in state['instances'].values()}
    suggested_port = next(p for p in range(51820, 52000) if p not in used_ports)
    port = int(ask('Listen UDP port', str(suggested_port)))
    if port not in range(1, 65536) or port in used_ports:
        die('Invalid or already managed UDP port')
    public = ask('Public IP / DNS endpoint')
    endpoint(public)
    candidates = [r['name'] for r in rows if r['name'] != name and not r['name'].startswith('wg')]
    if not candidates:
        die('No suitable egress interfaces found')
    suggested = uplink if uplink in candidates else candidates[0]
    print('NAT egress choices: ' + ', '.join(candidates))
    egress = list(dict.fromkeys(x.strip() for x in ask('NAT egress interface(s)', suggested).split(',') if x.strip()))
    if not egress or any(x not in candidates for x in egress):
        die('Invalid NAT egress interface')
    isolate = yes('Isolate clients from each other?', False)
    open_udp = yes(f'Manage host INPUT accept for UDP/{port}?', True)
    dns = ask('Client DNS (comma separated)', '1.1.1.1')
    if dns:
        for item in dns.split(','):
            ipaddress.ip_address(item.strip())
    allowed = parse_subnets(ask('Client AllowedIPs (full/split tunnel)', '0.0.0.0/0'))
    keepalive = int(ask('Default client keepalive (seconds)', '25'))
    if not 0 <= keepalive <= 65535:
        die('Invalid keepalive')
    private, pubkey = keys()
    inst = {'network': str(net), 'address': str(address), 'port': port,
            'endpoint': public, 'egress': egress, 'isolate': isolate,
            'open_udp': open_udp, 'dns': dns, 'allowed': allowed,
            'keepalive': keepalive, 'private': private, 'public': pubkey,
            'clients': {}}
    print(f'\nPlan: {name} {address}/{net.prefixlen}, UDP/{port}, endpoint {public}')
    print(f'NAT: {str(net)} -> {", ".join(egress)}; AllowedIPs: {", ".join(allowed)}')
    print(f'Activation delay: {DELAY_SECONDS}s (systemd + manager)')
    if not yes('Create and start instance?', True):
        return
    # Prepare startup mechanism before starting service; preserve config/key on failure.
    install_override(name)
    enable_forwarding()
    sync_conf(name, inst)
    state['instances'][name] = inst
    save_state(state)
    if run(['systemctl', 'enable', f'wg-quick@{name}.service'], check=False, display=True).returncode:
        print('WARNING: could not enable systemd service')
    if run(['systemctl', 'start', f'wg-quick@{name}.service'], check=False, display=True).returncode:
        print(f'ERROR: {name} could not start; saved for diagnosis.')
        print(f'Run: journalctl -u wg-quick@{name} -n 50 --no-pager')
    else:
        print(f'SUCCESS: {name} started and configured for automatic startup')


def list_instances(state):
    if not state['instances']:
        print('No managed instances')
    for name, inst in sorted(state['instances'].items()):
        print(f"{name}: {'UP' if online(name) else 'DOWN'} UDP/{inst['port']} "
              f"subnet={inst['network']} peers={len(inst['clients'])} NAT={','.join(inst['egress'])}")


def choose_instance(state, choice=None):
    if choice:
        get_inst(state, choice)
        return choice
    list_instances(state)
    if not state['instances']:
        die('Create an instance first')
    choice = ask('Instance', next(iter(state['instances'])))
    get_inst(state, choice)
    return choice


def delete_instance(state, name):
    inst = get_inst(state, name)
    print(f'About to delete {name} and revoke {len(inst["clients"])} managed clients')
    if not yes('Delete this instance?', False):
        return
    # A failed oneshot service can coexist with a manually activated interface.
    if online(name):
        result = run([str(DELAYED) if DELAYED.exists() else 'wg-quick', 'down', name], check=False, display=True)
        if result.returncode or online(name):
            die('Unable to deactivate interface; deletion cancelled')
    run(['systemctl', 'stop', f'wg-quick@{name}.service'], check=False)
    if online(name):
        die('Interface remains active; deletion cancelled')
    run(['systemctl', 'disable', f'wg-quick@{name}.service'], check=False)
    remove_override(name)
    conf = ROOT / f'{name}.conf'
    if conf.exists():
        conf.unlink()
    # Exports intentionally retained: must be handled securely by administrator.
    del state['instances'][name]
    save_state(state)
    print(f'Deleted {name}. Sensitive exports, if any, remain in {EXPORTS / name}')


def export_peer(state, name, client, output=None, show_qr=True):
    inst = get_inst(state, name)
    if client not in inst['clients']:
        die('Client not found')
    base = Path(output).expanduser().resolve() if output else EXPORTS / name
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    base.chmod(0o700)
    content = client_text(inst, inst['clients'][client])
    conf = base / f'{name}-{client}.conf'
    png = base / f'{name}-{client}.png'
    write_file(conf, content)
    run(['qrencode', '-t', 'PNG', '-s', '6', '-m', '2', '-o', str(png)], input_text=content)
    png.chmod(0o600)
    print(f'Client config: {conf}\nQR image:      {png}')
    if show_qr:
        print('\nScan QR with WireGuard mobile app:\n')
        run(['qrencode', '-t', 'ANSIUTF8'], input_text=content, display=True)
    print('SECURITY: config and QR include the client private key')


def add_client(state, name, client):
    inst = get_inst(state, name)
    if not client:
        client = ask('Client name')
    if not client or not CLIENT.fullmatch(client) or client in inst['clients']:
        die('Invalid or duplicate client name')
    net = ipaddress.ip_network(inst['network'])
    occupied = {inst['address']} | {p['ip'] for p in inst['clients'].values()}
    assigned = next((str(ip) for ip in net.hosts() if str(ip) not in occupied), None)
    if not assigned:
        die('No free client addresses')
    address = ipaddress.ip_address(ask('Client tunnel IP', assigned))
    if address.version != 4 or address not in net or str(address) in occupied or address in (net.network_address, net.broadcast_address):
        die('Invalid or occupied client address')
    allowed = parse_subnets(ask('Client AllowedIPs', ','.join(inst['allowed'])))
    dns = ask('Client DNS', inst['dns'])
    if dns:
        for entry in dns.split(','):
            ipaddress.ip_address(entry.strip())
    keepalive = int(ask('PersistentKeepalive', str(inst['keepalive'])))
    if not 0 <= keepalive <= 65535:
        die('Invalid keepalive')
    private, public = keys()
    inst['clients'][client] = {'ip': str(address), 'private': private,
                               'public': public, 'allowed': allowed,
                               'dns': dns, 'keepalive': keepalive}
    sync_conf(name, inst)
    save_state(state)
    if online(name):
        result = run(['wg', 'set', name, 'peer', public, 'allowed-ips', f'{address}/32'], check=False)
        if result.returncode:
            print('WARNING: peer was saved but live update failed: ' + result.stderr.strip())
    else:
        print('NOTE: instance down; peer will load at next start')
    print(f'Added {client} ({address}/32)')
    export_peer(state, name, client, show_qr=True)


def list_clients(state, name):
    inst = get_inst(state, name)
    if not inst['clients']:
        print('No clients')
    result = run(['wg', 'show', name, 'latest-handshakes'], check=False)
    stamps = {}
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2:
                stamps[parts[0]] = int(parts[1])
    for client, peer in sorted(inst['clients'].items()):
        ts = stamps.get(peer['public'], 0)
        last = 'never' if not ts else __import__('datetime').datetime.fromtimestamp(ts).astimezone().isoformat(timespec='seconds')
        print(f"{client:24} {peer['ip']:16} handshake={last}")


def delete_client(state, name, client):
    inst = get_inst(state, name)
    if client not in inst['clients']:
        die('Client not found')
    if not yes(f'Revoke {client} from {name}?', False):
        return
    public = inst['clients'][client]['public']
    if online(name):
        result = run(['wg', 'set', name, 'peer', public, 'remove'], check=False)
        if result.returncode:
            die('Live peer revocation failed; refusing to erase state: ' + result.stderr.strip())
    del inst['clients'][client]
    sync_conf(name, inst)
    save_state(state)
    for ext in ('.conf', '.png'):
        p = EXPORTS / name / f'{name}-{client}{ext}'
        if p.exists():
            p.unlink()
    print('Revoked client; separately distributed exports cannot be recalled')


def doctor(state):
    print('Route to 1.1.1.1:')
    run(['ip', '-4', 'route', 'get', '1.1.1.1'], display=True, check=False)
    network_overview()
    print('IP forwarding: ' + run(['sysctl', '-n', 'net.ipv4.ip_forward']).stdout.strip())
    print('iptables: ' + run(['iptables', '--version']).stdout.strip())
    list_instances(state)
    for name in state['instances']:
        print(f'{name} systemd override: {override_path(name).exists()}')


def menu(state):
    while True:
        print('\n=== WireGuard Manager ===')
        print('1) List instances    2) Add instance    3) Delete instance')
        print('4) List clients      5) Add client      6) Delete client')
        print('7) Export / QR       8) Doctor          0) Exit')
        op = ask('Choice', '0')
        try:
            if op == '0':
                return
            if op == '1':
                list_instances(state)
            elif op == '2':
                add_instance(state)
            elif op == '3':
                delete_instance(state, choose_instance(state))
            elif op == '4':
                list_clients(state, choose_instance(state))
            elif op == '5':
                add_client(state, choose_instance(state), None)
            elif op == '6':
                name = choose_instance(state)
                list_clients(state, name)
                delete_client(state, name, ask('Client to delete'))
            elif op == '7':
                name = choose_instance(state)
                list_clients(state, name)
                export_peer(state, name, ask('Client to export'), show_qr=True)
            elif op == '8':
                doctor(state)
            else:
                print('Unknown choice')
        except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
            print('ERROR:', exc, file=sys.stderr)


def main():
    os.umask(0o077)
    if os.geteuid() != 0:
        die('Run as root (sudo python3 wg-manager.py)')
    if not Path('/etc/debian_version').exists():
        die('Debian/Ubuntu only')
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    ROOT.chmod(0o700)
    DATA.chmod(0o700)
    p = argparse.ArgumentParser(description='WireGuard manager with delayed startup')
    sub = p.add_subparsers(dest='command')
    sub.add_parser('doctor')
    sub.add_parser('menu')
    i = sub.add_parser('instance')
    ii = i.add_subparsers(dest='action', required=True)
    ii.add_parser('add')
    ii.add_parser('list')
    ii.add_parser('delete').add_argument('name')
    c = sub.add_parser('client')
    cc = c.add_subparsers(dest='action', required=True)
    for action in ('add', 'list', 'delete', 'export'):
        a = cc.add_parser(action)
        a.add_argument('instance')
        if action != 'list':
            a.add_argument('name')
        if action == 'export':
            a.add_argument('--output')
            a.add_argument('--show-qr', action='store_true')
    args = p.parse_args()
    prerequisites()
    state = load_state()
    if args.command is None:
        if not state['instances']:
            print('First run: configure first managed WireGuard instance')
            add_instance(state)
        menu(state)
    elif args.command == 'menu':
        menu(state)
    elif args.command == 'doctor':
        doctor(state)
    elif args.command == 'instance':
        if args.action == 'add':
            add_instance(state)
        elif args.action == 'list':
            list_instances(state)
        elif args.action == 'delete':
            delete_instance(state, args.name)
    elif args.command == 'client':
        name = args.instance
        if args.action == 'add':
            add_client(state, name, args.name)
        elif args.action == 'list':
            list_clients(state, name)
        elif args.action == 'delete':
            delete_client(state, name, args.name)
        elif args.action == 'export':
            export_peer(state, name, args.name, args.output, args.show_qr)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError, KeyboardInterrupt) as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)