# OpenShift compact KVM lab automation — v3.0

## 1. Start the installation

Run these commands **on the dedicated x86_64 Linux KVM host as root** (Debian, Ubuntu, RHEL or Fedora). This project contains code and example configuration, not your pull secret, private key, or an installed cluster. It deploys classic UPI: temporary bootstrap plus three schedulable control-plane nodes, a local image mirror, OpenShift Virtualization, and dedicated Hostpath storage.

### New installation

```bash
git clone https://github.com/breburadu/breburadu.git
cd breburadu/ocplab-ansible
# Read-only, no Ansible needed:
./run.sh assess
# Or ./run.sh for the initial assessment/setup/module menu.
./bootstrap-host.sh
python3 scripts/configure.py
chmod 600 config/lab.json /root/ocp/secrets/pull-secret.json
./run.sh preflight
./start-screen.sh config/lab.json
```

In the interactive configuration, confirm `manage_host_services=true` on the host you intend to dedicate to this lab. Use the actual path of your downloaded Red Hat pull secret. Press Enter to keep an example value. Enter booleans as `true`/`false`, numeric values as numbers, and lists as JSON arrays. The generated file is `config/lab.json`.

The Screen launcher runs the following sequence and **stops at the first failed stage**:

```text
preflight → prepare → mirror → assets → ignition → vms → complete
          → virtualization → storage → expose → validate
```

One Screen session contains two command-line windows:

| Window | Purpose |
|---|---|
| `0 installer` | Ansible with `-vvvv`, stage results, exit codes; returns to a shell at completion/failure |
| `1 logs` | Automatically follows the current Ansible log and engine stage log, including long-running subtask output |

Use **Ctrl+A, then 0 or 1** to switch windows. **Ctrl+A, then D** detaches safely. Reconnect with `screen -r ocplab-install`. To see both windows at once: Ctrl+A then uppercase S splits the display; Ctrl+A then Tab selects the other region; Ctrl+A then 1 selects logs there. Detaching does not stop installation. Ctrl+C is not a detach command.

For a different session name:

```bash
OCP_SCREEN_SESSION=ocplab-recovery ./start-screen.sh config/lab.json virtualization storage validate
```

To run only a stage without Screen: `./run.sh assets config/lab.json`. `run.sh` always enables `-vvvv`. The Screen launcher defaults to all stages; **do not use that default to resume an existing cluster**. Specify the remaining phases explicitly.

### Upgrade the automation on the cluster from our test installation

Do not replace the existing `config/lab.json` with an example. Do not rerun `prepare`, `ignition`, or `vms` on the completed cluster. Keep the working directory `/root/ocp-automated` and its ownership markers.

Extract the new archive into a separate directory, then copy your current config into it. For example, with the new ZIP at `/root/ocplab-ansible.zip`:

```bash
mkdir -p /root/ocp/automation-v2
unzip /root/ocplab-ansible.zip -d /root/ocp/automation-v2
cd /root/ocp/automation-v2/ocplab-ansible
install -m 0600 /root/ocp/ocplab-ansible/config/lab.json config/lab.json
python3 scripts/upgrade_config.py config/lab.json --adopt-storage
./start-screen.sh config/lab.json storage validate
```

The migration checks the old config fingerprint, acquires the engine lock, backs up the old config and fingerprint, and adds new catalog/storage options. Optional `--settings` merges only operational module/exposure/wait/timeout settings, preserving identity and network. `--adopt-storage` is for the three raw data disks already created during our test. Adoption requires the expected disk filename, size, live attachment, and mounted XFS filesystem. It never formats an adopted disk. Without existing data disks, omit `--adopt-storage`.

If a previous job is running, wait for it to finish before upgrading. Do not delete a lock file to make a second installer start.


### Hardware assessment and module selection

`./run.sh` opens the initial menu. `./run.sh assess` (or `python3 scripts/hardware.py --disk-path /var/lib/libvirt/images`) is read-only and works without Ansible or a configuration file. It reports distribution, CPU count, CPU virtualization flags, /dev/kvm, nested KVM, total/available RAM and filesystem free space. It suggests bootstrap and per-node sizes. Setup can apply the suggestion only when explicitly selected.

