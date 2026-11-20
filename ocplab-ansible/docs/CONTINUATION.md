# Continuation notes

This repository contains the v2 automation developed during the lab installation. It does not contain a backup of the running cluster or its credentials.

## Last reported installation

- Debian KVM bastion; OpenShift 4.22.18; OpenShift Virtualization 4.22.12.
- Three compact control-plane/worker nodes, ocplab-node-1 through ocplab-node-3, at 192.168.123.11–13.
- Libvirt bridge virbr-ocp, gateway 192.168.123.1; raw OS disks.
- Runtime directory /root/ocp-automated; kubeconfig under install/auth/kubeconfig.
- SSH user core; private key remains on the bastion at /root/ocp/ssh/id_ed25519.
- Dedicated 80 GiB vdb disks mounted at /var/hpvolumes; hostpath-csi is the default StorageClass, RWO/Filesystem, Retain, WaitForFirstConsumer.
- Storage provisioning and a write/read smoke test succeeded. Local storage is not replicated, and reported PVC capacity is not a per-volume enforced quota.
- Catalog permissions fix and virtualization installation succeeded on the test installation. v2 includes the corresponding automation.

## Pending LAN integration

Last supplied configuration has HAProxy listening only on 192.168.123.1 for 80, 443, 6443 and 22623. The bastion has Ethernet 10.20.30.40 and Wi-Fi 10.20.30.35, both DHCP addresses. Libvirt DNS listens on 192.168.123.1:53.

Proposed next change: reserve the Ethernet address, add LAN HAProxy listeners for 80/443/6443, keep 22623 internal, and provide separate LAN DNS answers for api.ocplab.lab.local and *.apps.ocplab.lab.local pointing to the LAN address. Keep internal DNS answers unchanged. No successful execution of these LAN changes has been reported. LAN listener/DNS management is not yet integrated into v2; generated HAProxy configuration may overwrite manual changes.

## Working safely on the existing install

Read README upgrade instructions before running stages. Preserve the existing config/lab.json, cluster identity, work directory, state, and credentials on the host. Do not replace them with example values or rerun a full installation merely to switch to Git.

The earlier failed installation had a QEMU crash and corrupted guest files; the precise cause was not established. The later clean deployment succeeded. Do not treat CPU or disk contention alone as proof of corruption or assume image-format changes diagnose the original failure.

## Verification

18 offline unit tests passed again during GitHub migration. The complete v2 installation has not been rerun against real KVM infrastructure. User-reported live validation covers the original deployment plus manual patches and storage configuration.

Run offline tests from the project directory:

```bash
python3 -m unittest discover -s tests -v
```
