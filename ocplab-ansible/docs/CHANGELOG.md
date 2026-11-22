# v3.0.0

- Read-only hardware sizing script and initial run.sh menu.
- Distribution detection and APT/DNF, libvirt, CA, Chrony, QEMU and SELinux adapters.
- Explicit supported-module selection and optional catalog discovery.
- NAT by default for new configs; existing network settings preserved.
- LAN HAProxy/DNS, source ACLs, selected VM TCP forwarding and pod Service publication via NodePort.
- Longer completion/storage budgets, retryable API readiness and periodic diagnostics.
- Locked migration of operational settings; no cluster identity changes.
- GitHub Actions offline tests and syntax checks. No claim of physical multi-distribution testing.


# v2.0 — test-install fixes and storage automation

- Handle regular, symlink and hardlink binary entries in client archives.
- Run prepare preflight before setting the immutable configuration fingerprint.
- Recognize only the historical consent-only fingerprint failure before resources exist.
- Provide explicit config upgrade with backups and lock checking; preserve identity.
- Log URLs and cache verification; omit unavailable raw-image detached signature.
- Preserve existing libvirt UUID when switching installer boot to disk boot.
- Keep raw disks with cache=none; no claim that this remedies hardware faults.
- Rebuild the mirrored index with readable /configs and UID 1001; persist corrected reference.
- Diagnose async lock contention explicitly after Ctrl+C.
- Enable Ansible -vvvv, unbuffered phase logging and live subtask output.
- Add Screen installer/log windows; follow active files across phases.
- Add storage stage after virtualization: dedicated raw disks, XFS, UUID mounts,
  HPP, default StorageClass, and one-node write smoke test.
- Explicitly adopt verified pre-existing data disks without formatting them.
- Expand README: quick start, complete configuration reference, existing-cluster
  upgrade, Screen controls, retries, signatures, local storage and diagnostics.

Manual test evidence came from the existing installation. New v2 orchestration
has offline tests, not a fresh end-to-end deployment certification.