This installer still implements **three compact masters plus bootstrap**, not arbitrary node counts or single-node OpenShift. Four 16 GiB guests plus a 4 GiB host reserve require 68 GiB at bootstrap peak; a 62 GiB host requires explicit memory overcommit. CPU recommendations may overcommit logical CPUs. Storage budget is 460 GiB OS + 240 GiB data + 100 GiB reserve, plus additional room for mirrors. Sparse files do not reserve all of this space.

`./bootstrap-host.sh` installs Ansible/PyYAML/Screen prerequisites using APT or DNF. The prepare playbook selects distribution packages. RHEL requires suitable enabled repositories and entitlements; this script does not enable third-party repositories. Package availability, nested KVM and SELinux/firewall behavior must be validated on your host. RHEL-family handling includes QEMU ownership, discovered emulator, modular/monolithic libvirt, Chrony service, CA trust and targeted SELinux settings. SELinux is not disabled.

| Configuration | Behavior |
|---|---|
| `modules.selected` | `["core","virtualization","storage"]` by default. Core required; storage requires virtualization. Use `["core"]` for no optional operators. |
| `modules.list_catalog_packages` | False by default. When true, `./run.sh modules` additionally queries installed catalog PackageManifests. Requires a working cluster/catalog. |
| `waits.poll_seconds` | 30; readiness polling interval. |
| `waits.diagnostic_seconds` | 120; print operator/node or pod/warning-event snapshots while waiting. |
| `waits.api_seconds` | 900; permanent API readiness after bootstrap. |
| `exposure.lan_ips` | Assigned IPv4 addresses for LAN HAProxy/DNS listeners; empty by default. Reserve DHCP addresses first. |
| `exposure.allowed_cidrs` | Required when LAN listeners are enabled; restrict access to those source networks. |
| `exposure.dns_enabled` | True; separate LAN dnsmasq when LAN IPs exist. Internal libvirt DNS remains separate. |
| `exposure.upstream_dns` | Explicit upstream IPv4 resolvers, used by libvirt and LAN DNS; avoids recursion through the host resolver. |
| `exposure.tcp_forwards` | Selected VM TCP ports exposed through HAProxy. |
| `exposure.services` | Selected selector-backed Kubernetes TCP Services exposed through generated NodePort Services and HAProxy. |

`./run.sh list-modules` and `python3 scripts/configure.py --list-modules` list the managed modules offline. The Python setup also prompts for module selection. Catalog package discovery is informational: this installer does not claim to install every arbitrary Operator or supply its custom resource configuration. Changing the selected list does not uninstall existing operators or delete disks.

### LAN access, pod workloads and DNS

Example operational settings file (`lan-settings.json`) for the existing test host:

```json
{
  "exposure": {
    "lan_ips": ["10.20.30.40"],
    "allowed_cidrs": ["10.20.30.0/24"],
    "dns_enabled": true,
    "upstream_dns": ["1.1.1.1", "1.0.0.1"],
    "tcp_forwards": [
      {"name": "node1-ssh", "listen_port": 2221, "host": "ocplab-node-1", "port": 22}
    ],
    "services": [
      {"name": "demo", "namespace": "demo-app", "service": "demo-web", "port": 8080, "listen_port": 18080}
    ]
  },
  "waits": {"poll_seconds": 30, "diagnostic_seconds": 120, "api_seconds": 900},
  "timeouts": {"bootstrap_seconds": 14400, "cluster_seconds": 14400}
}
```

The demo Service must already exist; omit the services entry until it does. For a new installation, set exposure in config/lab.json during setup. For an existing locked install:

```bash
python3 scripts/upgrade_config.py config/lab.json --settings lan-settings.json
./run.sh expose
```

The `expose` stage requires completion, creates managed `lab-proxy-NAME` NodePort Services, and reloads HAProxy after syntax validation. It preserves original Services. It does not delete previously generated proxy Services when entries are removed; remove unused ones deliberately with `oc delete service` after confirming no consumers.

