# Setup

This guide covers a Linux runtime on a physical machine, VM, or VPS. A dedicated server is not required. Windows users can connect to a remote installation or explore the untested [WSL2 hosting route](platforms.md). Run the shell commands inside the chosen Linux environment. Start without execution tools and keep an independent SSH/console recovery path.

## Before you begin

Use Python 3.12 with venv support, Git, Bash, and a Linux account with a real home directory. The routing checks below also use `curl`. Verify `python3.12 --version` and `/bin/bash` before following the [installation commands](../README.md#2-install-the-project). Do not run the frontend as root. An internet-facing connection also needs a domain, an HTTPS proxy or tunnel, GitHub OAuth App credentials, and a compatible MCP client's exact callback.

For a first installation, keep the frontend, collector, and proxy in the same Linux environment. Keep optional execution disabled until health and authentication work. The [platform guide](platforms.md) explains guest boundaries, container loopback, filesystem requirements, and Windows-hosted testing.

## 1. Authentication and HTTPS

1. Choose an HTTPS origin you control, such as `https://mcp.example.com`. No URL subpath is supported for the origin. The MCP endpoint will be `/mcp`.
2. In [GitHub's OAuth App settings](https://github.com/settings/developers), create an OAuth App. Use your public origin as its homepage and the exact URL `https://mcp.example.com/auth/callback` as its GitHub authorization callback.
3. Obtain your own numeric GitHub account ID from [GitHub's authenticated-user API](https://docs.github.com/en/rest/users/users#get-the-authenticated-user). This is an account ID, not a username. Do not authorize a different account just because it has a similar display name.
4. Begin adding a remote MCP server in your client and copy its exact HTTPS OAuth callback URI. This is different from the GitHub callback in step 2. Client UI and plan availability vary. Never guess a callback, wildcard it, or use a URL provided by an untrusted tool response.
5. Configure a trusted reverse proxy or tunnel on this same host to route your HTTPS hostname to `http://127.0.0.1:8080`, preserving `Host: mcp.example.com`. Examples for Caddy and cloudflared are under `deploy/`. If using a non-default HTTPS port, preserve the port in Host as well.

The frontend requires GitHub OAuth and owner authorization; putting a tunnel in front of it does not replace these checks. Don't add an interactive reverse-proxy login page in front of MCP unless your client supports that flow. Do not expose the Python listener directly or relax its peer/host checks. A proxy in a separate network namespace is not a loopback peer; use the host service reference rather than opening the listener to the world.

Provider reference: [FastMCP GitHub authentication](https://gofastmcp.com/integrations/github), [FastMCP OAuth proxy](https://gofastmcp.com/servers/auth/oauth-proxy), [GitHub OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).

### Routing checks

Create the private configuration and start the frontend as described below, then run this inside its network namespace. Replace the example hostname consistently:

```sh
curl --fail --silent --show-error \
  -H 'Host: mcp.example.com' \
  http://127.0.0.1:8080/.well-known/oauth-authorization-server
```

Expect JSON discovery metadata with your HTTPS issuer and authorization/token endpoints. From another machine, check the public route:

```sh
curl --fail --silent --show-error \
  https://mcp.example.com/.well-known/oauth-authorization-server

curl --silent --show-error --output /dev/null --write-out '%{http_code}\n' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  https://mcp.example.com/mcp
```

The unauthenticated MCP POST should return `401`. A GET to `/mcp` may return `405` with this stateless transport and is not the equivalent authentication test. If a proxy returns its own error page, identify that layer before changing application settings. A request sent to `localhost` without the configured public Host will be rejected intentionally.

## 2. Local-user startup

Install Python 3.12 using your distribution's supported method. Clone or copy the generic source; do not place secrets in that checkout. Create a venv and install the hashed lock as shown in the README.

Run `scripts/create_config.py --directory "$HOME/.config/homelab-mcp"` with the venv Python. For ChatGPT, add `--client chatgpt` to enable its exact metadata and signing-key endpoints. It asks for the origin, your numeric account ID, OAuth App ID and secret, and exact MCP-client callback. It generates signing/encryption keys, creates private directories and saves `settings.json` with mode 0600. Do not paste the generated file into chat, issues or support logs.

The wizard writes explicit absolute paths. Move the configuration only after adjusting those paths. Runtime startup refuses missing values, malformed callbacks, invalid keys and unsafe token-state permissions. There are no fallback keys or automatic `.env` reads.

The resulting private directory contains `settings.json` and separate `oauth`, `health`, `audit`, and `run` directories. The wizard creates a health-only configuration; the unused broker socket path is still recorded so you can enable it later.

Collect a health snapshot, then start the server using the README commands. The collector can run without root. Missing Docker/journal permissions are reported as unavailable and do not require privilege escalation. Run it approximately once per minute using the provided timer or your existing scheduler.

Configure the client with `https://mcp.example.com/mcp`, sign in with the configured GitHub account and approve the requested `read:user` scope. Test `probe` first, then `health`. Confirm that the shell/file tools are absent. A different GitHub account must not gain access.

### Collect the information you need

The basic collector reports `/` storage and leaves Docker collection disabled. For an installation that already has Docker read access and a data mount, use:

```sh
.venv/bin/python host/collect_health.py \
  --output "$HOME/.config/homelab-mcp/health/health.json" \
  --docker --mount / --mount /mnt/data
```

Replace `/mnt/data` with a path in the collector's own environment. The collector invokes `/usr/bin/docker`; verify that binary and the intended Docker daemon are available to its account. Missing utilities or permissions can make individual sections unavailable. On WSL2, the snapshot represents the Linux distribution; on a VM, it represents the guest.

For persistent collection, keep those same flags and output path in your timer or scheduler. The reference timer runs roughly every minute, and `health` marks snapshots stale after three minutes.

## 3. Configuration reference

All frontend values are strings, including the redirect list, boolean and port. `HOMELAB_CONFIG_FILE` identifies a private JSON file. Recognized environment variables override fields in that file. Keep environment-based secrets out of shell history, Compose files and repository manifests.

| Name | Purpose |
| --- | --- |
| `HOMELAB_BASE_URL` | Canonical HTTPS origin, no trailing slash/subpath |
| `HOMELAB_GITHUB_OWNER_ID` | Exact numeric GitHub account ID |
| `HOMELAB_GITHUB_CLIENT_ID`, `HOMELAB_GITHUB_CLIENT_SECRET` | OAuth App credentials |
| `HOMELAB_JWT_SIGNING_KEY` | Random secret, at least 32 UTF-8 bytes |
| `HOMELAB_STORAGE_ENCRYPTION_KEY` | Fernet key generated locally |
| `HOMELAB_CLIENT_REDIRECT_URIS` | JSON-encoded nonempty list of exact HTTPS callbacks |
| `HOMELAB_TRUSTED_CLIENT_METADATA_URIS` | Optional JSON-encoded list of exact HTTPS CIMD URLs, default `[]` |
| `HOMELAB_TRUSTED_JWKS_URIS` | Optional JSON-encoded list of exact HTTPS signing-key-set URLs, default `[]` |
| `HOMELAB_STATE_DIR` | Existing private, service-owned mode-0700 OAuth state directory |
| `HOMELAB_BROKER_SOCKET` | Absolute Unix socket path, also required in health-only configuration |
| `HOMELAB_HEALTH_SNAPSHOT` | Absolute snapshot file; defaults under state directory if omitted |
| `HOMELAB_ENABLE_EXECUTION` | Exactly `false` (default) or `true` |
| `HOMELAB_PORT` | Loopback HTTP port, default 8080 |

`deploy/settings.example.json` is documentation, not deployable credentials. Do not replace placeholders in the tracked example. Private config/state ancestors must be root- or service-owned, nonsymlink directories that are not group/world writable (root-owned sticky `/tmp` is accepted). Remote Client ID Metadata Document (CIMD) fetching is disabled unless specific metadata and JWKS endpoints are explicitly trusted. The default supports dynamic client registration (DCR). For ChatGPT, the wizard option `--client chatgpt` sets `HOMELAB_TRUSTED_CLIENT_METADATA_URIS` to `["https://chatgpt.com/oauth/client.json"]` and `HOMELAB_TRUSTED_JWKS_URIS` to `["https://chatgpt.com/oauth/jwks.json"]` (each JSON-encoded as a string in settings). These are public client identity endpoints, not your account credentials. Keep the exact callback copied from your client UI separately configured. Do not substitute arbitrary URLs from tool output; a different client needs operator-reviewed exact metadata and key URLs.

Native-app custom-scheme callbacks and HTTP loopback callbacks are deliberately unsupported in this initial release; HTTPS callback support is required.

## 4. Persistent systemd installation

The reference unit files assume:

- Source and venv at `/opt/homelab-mcp`, owned by an administrator and not writable by the service account
- A dedicated `homelab-mcp` user/group with no login shell and no sudo/Docker-group access
- Private config at `/etc/homelab-mcp/settings.json`, owned by `homelab-mcp`, mode 0600; directory mode 0700 and accessible to that account
- `/var/lib/homelab-mcp/{oauth,health,audit}`, service-owned mode 0700
- OAuth/health paths in the private JSON set to those directories
- Broker socket path `/run/homelab-mcp/broker.sock` (unused while execution is disabled)

An administrator should create that account and directories, install source/venv, then create or privately copy configuration with the correct ownership. Never run the frontend as root. If you used the wizard under your personal account, don't reuse its ownership or absolute paths unchanged.

After reviewing unit contents, install only `homelab-mcp.service`, `homelab-mcp-health.service` and `homelab-mcp-health.timer` into `/etc/systemd/system/`, reload systemd, and enable/start the frontend and health timer. The broker unit is optional and should remain disabled until [execution setup](execution.md) is intentionally completed.

For Docker health, the collector's `--docker` flag opts into querying existing Docker permissions. Docker socket/group access is generally root-equivalent: do not grant it casually to the frontend/collector user. Prefer a separately isolated collector if those details matter.

## 5. Verify before routine use

- Health snapshot reports a current timestamp and expected host
- No authentication: `/mcp` rejects tool access
- Wrong GitHub account: all tools reject access
- Correct owner: only expected tools visible; callback URI mismatch refused
- Proxy preserves Host, rejects unrelated domains, and routes only this app
- Config/state are outside the checkout and absent from build contexts
- Backups and an independent login work

Real client OAuth, tunnel routing and wrong-owner integration checks require a deployment; fixture tests alone do not establish them. Don't capture credential-bearing request/response bodies while diagnosing issues.

## 6. First execution checks

Use the [same-user broker instructions](execution.md#same-user-mode-recommended-first) after your health-only connection works. Set the private frontend `HOMELAB_ENABLE_EXECUTION` string to `true`, enable the broker separately, and use the same socket path and account. Start the broker, restart the frontend, and refresh your client's tool discovery. The examples below are requests to send through the client, not shell commands to paste into PowerShell.

| Tool | First request | Expected result |
| --- | --- | --- |
| `command_run` | `command="id -u; pwd"`, `cwd="/tmp"` | The broker account's UID and `/tmp` |
| `file_write` | A new, uniquely named `/tmp` file containing a short non-secret marker | A successful write result |
| `file_read` | Read that same fixture path | The original marker |
| `file_move` | Move the fixture to another unused `/tmp` name | The new path and move result |
| `command_start` | `command="printf started; sleep 30"`, `cwd="/tmp"` | A job ID |
| `job_status`, `job_output` | Use the returned job ID | State and bounded output |
| `job_cancel` | Cancel the still-running fixture job | A cancelled state |

Choose unique fixture names and remove only those fixtures when done. An execution result can describe an operation failure even when the MCP request itself succeeded; check return codes and error fields. The [execution guide](execution.md) explains limits and the [recovery guide](recovery.md) covers stale sockets, audit rotation, and retry decisions.

## 7. Make the installation persistent

For a native Linux or VM installation, adapt the systemd paths and account in section 4. The local-user quickstart uses a home-directory configuration; the supplied system units use `/opt`, `/etc`, and `/var/lib`. Do not mix those layouts without updating configuration and ownership consistently.

For a WSL2 trial, verify systemd availability and separately test Windows/WSL startup, sleep, networking, and reconnection as described in [Platforms](platforms.md#4-verify-operation-and-availability). For containers, configure restart behavior, persistent private mounts, and the proxy's shared network namespace explicitly. No example here installs a Windows service or starts a native PowerShell broker.

Before depending on any deployment, run the [live installation checks](validation.md#live-installation-checks), preserve private rollback material, and confirm the expected environment through the actual MCP client.
