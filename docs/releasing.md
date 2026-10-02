# Release checklist

Use this checklist for a candidate release. Source publication, image builds, and deployment are separate actions.

## Source and documentation

- [ ] Review the diff, including examples, tests, workflow changes, and dependency updates.
- [ ] Check README commands, configuration names, relative links, and client setup instructions against the implementation.
- [ ] Keep runtime configuration, credentials, state, logs, snapshots, and private deployment identifiers outside the repository.
- [ ] Run `python scripts/check_public_tree.py`, an independent secret scan, and manual review of the files to be published.
- [ ] Preserve the MIT License and required third-party notices; see [Licensing](licensing.md).
- [ ] Review the repository's private vulnerability reporting options and keep [reporting guidance](../SECURITY.md#reporting) current.

## Build and behavior

- [ ] Install from the hash-locked dependencies in a clean Python 3.12 environment and run `pip check`.
- [ ] Compile Python files and run the full test suite, including real Unix-socket transport on Linux.
- [ ] Review dependency advisories and changes to Docker base images, OS packages, and GitHub Actions references.
- [ ] Build the application and broker images from the candidate source.
- [ ] Validate adapted systemd units and proxy configuration where those deployment methods are being supported.
- [ ] Follow the [live installation checks](validation.md#live-installation-checks) for the affected client and deployment paths.
- [ ] Review recovery procedures affected by the change, including authentication state, broker sockets, audit rotation, and rollback.

## Publish

- [ ] Confirm the candidate commit, intended repository, and commit attribution.
- [ ] Verify the pushed commit and its CI result.
- [ ] Describe user-visible changes, configuration changes, and required upgrade steps.
- [ ] Identify what was tested without treating fixtures as evidence of a live deployment.

When publishing a project derived from a private installation, prepare a reviewed public tree with fresh history. Do not change the visibility of a private deployment repository or import its configuration and history. See [Migration](migration.md) for separating source, configuration, and runtime state.