Traffic paths:
- API: LAN IP:6443 → HAProxy → node:6443.
- Console/OAuth/HTTP apps: LAN IP:80/443 → HAProxy → OpenShift ingress → Service → pods.
- Additional pod workload: LAN IP:18080 → HAProxy → node:allocated NodePort → selected Service endpoints.
- VM SSH example: LAN IP:2221 → HAProxy → node1:22.

Pod CIDR (`cluster_cidr`), Service CIDR (`service_cidr`) and VM CIDR are distinct, nonoverlapping networks. **HAProxy publishes TCP endpoints; it does not route an entire pod subnet.** No direct route to Pod IPs or ClusterIPs is assumed. Ordinary web workloads should use OpenShift Routes; explicit Service proxies cover additional TCP protocols. UDP publication is not implemented.

Machine-config port 22623 stays on the internal gateway. No general DNAT, forwarding-policy reset or global firewall flush is performed. A dedicated nftables table limits LAN listener sources; firewalld rules are added when active. Other site firewall policies still apply. Removing exposure entries does not remove pre-existing firewalld allowances; review those as part of decommissioning.

LAN clients use the bastion's LAN DNS address (or a router conditional forward for `ocplab.lab.local`). API and wildcard apps resolve to the first configured LAN IP. Internal clients retain gateway answers. The bastion receives managed /etc/hosts entries for API/registry/nodes and split DNS through systemd-resolved or NetworkManager; unmanaged regular resolv.conf is backed up and pointed to libvirt DNS. Managed symlinks without a supported resolver fail with instructions instead of being overwritten. Libvirt uses explicit upstreams to prevent a resolver loop.

Checks:
```bash
getent hosts api.ocplab.lab.local
getent hosts console-openshift-console.apps.ocplab.lab.local
nslookup console-openshift-console.apps.ocplab.lab.local 10.20.30.40
curl -k --resolve api.ocplab.lab.local:6443:10.20.30.40 https://api.ocplab.lab.local:6443/readyz
```

Existing v2 installations retain their network definition and isolation setting. Do not rerun prepare to recreate a live network: v3 adds explicit DNS forwarders to newly generated network definitions and rejects mismatched existing definitions. For an existing network, review its DNS forwarders before changing the bastion resolver. The standalone expose phase does not recreate the libvirt network or change the bastion resolver.

Completion now retries installer wait commands within the configured total budget. Transient API failures in readiness waits are retried, with periodic bounded diagnostics. Disk identity mismatches, foreign resources, malformed configuration, QEMU crashes, and a failed storage smoke pod still stop immediately; waiting longer must not conceal these failures.

## 2. Configuration parameters

All user-specific values live in `config/lab.json`. Secrets are referenced by path. The default example uses a separate `ocplab-auto` network, **not the existing libvirt `default` network**. Network UUIDs are configured explicitly, not discovered or adopted. The original-layout example is a reference for a fresh deployment after retiring the old network; it cannot take over an existing network.

### Identity, inputs and host layout

| Parameter | Default / meaning |
|---|---|
| `work_dir` | `/root/ocp-automated`; state, logs, install assets, manifests and credentials. Preserve throughout the installation. |
| `cluster_name`, `base_domain` | `ocplab`, `lab.local`; form `api.ocplab.lab.local` and `*.apps.ocplab.lab.local`. |
| `release` | Exact OpenShift version, `4.22.18`. |
| `release_digest` | Expected embedded release digest. Must match the selected installer/release. |
| `tools_url` | Red Hat client tools base URL; the version is appended by the downloader. |
| `pull_secret_file` | Path to your downloaded registry authentication JSON, default `/root/ocp/secrets/pull-secret.json`. File must exist and contain nonempty `auths`. |
| `ssh_private_key` | Default `/root/ocp/ssh/id_ed25519`; generated without a passphrase during prepare if absent, otherwise reused. Public key recovered if missing. |
| `disk_dir` | `/var/lib/libvirt/images/ocplab-auto`; QEMU-accessible boot assets and virtual disks. |
| `disk_format` | `raw` by default for OS disks; `qcow2` available. Dedicated storage data disks are always raw. |
| `machine` | QEMU machine type, default `q35`. |
| `manage_host_services` | Starts false; set true to authorize replacing lab HAProxy config and managing nginx, chrony and registry services. |
| `host_faults_remediated` | Defaults true for a clean host. Set false when investigating a known host fault. An acknowledgement, not a hardware test. |
| `allow_memory_overcommit` | True for this constrained lab; four 16 GiB VMs exceed a 62 GiB host before overhead. Bootstrap is retired after handoff. |
| `image_registry_emptydir` | True configures the cluster's internal registry with ephemeral storage. This is separate from the persistent external mirror and HPP guest disks. |
| `ntp_upstreams` | Host chrony upstreams. Nodes use the bridge gateway as NTP server. |

