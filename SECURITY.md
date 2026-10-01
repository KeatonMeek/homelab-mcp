# Security model

This project is a remote administration surface for a single trusted owner. It is not a multi-tenant service, a shell sandbox, a policy approval engine or a security-certified product. Public source is compatible with private configuration, but publishing source cannot guarantee that a running deployment is safe.

## Boundaries and defaults

- The frontend binds loopback, requires an exact public Host, checks Origin when supplied and ignores spoofable forwarding headers. A separately managed HTTPS proxy/tunnel is responsible for TLS and public routing.
- GitHub OAuth establishes identity. Every tool requires the configured numeric owner ID and `read:user` scope. Exact MCP-client callback allowlisting reduces redirect confusion. Neither a hostname nor an assistant's claim establishes ownership.
- Client metadata (CIMD) is opt-in through exact metadata and JWKS URL allowlists. The ChatGPT wizard option pins its public client metadata and signing-key endpoints, preserves private_key_jwt authentication and retains exact callback restrictions. Outbound fetches use the pinned FastMCP DNS/public-IP protections with redirects refused; cached keys expire within five minutes and failures do not fall back to stale persisted clients. This relies on reviewed provider internals and must be retested on dependency upgrades.
- By default, only literal probe and pre-collected health tools exist. The frontend performs no host commands for those tools.
- Enabling execution registers commands, file operations and jobs. The broker separately refuses all requests unless execution was explicitly enabled at startup. The broker listens only on a private Unix socket, verifies the peer OS UID and accepts no network connections itself.
- Same-user mode has the broker account's ordinary permissions. Running the broker as UID 0 requires another explicit opt-in. Optional namespace mode is full root administration, with host PID access and a privileged container. Do not mistake `--network=none` on that container for a network restriction on commands: `nsenter --net` enters the host network namespace.

**An authorized or compromised owner session can do everything the broker account can do, including read credentials, change the service, persist access, delete files, or control the whole host in root mode.** Access to a Docker socket, passwordless sudo, writable service definitions, privileged groups or other escalation paths can make an apparently unprivileged account root-equivalent.

**Assistant confirmations and MCP tool hints are not server-enforced approvals.** There is no independent per-command approval token, command allowlist or second-person review. The server cannot tell whether a command reflects the human's intent. Prompt injection, mistaken model reasoning and compromised MCP clients remain serious risks. Use a dedicated least-privileged account and keep execution disabled unless you accept that risk.

## What private data can leave

Commands, file contents and tool results are delivered to the requesting MCP client and potentially its AI provider. Health metadata can include hostname, container names/images, mount paths, service names, listening ports and aggregate errors. It excludes raw journal messages and container environment variables, but metadata may still be sensitive. A proxy, client or upstream provider may retain traffic independently of this application.

Do not ask the assistant to read private keys, tokens, passwords, database dumps or secret-bearing logs. Never embed secrets in commands. Best-effort output redaction covers some common key blocks/token formats; it cannot reliably recognize arbitrary, encoded, split or partially read secrets. It may also corrupt ordinary source-code strings and JSON that look like secrets. Redaction is not data-loss prevention.

OAuth state is encrypted at rest, but the frontend owns its encryption key and can decrypt it. Theft of both configuration and state defeats this protection. Same-UID processes can often access each other's files and runtime; running the broker as the frontend UID does not isolate frontend credentials from commands.

## Operational limits

- Jobs are kept in memory only, with a 64-job history and eight concurrent jobs. Restart loses IDs and output; new jobs evict completed history. Output is bounded, but detached processes and command-created files are not quota-managed.
- Cancellation sends signals to a process group. It cannot undo changes or reliably stop deliberately detached descendants. Backups are not transactions.
- File helpers refuse final symlinks, symlink parent components and common nonregular targets, but path checks are not a race-resistant filesystem sandbox. Another process may change paths between checks and operations. Commands bypass those helpers entirely.
- Replacements use same-directory temporary files and preserve basic mode/UID/GID. They do not guarantee retention of every ACL, xattr, hard-link relationship or application-level invariant. A crash can still lose unflushed directory metadata. Cross-filesystem moves are not atomic.
- Backups may contain secrets and accumulate indefinitely. They use private file permissions but remain readable to their owner/root. Review backup retention explicitly.
- Audit records omit command text, paths, file contents and output, retaining timestamps, operation, job ID, status and optional command hash. Hashes can reveal low-entropy commands by guessing. The audit file stops new work above its size limit until an operator rotates it; it is not tamper-proof and root can rewrite it.
- Request/output/time/concurrency bounds reduce accidents and some denial-of-service risks. They do not comprehensively rate-limit OAuth endpoints, constrain CPU/memory/disk/network use of shell commands or protect a hostile shared machine.
- Dependency pins/hashes and tests improve repeatability, not proof of absence of vulnerabilities. Review upstream advisories and refresh pins deliberately.

## Reporting

Until a maintainer provides a private reporting address or enables GitHub private vulnerability reporting, do not open public issues containing credentials, exploit details about an active server, or private operational data. Use the repository's private security reporting channel when available. For an exposed credential, revoke/rotate it first; deleting it from a later commit is insufficient.

## Recommended use

Prefer health-only, a single owner, strong GitHub account security, dedicated non-root service accounts, least-privileged host access, trusted HTTPS, private config/state, reviewed upgrades, offline backups and an independent recovery path. Treat enabling shell access as granting an administrator credential to your assistant session.
