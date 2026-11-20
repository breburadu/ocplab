#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
config=$1
shift
rc=0
for phase in "$@"; do
  ./run.sh "$phase" "$config" || { rc=$?; break; }
done
printf '\nRequested sequence finished with exit code %s. Logs window remains available.\n' "$rc"
exec bash
