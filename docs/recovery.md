# Recovery and maintenance

Keep an independent SSH session or console available before changing an administration tool. Do not rely on this service to repair its own authentication or network access.

## Failure guide

- **Startup configuration error:** verify required names, exact HTTPS callbacks, numeric owner ID, file ownership/mode and existing private state directory. Do not enable debug dumps of config or environment.
- **403 from the proxy/frontend:** check same-host loopback routing, preserved public Host (including a nondefault port), exact Origin and base URL. Spoofed forwarding headers are intentionally ignored.
- **OAuth/login failure:** verify GitHub App callback `/auth/callback`, separately verify the MCP client's exact callback list, owner account, clock and credential validity. Do not broaden redirects to wildcards.
- **Health unavailable/stale:** check the collector timer and snapshot permissions/path. Missing Docker/journal permissions may be expected. Avoid adding root privileges merely to hide an unavailable status.
- **Broker unavailable:** check both execution flags, matching socket paths, correct UID/permissions and broker service status. Do not open a TCP broker listener.
- **Broker socket already exists:** first establish whether a broker is running and whether active jobs matter. Only after stopping it and confirming the socket is stale should an operator remove that socket. Never delete unknown paths blindly.
- **Audit full:** new operations stop after the approximate 2 MB audit threshold. Stop the broker and securely rotate/archive the metadata file as its owner, then restart. Do not publish audits.
- **Lost job ID:** broker restart/eviction discards in-memory metadata and output. Check the actual host state before repeating a possibly completed operation.

## Cancellation and backups

Cancellation cannot reverse completed writes and does not reliably catch detached processes. Inspect the target state before retrying. File-write backups are adjacent, private `.homelab-backup-*` files; restore only after checking ownership, intended contents and application consistency. Cross-filesystem moves do not have automatic rollback. Backups consume space and can contain the same secrets as the original file.

## Rotation and suspected compromise

Disable public routing or stop the frontend/broker to contain access. Use an independent trusted session to revoke GitHub OAuth authorizations/credentials as needed, rotate the signing and encryption keys, and review host state. Changing the encryption key makes old encrypted state unreadable; archive it privately and start with a new state directory. Reconnect the client through OAuth. An old access token may remain usable until expiration unless the service is stopped or its verification context is replaced; do not assume upstream revocation instantaneously invalidates every issued MCP token.

A root-capable compromised session may have persisted outside this application. Credential rotation alone may be insufficient; follow your incident-response and backup/rebuild procedures.

## Upgrades

Review changes and upstream security advisories. Use a fresh venv, install `requirements.lock` with `--require-hashes`, run all tests, then stage deployment. The lock records exact distribution versions/hashes, not a vulnerability audit. Update `requirements.in`, generate a new hashed lock using a reviewed dependency resolver, and review transitive changes. Do not silently upgrade runtime dependencies on a live server.

Pinned Docker images, OS packages, GitHub Actions references and proxy software need periodic review too. Container builds and privileged namespace behavior must be tested in an authorized disposable Linux host before treating them as deployment-verified.