### Network and node addresses

| Parameter | Meaning |
|---|---|
| `network.name`, `.uuid` | New automation-owned libvirt network identity. UUID is fixed by the chosen config; reuse the same config for retries. |
| `network.bridge` | Linux bridge, `virbr-ocp`. |
| `network.cidr`, `.gateway` | `192.168.123.0/24`, `192.168.123.1`. |
| `network.dhcp_start`, `.dhcp_end` | Dynamic range `.100` through `.200`; reserved node addresses must be outside it. |
| `network.isolate_guests` | **False by default** enables NAT. True omits libvirt NAT forwarding. False enables NAT. Does not establish physical air-gap proof or isolate the host itself. |
| `http_port` | Local nginx port, `8080`. Serves boot assets and temporary Ignition. |
| `cluster_cidr`, `host_prefix` | Pod network `10.128.0.0/14`, per-node prefix `23`. |
| `service_cidr` | Service network `172.30.0.0/16`; must not overlap node/pod networks. |
| `bootstrap` and each entry in `nodes` | `name`, `ip`, `mac`, `memory_mib`, `vcpus`, `disk_gib`. Exactly three master/worker nodes. Default bootstrap `.10`, nodes `.11`–`.13`; 16 GiB/4 vCPU each, 100 GiB bootstrap disk and 120 GiB node OS disks. |

Node MACs, names and IPs must be unique. The script refuses existing unmanaged VMs. Do not change network or identity settings mid-installation. Console access from your workstation requires routing to the bridge network plus DNS resolution for API and wildcard apps; the host `/etc/hosts` entries do not configure your workstation.

### Registry, mirror and virtualization

| Parameter | Meaning |
|---|---|
| `registry.hostname`, `.port` | Local TLS mirror endpoint; default `registry.ocplab.lab.local:5000`. |
| `registry.image` | Container registry server image, default `docker.io/library/registry:2`. Prepare pins the pulled local image ID in the service definition. |
| `registry.container`, `.unit` | Podman container and systemd service names. |
| `mirror_parallel_images`, `mirror_parallel_layers` | Default 2 and 3, limiting load on the single NVMe host. |
| `mirror_retries`, `image_timeout` | Default 10 retries and `30m` per image. |
| `virtualization.enabled` | Legacy compatibility field; when `modules.selected` exists, module selection is authoritative. |
| `virtualization.version`, `.channel` | Exact operator version `4.22.12`, channel `stable`. |
| `virtualization.catalog`, `.package` | Source index and `kubevirt-hyperconverged`. |
| `virtualization.namespace`, `.hco_name` | `openshift-cnv`, `kubevirt-hyperconverged`. |
| `virtualization.fix_catalog_permissions` | True rebuilds the mirrored catalog with readable `/configs`, preserving UID 1001, pushes a `-permissions-fixed` tag and updates generated CatalogSource. Applies again after later mirror runs regenerate the original reference. |

The mirror is anonymous TLS on the lab bridge. The pull secret authenticates to upstream registries. Do not paste secrets into JSON fields, shell commands, bug reports or chat. HTTPS certificate checking remains enabled during mirroring.

### Storage (new late-stage automation)

