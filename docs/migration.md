# Moving an existing private installation to public generic code

This is a planned migration, not a command to change an active installation. Keep the existing service and private repository intact until a tested cutover is authorized. A public source repository can be used by the same private server without storing that server's identity or secrets in Git.

## Keep three things separate

1. Public generic source, tests and placeholder examples, with fresh Git history
2. Private deployment configuration and secrets outside the checkout
3. Private mutable state: encrypted OAuth data, health snapshots, audits and backups

Do not flip an old private repository's visibility. Do not copy its `.git`, deployment manifests, credentials, snapshots, terminal output, logs or history into the new repository. An original-history audit, when unavailable, cannot be substituted with a claim that history is clean. Fresh history limits what you publish, but the new files still need review.

## Configuration migration map

| Older deployment setting | Generic setting |
| --- | --- |
| `HSM_BASE_URL` | `HOMELAB_BASE_URL` |
| `HSM_OWNER_ID` / `PROBE_GITHUB_OWNER_ID` | `HOMELAB_GITHUB_OWNER_ID` |
| `HSM_CHATGPT_REDIRECT` / `PROBE_CHATGPT_REDIRECT_URI` | `HOMELAB_CLIENT_REDIRECT_URIS` JSON-encoded list |
| `PROBE_GITHUB_CLIENT_ID` | `HOMELAB_GITHUB_CLIENT_ID` |
| `PROBE_GITHUB_CLIENT_SECRET` | `HOMELAB_GITHUB_CLIENT_SECRET` |
| `PROBE_JWT_SIGNING_KEY` | `HOMELAB_JWT_SIGNING_KEY` |
| `PROBE_STORAGE_ENCRYPTION_KEY` | `HOMELAB_STORAGE_ENCRYPTION_KEY` |
| `PROBE_TOKEN_STORE_DIR` | `HOMELAB_STATE_DIR` |
| Fixed `/broker/broker.sock` | `HOMELAB_BROKER_SOCKET` |
| Fixed health snapshot path | `HOMELAB_HEALTH_SNAPSHOT` |
| Connector IP filter | Same-host loopback proxy and strict public Host/Origin checks |

Old environment names are not automatically accepted. The frontend no longer looks for secret files adjacent to Python source. `HOMELAB_CONFIG_FILE` is an explicit absolute private JSON path. The numeric owner remains a private deployment value; no person-specific owner ID is baked into the code.

## Behavioral changes to account for

- Health/probe only by default. Enabling execution now requires flags in both frontend and broker.
- Broker defaults to the OS account running it, without namespace entry. UID 0 requires explicit opt-in; namespace mode requires `host-root` as well.
- Frontend binds loopback only. An old bridge-network connector is not a loopback peer. Move the proxy to the same host/network namespace or design and review a replacement; do not simply bind to `0.0.0.0`.
- For a ChatGPT client using CIMD/private_key_jwt, explicitly configure its trusted metadata and JWKS URLs as described in setup (or use the wizard’s `--client chatgpt` option). Default DCR-only configuration will not preserve that client path.
- Client callback allowlist now supports explicit HTTPS clients rather than one hardcoded provider domain. Exact equality includes query strings.
- Broker socket ownership/peer UID is configurable rather than assumed to be 1000. New startup refuses an existing socket until its status is investigated.
- Backups use the `.homelab-backup-` prefix. Audit has a fixed size stop instead of silently replacing the previous audit file.

## Staged cutover

1. Back up the existing private configuration/state securely and record how to restart the old service. Do not export those backups into the public tree.
2. Install the new generic code beside the old installation, with a new venv. Run tests locally without host namespace access.
3. Create a separate private configuration and separate OAuth state directory. Use a test origin/port and separately authorized OAuth App where possible. Do not run old/new processes against the same mutable token store.
4. Test missing-auth rejection, wrong-owner rejection, correct-owner probe/health and exact redirect handling. Only then test harmless execution as a least-privileged account if needed.
5. Preserving old signing/encryption keys and state is not a promised zero-reauthentication migration. Fresh keys/state and owner reauthorization are the simplest clean boundary. If preserving state, back it up, verify the pinned provider's storage compatibility and stop the old process first.
6. At an approved maintenance window, adjust the private proxy/service configuration and connect the client to the intended endpoint. Verify live behavior before retiring anything.
7. Keep rollback possible. Changing the public project or plugin display name alone does not deploy this implementation or migrate state.

No migration, root deployment, secret rotation or live cutover was performed by preparing this package.
