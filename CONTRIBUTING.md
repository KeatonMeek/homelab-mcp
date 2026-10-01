# Contributing

Contributions that improve usability, portability, documentation and security are welcome. Discuss substantial architecture or privilege changes before implementing them. Contributions are expected to use the project's MIT License; see [LICENSE](LICENSE).

Use Python 3.12, install the hash-locked dependencies in a venv and run the README checks. Tests must use disposable fixtures and must never require credentials, host-root namespace entry or a running production service. Keep configuration generic and outside the repository. Changes to authentication, callback validation, OS privilege boundaries, file handling or deployment defaults need explicit security-focused review.

Do not include private server details or credential-bearing logs in issues or pull requests. Report security-sensitive findings privately through the configured repository channel when available. See [SECURITY.md](SECURITY.md) for reporting guidance and the current threat model.