| Parameter | Default / meaning |
|---|---|
| `storage.enabled` | Legacy compatibility field; selected `storage` module enables disks, mounts, HPP and a StorageClass. Requires `virtualization`. |
| `storage.disk_gib` | 80 per node. Sparse raw files; validate physical capacity as they grow. |
| `storage.target` | `vdb`; currently fixed by validation to prevent accidental OS disk selection. |
| `storage.mount_path` | `/var/hpvolumes`; currently fixed by validation and mount-unit name. |
| `storage.pool_name` | `vm-storage`, shared logical pool name across the three local paths. |
| `storage.storage_class` | `hostpath-csi`. |
| `storage.reclaim_policy` | `Retain`; PVC deletion leaves data for deliberate manual cleanup. `Delete` is available if you intentionally want automatic reclamation. |
| `storage.default` | True marks the class as default for general PVCs and virtualization. Refuses a different existing default class. |
| `storage.adopt_existing_disks` | False for new deployments. True allows verified existing, mounted XFS data disks from our manual test; never permits formatting them. |
| `storage.minimum_host_free_gib` | 100 GiB host reserve, in addition to the full nominal size of data disks not yet created. This does not reserve capacity at filesystem level. |
| `storage.timeout_seconds` | 3600 seconds for each HPP rollout/verification/smoke wait; periodic pod/event diagnostics. |
| `storage.smoke_test` | True creates `ocplab-storage-test/storage-check` PVC and pod using the installed HCO image. Leaves evidence in place. |

HPP is node-local, not replicated or shared. Three 80 GiB disks are not a single resilient 240 GiB volume. Requested PVC sizes are not enforced quotas in this setup: our 1 GiB test PVC reported 79 GiB and exposed the full backing filesystem. Monitor actual free space. Do not rely on requested PVC capacities to prevent exhaustion. No automatic live migration or node-failure recovery is promised.

### Timeouts

`timeouts.mirror_seconds=21600`, `vm_install_seconds=1800`, `bootstrap_seconds=14400`, `cluster_seconds=14400`, `operator_seconds=3600`. These are stage/subtask budgets, not guarantees of completion. The Ansible async task has a 24-hour outer ceiling; each phase starts a new task. Increase budgets in your initial config before mutation; arbitrary config changes are deliberately blocked once resources exist.

## 3. Detailed operations guide

### What each stage does

| Stage | Actions and checkpoint |
|---|---|
| `preflight` | Detects supported Linux distribution, checks root, KVM, pull secret, names, CIDRs, nested virtualization, host RAM/free disk and owned VMs. Makes no cluster infrastructure changes. |
| `prepare` | Installs dependencies; creates its own libvirt DNS/DHCP network; configures HAProxy, nginx, local NTP, SSH key, registry CA/TLS service; downloads and verifies tools. |
| `mirror` | Mirrors exact release/operator selection with oc-mirror v2, persistent workspace/cache and retries; writes IDMS, ITMS, catalog and pinned configurations. |
| `assets` | Downloads kernel, initramfs, rootfs and raw installation image from installer stream metadata, verifies SHA-256 and serves locally. Valid cached assets are reused. |
| `ignition` | Creates backed-up install inputs, manifests, schedulable control planes, chrony config and Ignition. A partial existing install directory is not silently replaced. |
| `vms` | Creates OS disks and direct-kernel installer domains; verifies installed filesystem/Ignition offline; preserves assigned UUID on disk-boot transition; checks SSH and preserves ownership state. |
| `complete` | Waits for bootstrap handoff; removes bootstrap from HAProxy; verifies permanent API; shuts down bootstrap gracefully; waits for install completion. Retains bootstrap files for diagnosis. |
| `virtualization` | Checks guest `/dev/kvm`, repairs catalog image permissions, applies mirror resources/catalog, creates subscription, approves only expected CSV InstallPlan, creates HCO and waits for availability. |
| `storage` | Creates dedicated raw disks, persists and hot-attaches `vdb`, checks identity, formats only new empty automation-owned disks, mounts by UUID, creates HPP/default class and performs write test. |
| `validate` | Checks nodes, cluster operators, static Pod manifest parsing, chrony command access, HCO availability and storage mounts/HPP readiness; writes validation.json. |
| `diagnostics` | Saves host memory, kernel, QEMU and IO evidence without deleting or repairing resources. |

