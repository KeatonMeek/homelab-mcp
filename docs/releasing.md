# Release checklist

The prepared tree is source code, not proof of a production deployment. The project is MIT-licensed. Publication and deployment remain separate operator actions.

## Privacy and ownership

- [ ] Use a fresh repository/history; do not change an existing private repository's visibility
- [ ] Review every prospective tracked file, including hidden files, tests, workflow logs and examples
- [ ] Exclude all runtime config/state, credentials, domain/account identifiers, host paths, logs, screenshots and private-history artifacts
- [ ] Run `python scripts/check_public_tree.py`; understand that it is a limited heuristic, not a full secret scanner
- [ ] Run an independent reputable secret scan and manual content review before publication
- [ ] Verify the commit author/committer identity with the owner; use an approved GitHub noreply address if privacy is desired
- [x] MIT License and copyright attribution approved; see [licensing](licensing.md)
- [ ] Confirm intended repository owner, public visibility, name and description
- [ ] Configure private vulnerability reporting or a maintainer reporting contact

## Reproducibility and behavior

- [ ] Python 3.12 clean-venv install from hash-locked dependencies succeeds; `pip check` passes
- [ ] Compile all Python files; run full unit/integration fixture suite
- [ ] Review transitive dependencies/advisories; version pins do not certify safety
- [ ] Validate workflow and deployment examples; pin GitHub Actions to reviewed immutable commits before hardened release if desired
- [ ] Build application/broker images on an authorized disposable Linux environment and review image findings
- [ ] Check real TLS/proxy routing, owner login, no-auth and wrong-owner rejection
- [ ] Check execution tools are absent by default and broker rejects disabled execution
- [ ] If offering root mode, separately test harmless namespace operations on a disposable host
- [ ] Verify backup, key rotation, restart, stale socket, audit-full and rollback procedures

## Publish only after approval

Create the repository with only the reviewed tree and fresh history. Verify the pushed commit and CI status. Do not deploy, enable root access or migrate an existing server merely because the code was published. Keep the status honest: indicate which live checks remain unrun and avoid universal client/subscription or security claims.
