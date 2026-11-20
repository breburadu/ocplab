# Lessons from the October 20 lab

1. **Preserve intent:** this is classic UPI with local HTTP boot/Ignition and a mirror, not an implicit switch to Agent ISO installation. Agent can also be disconnected, but it is a different provisioning flow.
2. **Pin artifacts:** OpenShift 4.22.18; the installer stream reported 9.8.20260715-1 live boot assets; installed nodes reported 9.8.20261006-0. Derive boot assets from the installed tool, not assumptions based on unrelated release metadata.
3. **Mirror v2 explicitly:** `--v2` is mandatory for this build. Select exact release/Operator versions. A dry-run is discovery, not transfer/integrity proof. Successful observed totals were 192 release and 71 Operator images; don't hard-code counts as universal assertions.
4. **No registry password requested:** local TLS registry is anonymous; Red Hat pull secret still needed for upstream pulls. The installer warning about the local registry missing from pullSecret is expected.
5. **DNS:** API/API-int point to HAProxy, not node 1. Libvirt DNS host records cannot be modified by the attempted net-update operation; use add/delete or owned full XML. `.local` host NSS resolution and VM DNS are different; wildcard routes require actual DNS.
6. **Separate ports:** nginx 8080; HAProxy 6443/22623/80/443; registry 5000. Retain read-only bind mounts and no traversal access to `/root`.
7. **HAProxy:** match full sections, not a substring in `default_backend`. Use a complete generated file and validate before reload. Bootstrap belongs only in API/MCS backends.
8. **Provisioning lifecycle:** successful live installation can end with the VM shut off. Switch persistent XML to disk boot and on_reboot=restart, verify installed Ignition, then start. Do not reinstall repeatedly on each reboot. Persist serial-console arguments; run guest service commands via SSH, not on the bastion.
9. **Three nodes must overlap:** bootstrap cannot complete before masters exist. All three are schedulable and carry workloads. Memory overcommit was explicitly accepted for this lab; initial low RSS does not establish sufficient worst-case RAM.
10. **Time:** local chrony for nodes and bootstrap, with host local stratum fallback during isolation. Local fallback keeps common time but is not proof of accurate UTC.
11. **Errors need chronology:** initial missing CRDs/namespaces resolved on retry. CSRs were automatically approved/issued. Avoid blind approvals or premature node restarts. Track installer status, not just Ready nodes.
12. **Actual failure:** QEMU node 3 crashed with `double free or corruption (out)` at 09:09:16 UTC. Later QCOW2 refcount repairs were observed. Node 1's static manifest was truncated; another revision file contained an unrelated OLM catalog record. Node 3's containers/storage images.json was malformed. Root cause was not established. Do not label this merely resource pressure or claim raw disks solve it.
13. **Recovery limits:** etcd had four voters, with bootstrap/node1/node2 healthy and node3 unavailable. Recreating node1 then would lose quorum. There is no automatic destructive recovery in this project.
14. **Evidence:** API direct, HAProxy and service probes were fast at some moments while controllers timed out at others. That does not rule out intermittent I/O/etcd or pod-path issues. Host I/O pressure was high; memory pressure was low in later samples.
15. **File operations:** built-in open supports opener; Path.open does not. Atomic generation and validation reduce automation mistakes but cannot protect against all host corruption.
16. **Completion:** only after base install succeeds should Virtualization install and readiness checks run. Persistent VM storage and a guest smoke test remain separate acceptance items.

17. **Clean rebuild succeeded:** the subsequent clean-host test completed OpenShift 4.22.18 and Virtualization 4.22.12. This does not establish the original crash root cause.
18. **Catalog permissions:** UID 1001 could not read root-owned /configs mode 0700. A derived image with a+rX on /configs resolved the failure while preserving UID 1001.
19. **Async interruption:** Ctrl+C detached the Ansible caller but left virtualization running; preserve process locks and monitor the existing job.
20. **Storage:** dedicated 80 GiB raw vdb disks, UUID-based XFS mounts and HPP reached 3/3 readiness. A write smoke test succeeded. Requested 1 GiB PVC reported 79 GiB; requested size is not an enforced quota.
