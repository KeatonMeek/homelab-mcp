# Setup

This guide describes actions for the operator to review and run on their own Linux host. It is not an installer. Start without execution tools and keep an independent SSH/console recovery path.

## 1. Authentication and HTTPS

1. Choose an HTTPS origin you control, such as `https://mcp.example.com`. No URL subpath is supported for the origin. The MCP endpoint will be `/mcp`.
2. In [GitHub's OAuth App settings](https://github.com/settings/developers), create an OAuth App. Use your public origin as its homepage and the exact URL `https://mcp.example.com/auth/callback` as its GitHub authorization callback.
3. Obtain your own numeric GitHub account ID from [GitHub's authenticated-user API](https://docs.github.com/en/rest/users/users#get-the-authenticated-user). This is an account ID, not a username. Do not authorize a different account just because it has a similar display name.
4. Begin adding a remote MCP server in your client and copy its exact HTTPS OAuth callback URI. This is different from the GitHub callback in step 2. Client UI and plan availability vary. Never guess a callback, wildcard it, or use a URL provided by an untrusted tool response.
5. Configure a trusted reverse proxy or tunnel on this same host to route your HTTPS hostname to `http://127.0.0.1:8080`, preserving `Host: mcp.example.com`. Examples for Caddy and cloudflared are under `deploy/`. If using a non-default HTTPS port, preserve the port in Host as well.

The frontend requires GitHub OAuth and owner authorization; putting a tunnel in front of it does not replace these checks. Don't add an interactive reverse-proxy login page in front of MCP unless your client supports that flow. Do not expose the Python listener directly or relax its peer/host checks. A proxy in a separate network namespace is not a loopback peer; use the host service reference rather than opening the listener to the world.

Provider reference: [FastMCP GitHub authentication](https://gofastmcp.com/integrations/github), [FastMCP OAuth proxy](https://gofastmcp.com/servers/auth/oauth-proxy), [GitHub OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app).

## 2. Local-user startup

Install Python 3.12 using your distribution's supported method. Clone or copy the generic source; do not place secrets in that checkout. Create a venv and install the hashed lock as shown in the README.

Run `scripts/create_config.py --directory "$HOME/.config/homelab-mcp"` with the venv Python. For ChatGPT, add `--client chatgpt` to enable its exact metadata and signing-key endpoints. It asks for the origin, your numeric account ID, OAuth App ID and secret, and exact MCP-client callback. It generates signing/encryption keys, creates private directories and saves `settings.json` with mode 0600. Do not paste the generated file into chat, issues or support logs.

The wizard writes explicit absolute paths. Move the configuration only after adjusting those paths. Runtime startup refuses missing values, malformed callbacks, invalid keys and unsafe token-state permissions. There are no fallback keys or automatic `.env` reads.

Collect a health snapshot, then start the server using the README commands. The collector can run without root. Missing Docker/journal permissions are reported as unavailable and do not require privilege escalation. Run it approximately once per minute using the provided timer or your existing scheduler.

Configure the client with `https://mcp.example.com/mcp`, sign in with the configured GitHub account and approve the requested `read:user` scope. Test `probe` first, then `health`. Confirm that the shell/file tools are absent. A different GitHub account must not gain access.

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
