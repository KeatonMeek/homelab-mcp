# Preparation validation

Checked on 2026-10-01 in a Linux cloud workspace using Python 3.12. This records source-package validation, not a live deployment certification.

## Passed

- Clean virtual environment installation from `requirements.lock` with `pip --require-hashes`
- `pip check`: no broken requirements
- Python compilation for app, collector, scripts and tests
- Ruff 0.16.10 `F,E9` checks: no findings (focused fatal/unused checks, not a complete style/security audit)
- Unit/fixture integration suite: 45 tests executed, 44 passed
- Authentication rejection for absent/wrong owner/missing scope; intended owner path
- Exact callback restrictions, encrypted OAuth-state persistence, disabled-by-default tool registration
- Opt-in trusted CIMD/JWKS and ChatGPT-style private_key_jwt fixture verification, including the actual FastMCP discovery/token HTTP routes, rejected untrusted URLs/private DNS/redirects, signature/issuer/audience/expiry/replay checks and no stale fallback
- The fixture token request passed client authentication and then rejected its intentionally nonexistent authorization code; no real user authorization-code exchange was performed
- ASGI loopback/Host/Origin/forwarding and bounded request-body checks, including an escaped 128 KiB file payload
- Disposable broker command/file/job, timeout, output-bound, cancellation, audit and opt-in tests
- Generic collector, configuration and snapshot tests
- JSON, YAML and TOML parse checks
- Public-tree heuristic checks and targeted manual check for known deployment-specific identifiers

## Not established

- One real AF_UNIX socket test was skipped because this workspace prohibits Unix socket creation. Mocked broker protocol tests passed; real socket transport must run on an ordinary Linux test host.
- systemd unit verification was blocked by the workspace's read-only `/run/systemd`; installing/starting units was not attempted.
- No Docker executable was available; neither image was built here.
- No live GitHub OAuth round trip, actual MCP client connection, tunnel/TLS routing or wrong-owner live login was tested.
- No root/privileged container or namespace operation, production installer, migration or service change was run.
- No independent original private-history audit, comprehensive secret scan, dependency vulnerability audit or security certification is implied.

The release starts with fresh Git history; no private repository history is inherited. Source archives exclude Git metadata. Complete the release checklist and review the actual candidate commit before public publication. Changes after this validation require affected checks to be rerun.