Validation is a bounded checklist, not certification: it does not reboot nodes to test persistence, validate every storage node with a guest VM, enforce quotas, benchmark etcd, or prove complete network isolation. A smoke test completed in an earlier run is retained; rerunning storage does not recreate that completed pod automatically.

### Logging and verbosity

Ansible runs with `-vvvv` and displays the phase in the task name. The engine runs unbuffered and logs phase starts, command executable/exit status, cache decisions, downloads, Subscription conditions, CSV progress, storage work and outcomes. Long-running mirror/build/install commands stream output into both their subtask log and the active phase log. This avoids the original silent asynchronous task.

Logs are under `<work_dir>/logs` with mode 0600 and unique timestamps. `active-ansible.path` and `active-stage.path` select the files followed by Screen window 1. The viewer follows changes automatically; it does not start commands or write cluster state. View independently:

```bash
python3 -u scripts/follow_logs.py config/lab.json
```

Verbosity is maximal at the Ansible diagnostic level, but raw command arguments/stdin are intentionally not echoed by the engine: manifests and stdin can contain credentials. Installer lines containing password/token indicators are suppressed. Logs may still contain internal IPs, registry paths and error excerpts; treat them as private. Do not enable shell `set -x` around secret handling.

### Screen, Ctrl+C, interruption and retries

Screen protects against SSH disconnection, not host shutdown. Reattach with `screen -r ocplab-install`. If the session is attached elsewhere, use `screen -d -r ocplab-install` to detach that terminal and reattach here.

Ansible async means Ctrl+C at the Ansible console can leave Python running. Inspect before retrying:

```bash
pgrep -af '[p]ython3 .*scripts/lab.py'
lslocks -o PID,COMMAND,PATH | grep automation.lock
# Use the job ID printed by Ansible:
ansible localhost -i inventory.ini -m ansible.builtin.async_status -a 'jid=YOUR_JOB_ID'
```

A lock conflict now explains this situation. **Never delete automation.lock while a process holds it.** Do not start another run until the job finishes. If explicit cancellation is necessary, inspect the parent and child processes first; abrupt interruption during disk installation is not an automatic safe resume point. The automation refuses ambiguous disk state rather than rerunning the OS installer blindly.

A failed Screen sequence returns to a shell in window 0. After fixing the cause, run remaining stages there, or exit the old session and launch a new named session with explicit phases. Do not rerun the full sequence: `ignition` intentionally refuses an existing consumed/partial installation directory.

### Configuration locks and upgrading

The v1 bug wrote a fingerprint before preflight succeeded. v2 runs preparation preflight before creating the fingerprint and recognizes only the exact old false-to-true host-acknowledgement transition when no resource markers exist. It does not allow arbitrary identity changes.

For an existing installation, `scripts/upgrade_config.py` adds v2 options under a lock and preserves your original settings. Backups are stored under `<work_dir>/backups/automation-upgrade-*`. If interrupted between config and fingerprint writes, the next stage fails closed; inspect those backups rather than deleting locks. The historical `os_variant` and `operator_storage_note` fields may remain in migrated configs; v2 ignores them.

### Host storage safety and restart behavior

Every data disk has a JSON ownership record under `<work_dir>/state/data-disk-NODE`. Existing unmanaged files or a different `vdb` attachment stop the stage. New disks must match the expected byte size, have no partitions/dependent devices, no mount and no filesystem signatures before XFS creation. A partially completed new disk may resume with its existing XFS filesystem; it is not reformatted. After a successful mount, formatting permission is removed from its ownership record.

Persistent mount units are installed at `/etc/systemd/system/var-hpvolumes.mount`, using each disk UUID and ordered before kubelet. They are host-side SSH configuration, not MachineConfigs; keep the generated units and state for node replacement. They do not provide fail-closed scheduling if a future disk is missing: verify mounts before allowing workloads after recovery. A separate MachineConfig-managed hardening rollout is not included because it would reboot the compact control plane.

