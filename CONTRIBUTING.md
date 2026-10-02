# Contributing

Thanks for taking a look at Homelab MCP. Contributions can be code, tests, clearer setup instructions, client compatibility reports, or a careful review of the implementation.

## Get started

Fork the repository, clone your fork, and create a branch for your change. Use Linux with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements.lock
.venv/bin/python -m pip check
.venv/bin/python -m compileall -q app host scripts tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_public_tree.py
```

Keep tests self-contained with disposable fixtures. Tests must not require credentials, host-root namespace entry, or a running production service. See [Testing and deployment checks](docs/validation.md) for container builds and live verification.

## Submit a change

- Describe the problem and the resulting behavior. Include a small reproduction for bug fixes.
- Keep changes focused, and add regression coverage for behavior changes.
- Update setup instructions or examples when configuration, tool schemas, or deployment behavior changes.
- Include the checks you ran and any environment-dependent checks you could not run.
- Keep examples generic. Never commit configuration, credentials, token state, health snapshots, or private server details.

Discuss substantial architecture or permission changes before implementing them. Changes to authentication, callbacks, permissions, file handling, or deployment defaults need a security-focused review.

Authentication changes should preserve exact owner and callback checks. Execution changes should preserve explicit opt-in behavior and document their operating-system permissions. Review the [security model](SECURITY.md) when changing either boundary.

## Report a problem or share a review

For ordinary bugs, open an issue with your Python version, client type, relevant package version or commit, and a minimal reproduction. Use synthetic values and remove private data from any output you include. Suggestions and reviews of documentation, deployment portability, tests, and authentication are welcome too.

For sensitive findings, follow [Security reporting](SECURITY.md#reporting) rather than posting exploit details or operational data in a public issue.

## Maintain a release

Use the [release checklist](docs/releasing.md) before publishing a release. For existing installations, consult [Recovery and maintenance](docs/recovery.md) and [Migration](docs/migration.md). Publication and deployment are separate steps.

Contributions are made under the project's [MIT License](LICENSE). Preserve applicable copyright and third-party license notices.
