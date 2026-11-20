#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
phase="${1:-preflight}"
config="$(realpath "${2:-config/lab.json}")"
work_dir=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["work_dir"])' "$config")
mkdir -p "$work_dir/logs"
log="$work_dir/logs/ansible-$phase-$(date +%Y%m%dT%H%M%S)-$$.log"
export PYTHONUNBUFFERED=1 ANSIBLE_FORCE_COLOR=0
vars=$(python3 -c 'import json,sys; print(json.dumps(dict(phase=sys.argv[1],config_file=sys.argv[2])))' "$phase" "$config")
# Lock the CLI wrapper too: do not redirect the viewer away from an active run.
exec 9>"$work_dir/runner.lock"
flock -n 9 || { echo 'Another run.sh is active. Reattach Screen or inspect logs.'; exit 1; }
if lslocks -n -o PATH | grep -Fxq "$work_dir/automation.lock"; then
  echo 'An async stage is still active. Reattach Screen; do not delete lock files.'; exit 1
fi
printf '%s\n' "$log" > "$work_dir/logs/active-ansible.path"
# Clear only the viewer pointer; never remove engine or ownership locks.
: > "$work_dir/logs/active-stage.path"
echo "Stage: $phase | Ansible: -vvvv | log: $log"
ansible-playbook -vvvv playbooks/site.yml --extra-vars "$vars" 2>&1 | tee "$log"