Sparse allocation avoids upfront writes, but OS images, the external mirror, automatically imported boot sources and guest disks compete on the same host NVMe. A free-space budget is checked; no capacity reservation is made. Monitor both `df -h` on the host and `/var/hpvolumes` on every node. Automatic boot-source imports can start after the default class appears; they are not included in the operator mirror selection.

### Air-gap behavior and signatures

`network.isolate_guests=true` produces an isolated libvirt network. Local DNS, registry, HTTP and NTP remain accessible; the host may retain upstream access. DNS forwarding can still resolve external names. Full air-gap verification requires explicit egress testing and host/network controls. Your test deployment reported `isolation_configured=false`; migration preserves that value.

OS images are downloaded with HTTPS and checked against the installer-provided SHA-256. The `.sig` URL returned 403 in our test. v2 does not request that unavailable signature and retains the existing `coreos.inst.insecure` setting, allowing an absent detached signature. **SHA-256 verification is retained; detached GPG verification is not provided by this lab workflow.** This is independent of registry TLS verification.

Guest OS boot sources require their own mirroring/import plan in a disconnected environment. Successfully importing Fedora/CentOS online in the test does not prove offline readiness.

### Catalog and operator troubleshooting

The observed index image used UID 1001 but `/configs` was root-owned mode 0700. CatalogSource security changes were not the solution: the pod already had `anyuid`. v2 derives a local image with `chmod -R a+rX /configs` and restores USER 1001. It pushes a separate tag without overwriting the original mirror tag and writes the corrected reference into the generated CatalogSource. Upstream regeneration via `mirror` is handled by the next `virtualization` stage. It does not disable AppArmor or SELinux.

Check:

```bash
export KUBECONFIG=/root/ocp-automated/install/auth/kubeconfig
oc -n openshift-marketplace get pods,catalogsources
oc -n openshift-cnv get subscriptions,installplans,csv
oc -n openshift-cnv get hyperconverged kubevirt-hyperconverged -o yaml
```

If a catalog fails, read its previous container logs before changing security settings. If an InstallPlan includes unexpected dependencies or a different version, the automation stops for review. It never blanket-approves every pending InstallPlan or CSR.

### Storage diagnostics and cleanup

```bash
oc get storageclass,pv
oc get storageprofile hostpath-csi -o yaml
oc -n openshift-cnv get daemonset hostpath-provisioner-csi
oc -n ocplab-storage-test get pvc,pod -o wide
oc -n ocplab-storage-test logs storage-check
```

Expected: HPP desired/current/ready 3, CSI pods 4/4, recognized RWO Filesystem profile, test PVC Bound, test pod Completed and `ocplab-storage-ok`. Provisioning waits for a consumer with `WaitForFirstConsumer`; an isolated pending PVC is not necessarily a fault. A Retain volume remains after PVC deletion. No automatic destructive cleanup, filesystem repair, guest replacement or etcd membership removal is included.

## 4. Tested fixes and remaining scope

The original lab reached successful OpenShift/Virtualization validation and a successful HPP write test. The v2 baseline integrated those manual fixes and automates the storage work. v3 extends hardware assessment, distribution adapters, module selection, waits and exposure. **The v3 multi-distribution installation has not been exercised end-to-end on physical hosts.** GitHub Actions runs offline tests and syntax checks; it does not certify a live deployment. See `docs/TEST_RESULTS.txt` for actual checks, and `docs/LESSONS_LEARNED.md` for incident context.

The earlier QEMU double-free and unrelated guest-file corruption were not root-caused. Raw disks are a deliberate lab default, not a claim that a host/QEMU/hardware defect is fixed. Stop on fresh corruption evidence.

References: https://coreos.github.io/coreos-installer/cmd/install/ ; https://libvirt.org/formatdomain.html ; https://docs.redhat.com/en/documentation/openshift_container_platform/4.21/html/virtualization/storage . Actual CRDs are checked with server-side dry-run before storage objects are applied.
