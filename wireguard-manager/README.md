# WireGuard Manager

Debian/Ubuntu Python 3 command-line manager for multiple WireGuard interfaces, clients, firewall NAT, and QR/config exports.

## Current status

Version 2.0 was reported successfully tested on Debian with a working mobile WireGuard tunnel and a scannable terminal QR code. Further testing is recommended on other hosts and distributions.

## Features

- Interactive first-run setup and additional instances
- Required package detection and apt installation
- Inspect IPv4 interfaces and choose a NAT egress using the route to `1.1.1.1`
- Per-instance IPv4 forwarding, iptables FORWARD/MASQUERADE rules, and optional host INPUT allowance
- Two-second activation delay inserted into an independent local copy of `wg-quick`
- Per-instance systemd override for startup after reboot
- Create, list, and revoke clients; live peer changes when the interface is running
- Automatically export client `.conf`, QR PNG, and print the QR in the terminal when adding a client

## Installation

Install as root on a Debian-based system:

```bash
sudo install -m 700 wg-manager.py /usr/local/sbin/wg-manager
sudo wg-manager
```

The first-run wizard configures the initial managed interface.

## Commands

```bash
sudo wg-manager                             # Interactive wizard/menu
sudo wg-manager instance add                # Create another instance
sudo wg-manager instance list               # List managed interfaces
sudo wg-manager instance delete wg1         # Delete an instance
sudo wg-manager client add wg1 phone         # Add peer and show CLI QR
sudo wg-manager client list wg1              # List peers
sudo wg-manager client export wg1 phone --show-qr
sudo wg-manager client export wg1 phone --output /root/wg-exports
sudo wg-manager client delete wg1 phone
sudo wg-manager doctor                       # Network and state checks
```

## On-disk paths

- Server WireGuard configurations: `/etc/wireguard/<instance>.conf`
- Manager state: `/etc/wireguard/wg-manager/state.json`
- Client exports: `/etc/wireguard/wg-manager/exports/<instance>/<instance>-<client>.conf`
- QR images: `/etc/wireguard/wg-manager/exports/<instance>/<instance>-<client>.png`
- Delayed executable: `/usr/local/libexec/wg-quick-delayed`
- Instance systemd override: `/etc/systemd/system/wg-quick@<instance>.service.d/10-manager-delay.conf`

**Security:** Never commit `state.json`, WireGuard private keys, actual server configs, client exports, or QR PNG files. Files exported by the script contain client private keys. The delayed startup copy is generated on each configured host.

## Known limitations / development backlog

- IPv4 tunnel routing only
- Startup delay is a host-specific workaround; the root cause of the initial kernel `RTNETLINK answers: Permission denied` has not been diagnosed
- Multi-interface NAT is an explicit administrator choice; validate routes and firewall interactions before production use
- Existing managed instances cannot yet be edited in place through a dedicated `instance edit` subcommand
- No automated test suite yet
- Deleting instances leaves separately distributed exports and any retained export files for manual secure cleanup
- The manager uses iptables and may need integration-specific consideration for nftables/UFW policies

## Working history

Initial deployment used `wg1`, `10.77.0.0/24`, UDP `443`, with `enp38s0` as the internet-facing interface. A default two-second activation delay in a local `wg-quick` copy resolved the observed startup issue during testing. Mobile QR onboarding and tunnel operation were subsequently confirmed by the operator.

This repository contains code and documentation only, not live host keys or exported VPN profiles.
