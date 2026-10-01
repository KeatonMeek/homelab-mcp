# Optional command and file execution

Read [SECURITY.md](../SECURITY.md) before enabling this. There is no command allowlist or enforced human-approval step.

## Same-user mode (recommended first)

1. Choose the OS account and the data it may access. No sudo, Docker group, host socket mounts or extra privileges are required for basic commands.
2. Create a mode-0700 private runtime directory owned by that account. Configure the same absolute socket path in the frontend JSON and broker environment. The socket is mode 0600 and peer UID must match `HOMELAB_ALLOWED_UID` (defaults to the broker UID).
3. Set `HOMELAB_ENABLE_EXECUTION` to `true` separately for the frontend and broker. The broker reads its own environment, not the frontend JSON. This separation is deliberate.
4. Set `HOMELAB_BROKER_MODE=local`, leave root disabled and start `python -m app.execution_broker` from the installed checkout/venv. Or use the optional systemd broker unit plus an owner-only `/etc/homelab-mcp/broker.env` based on the example.
5. Restart the frontend after its configuration change. Verify a harmless `id -u` command and temporary-file round trip. Never test with production secrets or destructive commands.

For the local-user README setup, a foreground broker example is:

```sh
HOMELAB_ENABLE_EXECUTION=true \
HOMELAB_BROKER_SOCKET="$HOME/.config/homelab-mcp/run/broker.sock" \
HOMELAB_AUDIT_PATH="$HOME/.config/homelab-mcp/audit/audit.jsonl" \
.venv/bin/python -m app.execution_broker
```

The wizard already created those private directories. Separately edit the private frontend JSON's execution flag; do not edit the tracked example. With systemd, use `/run/homelab-mcp/broker.sock` consistently instead. The reference broker unit intentionally does not impose an artificial path sandbox; ordinary OS permissions determine command access.

## Root on the host (advanced)

A native root broker can use `HOMELAB_BROKER_MODE=local` with `HOMELAB_ALLOW_ROOT=true`. Run only the broker as root, never the public frontend. Configure `HOMELAB_ALLOWED_UID` to the frontend account's actual numeric UID. Its socket directory must be owned by that frontend UID, mode 0700. Keep audit records in a separate root-owned mode-0700 directory.

This grants the frontend account and its owner session access to a root command channel. Root can modify the OAuth files, service, other accounts and network. The socket is not a safe privilege boundary against a compromised frontend.

## Privileged container compatibility (advanced)

The optional `deploy/Dockerfile.broker` retains the namespace-entry architecture for operators who deliberately need it. Requirements:

- Linux Docker host; broker container UID 0, `--privileged`, `--pid=host`
- `--network=none`, no published ports, read-only image filesystem
- Only the private socket directory and root-owned audit directory mounted writable
- `HOMELAB_ENABLE_EXECUTION=true`, `HOMELAB_ALLOW_ROOT=true`, `HOMELAB_BROKER_MODE=host-root`
- `HOMELAB_ALLOWED_UID` set to the frontend's host UID, correct private-directory ownership
- `/usr/bin/nsenter` inside the broker image; `/usr/bin/python3` and `/bin/bash` on the host

No runnable privileged Compose stack is enabled by default. Build the image and create a private deployment manifest only after reviewing the host-specific mounts and permissions. Container root enters PID 1's host mount/root/network/IPC/UTS/PID namespaces. The broker's own transport has no TCP listener, but spawned commands have the host's networking and root authority. This is not container isolation from the host.

## Tool limits

Commands: 1–32,768 characters, absolute cwd, 1–3,600 seconds, 1–128 KiB raw output. Files: absolute paths, reads up to 64 KiB, writes up to 128 KiB encoded UTF-8. New file mode defaults to 0600; existing basic ownership/mode are preserved. Writes create adjacent private backups. Moves require explicit overwrite of existing regular-file targets; directory overwrite is refused. Job state is volatile across broker restarts.

Turn execution off by disabling its flag in the frontend and stopping the broker. Revoke compromised sessions as appropriate. Disabling a flag does not undo actions or stop already detached processes.
