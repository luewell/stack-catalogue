# Stack catalogue

This repository provides the service and runtime catalogue consumed by Stack.
The user's global instructions apply. All project artifacts are English.

- Source entries live in `entries/<category>/<type>.json`. Keep versions of one
  type together and preserve the existing readable JSON formatting.
- A file's `defaults` block describes the type and each entry under `services`
  describes one release: its version, support, lifecycle, description and
  digests, plus anything that release alone does differently. A file with a
  single version keeps that split too, so the day it gains a second one nothing
  moves. `{version}` inside a default is expanded per entry; a release writing
  its own URL writes it whole. Fields merge one level into `artifacts` platforms
  and `runtime`, and no deeper.
- `defaults.every_platform` holds what each platform's build says identically,
  which is usually how the download is unpacked, leaving `artifacts` to name one
  URL per platform. A platform stating a field for itself keeps its own.
- `defaults` may not carry `version`, `digest`, `support` or `lifecycle`, and
  `build.py` refuses a file that does. Each of those is a claim about one
  release: an inherited checksum is a version claiming another's bytes, and an
  inherited support status leaves the generated file always carrying one, so
  nothing downstream can see that nobody chose it.
- `v1.json` is generated and committed. Edit source entries, then run
  `python3 build.py`; never maintain the combined file independently.
- `build.py` uses Python's standard library, expands `defaults` and rejects
  duplicate type/version identities. It writes whole entries in one field order,
  so the served file has one shape whatever a source file's order. No dependency
  installation is needed to regenerate the catalogue.
- It also refuses a file that states the same thing for every version or for
  every platform when `defaults` or `every_platform` could state it once, and a
  single-release file that describes its type beside that release. The fields
  each release states for itself are exempt, so a type whose builds are one file
  for every platform still writes that digest per platform.
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
- A runtime is verified after installation by running its pinned command with
  `runtime.version_arguments`, `--version` when absent. Go declares `version`.
- Every downloadable artifact requires an HTTPS URL and pinned digest. Changes
  to runtime commands must not silently alter artifact URLs, digests or versions.
- Never publish, stage, commit or modify real service data without explicit
  authorization.
