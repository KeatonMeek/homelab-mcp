# Homelab MCP

Bring your homelab into your AI assistant through the Model Context Protocol (MCP).

Homelab MCP gives an OAuth-capable MCP client access to server health snapshots and, when enabled, shell commands, text-file operations, and background jobs. Use it to understand your server's current state, investigate problems, and carry out maintenance from the same conversation.

You do not need a dedicated physical server. The service can run in a Linux environment on a home PC, VM, or VPS, and authenticates a single owner through GitHub OAuth. It makes no model API calls and requires no model API key of its own.

## Why use it?

- **Get a useful health overview.** Check system load, memory, storage, service errors, and optional Docker inventory. Each snapshot includes its collection time and freshness.
- **Investigate with context.** Bring server information into your assistant conversation before deciding what to change.
- **Enable maintenance when you need it.** Add commands, file operations, and asynchronous jobs through an optional local broker.
- **Keep deployment settings private.** Store your domain, credentials, configuration, and runtime state separately from the public source.
- **Choose your client and hosting setup.** Use an OAuth-capable remote MCP client with your own HTTPS reverse proxy or tunnel. Client authentication requirements are covered in the [setup guide](docs/setup.md).

## Where can I run it?

The current implementation uses Linux interfaces. The machine hosting that Linux environment does not have to be a dedicated Linux server, and your assistant can run on a different device.

| Your setup | Deployment path | Managed environment |
| --- | --- | --- |
| Linux PC, home server, or VPS | Native Python setup below | That Linux environment |
| Linux virtual machine on another OS | Install inside the VM | The Linux guest |
| Windows PC with WSL2 | Try the Linux setup inside a WSL2 distribution; project validation is still pending | The WSL Linux environment |
| Docker Engine on Linux | Build the supplied images and configure private proxy/socket routing | Resources visible to the configured containers and broker |
| Windows with Docker Desktop's Linux backend | Possible hosting route; complete project deployment remains untested | Linux containers/VM, not native Windows administration |
| Native Windows Python or PowerShell | No native port is currently provided | Not applicable |

Windows users can use an MCP client to manage a separate Linux installation today. For hosting on the Windows machine itself, see the [WSL2 trial guide and platform details](docs/platforms.md), which distinguish upstream platform capabilities from project-tested behavior.

## How it works

```text
MCP client → HTTPS proxy or tunnel → Homelab MCP frontend
                                      ├─ Health snapshots ← scheduled host collector
                                      └─ Private Unix socket → optional execution broker
```

The frontend listens on `127.0.0.1:8080`. Your proxy runs in the same network namespace and exposes the `/mcp` endpoint over HTTPS. GitHub OAuth identifies the owner, and the frontend checks that identity for every tool request.

Only `probe` and `health` are enabled by default. Optional command and file tools run with the broker account's operating-system permissions. Review the [execution guide](docs/execution.md) and [security model](SECURITY.md) before enabling them.

## Quickstart

### 1. Prepare your environment

You will need:

- A Linux runtime with Python 3.12, venv support, Bash, and Git. This can be a physical machine or Linux guest. For a Windows-hosted trial, start with [WSL2 preparation](docs/platforms.md#trying-it-from-windows-with-wsl2).
- A domain with HTTPS routing through a reverse proxy or tunnel on the same host/network namespace as the frontend.
- A GitHub OAuth App and your numeric GitHub account ID.
- A remote MCP client that supports OAuth and an exact HTTPS callback URI.

For an origin such as `https://mcp.example.com`, set the GitHub OAuth App callback to `https://mcp.example.com/auth/callback`. Separately copy the exact callback URI supplied by your MCP client. Follow [Authentication and HTTPS](docs/setup.md#1-authentication-and-https) for the account and proxy setup.

Docker is optional. Health collection uses Linux system information; Docker and journal details depend on the utilities and permissions available in that environment. Keep the machine or guest running while you want remote access.

### 2. Install the project

Run these commands in the chosen Linux environment as the account that will run the frontend. On WSL2, use the distribution's terminal and Linux home directory. Check `python3.12 --version` first; install Python 3.12 and its venv package through your distribution if needed.

```sh
git clone https://github.com/KeatonMeek/homelab-mcp.git
cd homelab-mcp
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip check
```

### 3. Create your private configuration

Run the wizard as the account that will run the frontend. For ChatGPT:

```sh
.venv/bin/python scripts/create_config.py \
  --directory "$HOME/.config/homelab-mcp" \
  --client chatgpt
```

For a client using dynamic client registration, omit `--client chatgpt`. The ChatGPT option configures its exact public metadata and signing-key endpoints; client availability and setup depend on your account and client.

Have these values ready before running the wizard:

| Value | Where it comes from |
| --- | --- |
| Public origin, such as `https://mcp.example.com` | Your domain and HTTPS proxy/tunnel configuration |
| Numeric owner ID | Your GitHub account ID, not your username |
| OAuth App client ID and client secret | Your GitHub OAuth App settings |
| Exact client callback | The connection setup in your MCP client |

The wizard asks for your HTTPS origin, owner ID, OAuth App credentials, and client callback. It hides the client secret while you type, generates signing and encryption keys locally, and saves configuration outside the checkout. See the [configuration reference](docs/setup.md#3-configuration-reference) for all settings.

### 4. Collect a snapshot and start the frontend

```sh
.venv/bin/python host/collect_health.py \
  --output "$HOME/.config/homelab-mcp/health/health.json"

HOMELAB_CONFIG_FILE="$HOME/.config/homelab-mcp/settings.json" \
  .venv/bin/python -m app.server
```

To include Docker inventory, add `--docker` to the collector command. To report additional storage paths, use repeatable `--mount` options, such as `--mount / --mount /mnt/data`. Collection uses the account's existing permissions.

Configure your proxy to route the **entire HTTPS hostname**, including OAuth and discovery paths, to `http://127.0.0.1:8080`, preserving the public `Host` header. [Caddy](deploy/Caddyfile.example) and [cloudflared](deploy/cloudflared.example.yml) examples are included.

Before registering the client, check that `https://mcp.example.com/.well-known/oauth-authorization-server` returns discovery metadata. A local `Host: localhost` request is not a valid public-host test. See [Routing checks](docs/setup.md#routing-checks) for exact diagnostic commands.

### 5. Connect your client

Add `https://mcp.example.com/mcp` to your client, replacing the example hostname with your own. Sign in with the configured GitHub account and approve the `read:user` scope. Try `probe`, then ask for a health summary.

Confirm the initial tool list contains `probe` and `health`, with execution tools absent. Ask for the snapshot timestamp as well as its contents; a successful connection alone does not mean the collector is being refreshed.

### 6. Keep it running and choose optional features

The commands above run the frontend in the foreground and collect one snapshot. For ongoing use, configure a service and refresh health approximately every minute using the [systemd setup](docs/setup.md#4-persistent-systemd-installation) or your existing scheduler.

For command and file tools, follow [same-user execution setup](docs/execution.md#same-user-mode-recommended-first). Enable execution in both the private frontend settings and the broker environment, start the broker, restart the frontend, and refresh the client's tools. Start with a harmless `id -u; pwd` request and a disposable file round trip. The [first-use checklist](docs/setup.md#6-first-execution-checks) walks through commands and jobs.

## Deployment examples

- **Home PC or small server:** run the frontend and collector directly in Linux, with Caddy or cloudflared in the same namespace. Add a service/timer after the initial connection works.
- **Linux VM or VPS:** use the same setup inside the guest. Its health and commands describe that guest; the assistant does not automatically administer the hypervisor or other machines.
- **Windows workstation:** use a remote Linux service from your client, or try the documented WSL2 route. Keep Linux source, configuration, collector, broker, and proxy together while validating the setup.
- **Container-based installation:** build the [frontend image](deploy/Dockerfile), then configure private mounts and a proxy that can reach its loopback listener. The [platform guide](docs/platforms.md#docker-desktop-on-windows) explains why Docker Desktop and a published port alone are not a turnkey Windows installation.

## Example requests

These are illustrative prompts for your assistant. Available actions depend on your enabled tools, installed software, and account permissions.

| Goal | Example prompt | Requires |
| --- | --- | --- |
| Health overview | “Summarize CPU load, memory, and disk usage. How recent is the snapshot?” | Default health tools |
| Docker inventory | “List my containers and point out any that are stopped or unhealthy.” | Health collector with `--docker` |
| Troubleshooting | “Investigate why this service is restarting. Start with its status and configuration, and explain what you find.” | Optional execution for inspection beyond snapshots |
| Service setup | “Help me plan a new Docker Compose service. Show the configuration and commands for review before applying them.” | Optional execution to write files or apply changes |
| Configuration review | “Read this non-secret configuration file and explain the setting I should change before we edit it.” | Optional execution |
| Background work | “Run this maintenance command as a background job, then check its status and output.” | Optional execution |

Use prompts that identify the intended service and scope. Keep credentials out of commands and shared results. Your client's review workflow is separate from the server's authorization checks; see [Security](SECURITY.md).

## Available tools

| Tools | Purpose | Availability |
| --- | --- | --- |
| `probe` | Confirm connectivity with a literal echo, timestamp, and nonce | Default |
| `health` | Read system, Docker, storage, log-summary, and network snapshots | Default |
| `command_run`, `command_start` | Run Bash commands synchronously or as background jobs | Opt-in |
| `job_status`, `job_output`, `job_cancel` | Inspect or cancel a running job | Opt-in |
| `file_read`, `file_write`, `file_move` | Read, write, and move text files, with backups for replacements | Opt-in |

To enable commands and file operations, follow the [optional execution guide](docs/execution.md). It covers broker startup, account permissions, and tool limits.

## Troubleshooting

| Symptom | Start here |
| --- | --- |
| Cannot connect or discovery fails | Check HTTPS, the entire-hostname route, public Host, and proxy network namespace |
| GitHub login or callback fails | Check the two distinct callback URLs and the configured numeric owner |
| Health is stale or missing sections | Check the collector schedule, paths, installed utilities, and existing account permissions |
| Command tools are missing | Check both execution flags, broker startup, then refresh client tool discovery |
| Windows/WSL endpoint stops after sleep or restart | Check the Linux guest, proxy, and service lifecycle independently |

See [Recovery and maintenance](docs/recovery.md) and [platform-specific checks](docs/platforms.md) for the next steps.

## Documentation

- [Platforms, WSL2, and Docker deployment](docs/platforms.md)
- [Setup and configuration](docs/setup.md)
- [Optional execution](docs/execution.md)
- [Security and permissions](SECURITY.md)
- [Recovery and maintenance](docs/recovery.md)
- [Testing and deployment checks](docs/validation.md)
- [Contributing](CONTRIBUTING.md)

## Contribute, review, or fork

Reviews, bug reports, documentation improvements, and pull requests are welcome. Fork the repository to adapt it to your own homelab, and share improvements that could help other operators.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development commands and review guidance. Keep reports free of credentials and private server data; use the [security reporting guidance](SECURITY.md#reporting) for sensitive findings.

## License

Homelab MCP is licensed under the [MIT License](LICENSE). You can use, modify, and distribute it under those terms. Third-party dependencies retain their own licenses; see [Licensing](docs/licensing.md).
