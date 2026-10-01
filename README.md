# Homelab MCP

**Manage your Linux server through your AI assistant.**

Homelab MCP connects an OAuth-capable MCP client to a Linux machine you own. Start with host-health snapshots. If you choose, enable shell commands, text-file operations and asynchronous jobs through a private Unix-socket broker.

The application runs locally on your server. It makes no model API calls and requires no model API key. Your assistant/client and its provider may receive tool requests and results under their own terms. Remote MCP availability, account plans and supported authentication flows vary by client; this project does not promise compatibility with every assistant or subscription.

**Pre-release software for a trusted single owner. Not a shell sandbox or a security-certified product.** A client authorized to use execution tools can do everything the broker's OS account can do. Root mode means full host control. Assistant confirmation prompts are not a server-enforced approval boundary.

## Public code, private installation

The same generic source can be published and run privately. Keep your actual domain, account ID, OAuth credentials, signing/encryption keys, tunnel credentials, snapshots, audit records and token state **outside this checkout**. Examples contain placeholders only. Do not publish an existing deployment directory or carry private Git history into a public repository.

- Owner authentication: GitHub OAuth with a numeric GitHub account-ID check on every tool
- Default: `probe` and `health`; no shell or file tools
- Optional execution: same-user broker by default; root requires an additional explicit opt-in
- Persistent encrypted OAuth state and short-lived MCP access tokens
- Exact client callback allowlist, loopback-only HTTP listener, explicit public host/origin checks
- Bounded commands, output, file reads and in-memory jobs; metadata-only optional audit
- No automatic installation, firewall changes, account setup or remote publishing

## Start here

Requirements: Linux, Python 3.12, Bash, and an OAuth-capable remote MCP client. For remote use, supply your own HTTPS reverse proxy/tunnel and GitHub OAuth App. A public GitHub repository does not host this service for you.

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip check
.venv/bin/python -m unittest discover -s tests -v
```

For a local-user installation, run the interactive wizard as the account that will run the frontend. It writes outside the repository, hides the OAuth client secret as you type, and generates fresh keys locally:

```sh
.venv/bin/python scripts/create_config.py --directory "$HOME/.config/homelab-mcp"
.venv/bin/python host/collect_health.py --output "$HOME/.config/homelab-mcp/health/health.json"
HOMELAB_CONFIG_FILE="$HOME/.config/homelab-mcp/settings.json" .venv/bin/python -m app.server
```

For ChatGPT, add `--client chatgpt` to the wizard command; this trusts only its exact public client-metadata and signing-key URLs. Other clients use dynamic registration by default, or explicitly configured trusted metadata/key URLs.

The frontend binds `127.0.0.1:8080`. Configure an HTTPS proxy on the same host and preserve the public `Host` header. OAuth is required even on loopback; there is no unauthenticated development shell. Finish the [setup guide](docs/setup.md) before connecting a client.

## Tools

| Tool | Default | Purpose |
| --- | --- | --- |
| `probe` | enabled | Echo a bounded literal challenge with time and a nonce |
| `health` | enabled | Read bounded host snapshot, report its age and stale status |
| `command_run`, `command_start` | opt-in | Bash as the broker OS account; synchronous or job-based |
| `job_status`, `job_output`, `job_cancel` | opt-in | Job status, bounded output and process-group cancellation |
| `file_read`, `file_write`, `file_move` | opt-in | Bounded text reads, atomic replacements with backups, moves |

Files are not limited to a folder allowlist. Execution tools can read secrets or delete data if requested. Tool hints are advisory; they do not authorize or restrict execution. Do not put secrets in commands or ask an assistant to read credentials.

## Documentation

- [Setup and configuration](docs/setup.md)
- [Security model and limitations](SECURITY.md)
- [Optional execution and root management](docs/execution.md)
- [Migration from a private deployment](docs/migration.md)
- [Recovery and maintenance](docs/recovery.md)
- [Validation and remaining checks](docs/validation.md)
- [Release checklist](docs/releasing.md)
- [Licensing](docs/licensing.md)

## Development

```sh
.venv/bin/python -m compileall -q app host scripts tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_public_tree.py
```

Tests use disposable local fixtures. They do not enter host namespaces, contact GitHub or deploy a service. Dependency versions and distribution hashes are locked; Docker base images are digest-pinned. OS packages and GitHub Actions major-version tags still need release-time review. No live OAuth flow, privileged deployment or container build is implied by unit tests.

Licensed under the [MIT License](LICENSE). Copyright © 2026 Keaton Meek. Runtime dependencies retain their respective licenses.
