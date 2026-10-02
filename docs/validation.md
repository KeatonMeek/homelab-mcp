# Testing and deployment checks

Use automated tests to check the source and separate live checks to verify an installation. GitHub Actions runs the repository's test workflow on pushes and pull requests; consult the run for the exact commit you intend to use.

## Local test suite

On Linux with Python 3.12, from the repository root:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q app host scripts tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_public_tree.py
```

The suite covers:

- Owner authorization, exact callbacks, encrypted state, and default tool registration.
- Trusted client metadata and signing-key retrieval, client assertions, and rejected untrusted destinations.
- Loopback, Host, Origin, request-body, and broker protocol checks.
- Exported tool schemas, including absolute paths under full-match client validation.
- Disposable command, file, job, timeout, cancellation, output-bound, and audit fixtures.
- Configuration, health collection, and snapshot handling.

Tests do not use live OAuth credentials, deploy services, or enter host namespaces. The real Unix-socket test may skip in environments that prohibit socket creation. Run it on an ordinary Linux test host before relying on broker transport.

`check_public_tree.py` checks for selected credential patterns and runtime files. Use it alongside manual review; it is not a comprehensive secret scanner or security audit.

## Container builds

Build both images from a clean checkout on a Linux machine with Docker:

```sh
docker build -f deploy/Dockerfile -t homelab-mcp:test .
docker build -f deploy/Dockerfile.broker -t homelab-mcp-broker:test .
```

Building the broker image does not enable execution. Review [deployment configuration](setup.md) and [execution modes](execution.md) separately before starting containers. For systemd installations, validate the adapted unit files with `systemd-analyze verify` on the target distribution before enabling them.

## Live installation checks

Use a test installation or a planned maintenance window, with an independent recovery path:

1. Verify HTTPS routing, discovery, and exact callback settings.
2. Confirm unauthenticated requests cannot call tools and a different GitHub account cannot access the owner's tools.
3. Connect the intended MCP client, call `probe`, and check that `health` reports a current snapshot.
4. Confirm command and file tools are absent when execution is disabled.
5. If execution is enabled, use disposable files and harmless commands to check account identity, file operations, output limits, timeouts, job status, and cancellation through the actual client.
6. Refresh client tool discovery after schema changes. Verify exported tools as well as direct broker behavior.
7. Check planned restart recovery, saved authentication, and your rollback procedure before routine use.

Record the tested commit and results privately without credentials or sensitive output. A passing test suite or container restart does not establish whole-host reboot recovery or compatibility with every client. Review [Security](../SECURITY.md) for the permission model and operational limits.
