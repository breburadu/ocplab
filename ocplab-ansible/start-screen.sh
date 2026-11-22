#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v screen >/dev/null || { echo 'Run ./bootstrap-host.sh to install Screen'; exit 1; }
config=$(realpath "${1:-config/lab.json}")
shift "$(( $# > 0 ? 1 : 0 ))"
if [ "$#" -eq 0 ]; then
  set -- preflight prepare mirror assets ignition vms complete virtualization storage expose validate
fi
session=${OCP_SCREEN_SESSION:-ocplab-install}
[[ "$session" =~ ^[a-zA-Z0-9_-]+$ ]] || exit 1
if screen -ls | grep -Eq "[.]${session}[[:space:]]"; then
  echo "Session exists. Reattach: screen -r $session"; exit 1
fi
# Two shells in one session. No task is executed outside Screen.
screen -dmS "$session" -t installer bash "$PWD/scripts/session_run.sh" "$config" "$@"
screen -S "$session" -X screen -t logs python3 -u "$PWD/scripts/follow_logs.py" "$config"
screen -S "$session" -X select 0
echo "Started $session: window 0 installer; window 1 logs."
echo "Ctrl+A then 0/1 switches; Ctrl+A then D detaches."
if [ -t 0 ] && [ -t 1 ]; then exec screen -r "$session"; fi
