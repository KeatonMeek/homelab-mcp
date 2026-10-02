# Platforms and deployment options

Homelab MCP needs a Linux runtime, not a dedicated physical server. That runtime can be a home PC, virtual machine, VPS, or another machine you already use. Your MCP client can run elsewhere, including on Windows, as long as it can connect to the service's HTTPS endpoint.

## Compatibility at a glance

| Environment running Homelab MCP | Current status | What it observes or manages |
| --- | --- | --- |
| Linux machine with Python 3.12 | Tested project runtime | That Linux environment, under the configured account |
| Linux VM or VPS | Fits the Linux deployment model; verify the guest's dependencies and routing | The guest, not automatically its hypervisor or physical host |
| Windows with a WSL2 Linux distribution | Candidate route based on WSL2's Linux environment; not yet tested by this project | The distribution's Linux view and accessible resources |
| Docker Engine on Linux | Images build and Linux container execution has been tested; private routing and mounts require configuration | Container-visible resources, the selected Docker daemon, and any explicitly configured broker target |
| Docker Desktop on Windows with a Linux backend | Linux image hosting is possible in principle; the full Homelab MCP deployment is untested | Linux container/VM resources, not native Windows administration |
| Native Windows Python or PowerShell | Not implemented | No native Windows collector, broker, or service setup is provided |

The collector reports the environment where it runs. A broker in local mode executes there as its OS account. Docker inventory refers to the daemon reached by the collector's Docker CLI; it can differ from the collector's own environment. These tools do not automatically connect to other machines over SSH.

## Why a Linux runtime is needed

These are implementation requirements, not hardware requirements:

- [Configuration](../app/config.py) checks Unix ownership, file modes, and directory permissions.
- The [broker](../app/execution_broker.py) uses Unix sockets and Linux `SO_PEERCRED` to verify its caller.
- The [command worker](../app/host_actions.py) invokes `/bin/bash` and uses Unix account information. There is no PowerShell command adapter.
- The [collector](../host/collect_health.py) reads `/proc` and Linux filesystem/network information. Service and journal sections use systemd utilities when available.
- Optional host namespace entry uses Linux `nsenter`. The reference persistent services use systemd.

Some optional health sections can report unavailable when utilities or permissions are missing. That does not make the complete application a native Windows port.

## Trying it from Windows with WSL2

**This is a proposed setup path, not a project-verified Windows installation.** Start with health-only access and complete the checks below before relying on it.

### 1. Install a Linux distribution

Follow Microsoft's [WSL installation guide](https://learn.microsoft.com/en-us/windows/wsl/install). In an administrator PowerShell window, the usual starting point is:

```powershell
wsl --install
```

Restart Windows if prompted, finish the distribution's Linux user setup, and check its version:

```powershell
wsl --list --verbose
```

Use a distribution listed as version `2`. If you need a particular distribution or are upgrading an existing installation, follow Microsoft's instructions instead of assuming the default matches this project's Python requirement.

### 2. Work inside the Linux environment

Open the distribution's Linux terminal. Install Python 3.12, venv support, Bash, Git, and your chosen proxy using that distribution's package instructions. Run the [project installation steps](../README.md#2-install-the-project) there, not in native PowerShell.

Keep the checkout under a Linux home directory and private configuration under its Linux `$HOME/.config/homelab-mcp`, rather than `/mnt/c`. Microsoft recommends the [Linux filesystem for Linux command-line work](https://learn.microsoft.com/en-us/windows/wsl/filesystems); the project's Unix ownership checks and socket files also need suitable filesystem behavior.

WSL can expose mounted Windows files and interoperability features. Treat those as resources available to the Linux account, not as a tested Windows-management feature or an isolation guarantee. A health snapshot describes the Linux environment, not Windows Task Manager, Windows services, or the Event Log.

### 3. Keep the frontend and proxy together

For the initial trial, run the HTTPS proxy or tunnel inside the same WSL distribution and network namespace as the frontend. Route the whole hostname to `127.0.0.1:8080` and preserve its public Host header.

Microsoft documents [WSL networking and localhost forwarding](https://learn.microsoft.com/en-us/windows/wsl/networking), including differences between NAT and mirrored networking. Windows-browser access to a WSL port does not prove that a Windows-side proxy will appear as a loopback peer to this application's guard. Do not relax the guard or expose the Python listener to work around that distinction.

### 4. Verify operation and availability

Run the [local suite and live checks](validation.md), including real Unix-socket transport, owner OAuth, health freshness, and optional harmless command/file/job checks. Test startup after stopping and restarting WSL and Windows, plus behavior across sleep and network changes.

If using the supplied service units, first check [systemd support in your WSL distribution](https://learn.microsoft.com/en-us/windows/wsl/systemd). Systemd configuration alone is not evidence that your endpoint will recover after Windows starts or sleeps. Configure and test that lifecycle separately.

## Docker Desktop on Windows

Docker documents a [WSL2 backend for Linux containers](https://docs.docker.com/desktop/features/wsl/). Its integration can make a Docker daemon available from a WSL distribution. Check the selected daemon with `docker context show` and `docker info`; optional Homelab MCP Docker inventory will reflect that daemon. The collector currently invokes `/usr/bin/docker`, so verify that path inside its environment as well.

The supplied image listens on container loopback. A published port alone does not make it a complete deployment. A proxy in another container has a separate loopback interface unless you deliberately share the network namespace. Review [Docker Desktop networking](https://docs.docker.com/desktop/features/networking/) and design the private proxy/socket/mount arrangement before running the service.

A Linux broker inside Docker Desktop is not a Windows service manager. Privileged Linux namespace entry is not a route to native Windows host control, and this project has not validated that broker mode on Docker Desktop. For a first Windows-hosted trial, the WSL distribution setup above keeps the Linux processes and their paths easier to inspect.

## What remains to be tested on Windows-hosted Linux

The project has not yet completed an end-to-end WSL2 or Docker Desktop validation. Useful compatibility reports should identify the Windows/WSL/distribution or Docker Desktop versions and cover:

- Python installation, private filesystem permissions, and all tests without a Unix-socket skip.
- Proxy peer/Host behavior, HTTPS discovery, owner login, and client reconnection.
- Which health sections and Docker daemon are visible.
- Same-user command/file/job behavior using disposable fixtures.
- Restart, sleep, startup, and saved-authentication recovery.

Share a sanitized report through [Contributing](../CONTRIBUTING.md). Keep credentials, private hostnames, and operational data out of public reports.
