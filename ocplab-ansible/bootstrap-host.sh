#!/usr/bin/env bash
# Install CLI prerequisites; evaluate hardware before running this if desired.
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo 'Run as root'; exit 1; }
. /etc/os-release
case "$ID" in
  debian|ubuntu)
    apt-get update
    apt-get install -y ansible-core python3-yaml screen git
    ;;
  rhel|fedora|centos|rocky|almalinux)
    dnf install -y ansible-core python3-pyyaml screen git
    ;;
  *) echo "Unsupported distribution: $ID"; exit 1;;
esac
echo 'Prerequisites ready. RHEL requires enabled repositories/subscription; no repository is enabled automatically.'
