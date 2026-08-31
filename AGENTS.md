# Stack catalogue

This repository provides the service and runtime catalogue consumed by Stack.
The user's global instructions apply. All project artifacts are English.

- Source entries live in `entries/<category>/<type>.json`. Keep versions of one
  type together and preserve the existing readable JSON formatting.
- `v1.json` is generated and committed. Edit source entries, then run
  `python3 build.py`; never maintain the combined file independently.
- `build.py` uses Python's standard library and rejects duplicate type/version
  identities. No dependency installation is needed to regenerate the catalogue.
- `.github/workflows/check.yml` checks generation, required artifact metadata
  and downloaded digests. Local validation also uses Stack's
  `stack catalog check v1.json`; a JSON parser alone does not validate runtime
  commands or security behavior.
- Runtime templates execute with the consuming user's privileges. Validate
  authentication and isolation with the matching Stack integration tests before
  changing initialization, provisioning or access policies.
- Command templates receive paths and identities as reserved `STACK_*` environment
  variables. Quote expansions; do not splice values into shell source. Service
  metadata and connection templates retain their separate substitution contract.
- Node entries carry official lifecycle dates; the consumer refreshes LTS/EOL
  status from those dates. Update source and generated metadata together.
- The S3 entry selects `provisioner: versitygw` for native signed account creation;
  root/group credentials must not appear in administrative command arguments.
- PostgreSQL uses SCRAM for TCP and Unix sockets, a reserved administrator,
  per-group passwords and a `pgdata` cluster directory. Connection templates may
  interpolate only declared group secrets. S3 publishing declares both policy
  and ACL ownership attributes. Stack's `internal/service/AGENTS.md` documents
  the matching consumer contracts.
- Every downloadable artifact requires an HTTPS URL and pinned digest. Changes
  to runtime commands must not silently alter artifact URLs, digests or versions.
- Never publish, stage, commit or modify real service data without explicit
  authorization.
