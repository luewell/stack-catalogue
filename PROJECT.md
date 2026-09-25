# Stack catalogue context

This repository publishes native service and language runtime metadata for Stack,
with optional immutable Docker image metadata on selected releases.
A runtime entry separates the commands it can offer from the ones every pin gets:
`node`, `go`, `ruby` and `python3` are exposed, and `npm`, `npx`, `corepack`,
`gofmt`, `gem`, `bundle`, `rake`, `pip` and the rest are named by a repository
that wants them. Rust exposes what rustup's default profile installs (`cargo`,
`rustc`, `rustdoc`, `rustfmt`, `cargo-fmt`, `cargo-clippy`, `clippy-driver`),
since cargo finds `rustc`, `rustdoc` and its subcommands on PATH;
`rust-analyzer` and the debugger wrappers are opt-in.
Source entries live under `entries/`; `python3 build.py` validates identities,
HTTPS artifact URLs and digests (lowercase `sha256` or `sha512` for artifacts,
`sha256` for image indexes and manifests) and combines them into the committed
`v1.json`. A source file may share what its versions have in common through a
`defaults` block, and what its platforms have in common through
`defaults.every_platform`; both are expanded at build time, so
the served document stays a flat list of whole entries, each carrying its own
URL and digest. Version, digest, support and lifecycle are refused there,
because each states something about one release. The consumer validates runtime
and artifact contracts with `stack catalog check v1.json`.

Node 24.20.0 and PHP 8.4.25 carry `image` metadata for the official Bookworm
and FPM images respectively. The complete Node Bookworm image includes
`libatomic.so.1`, which the catalogue's standalone pnpm binary requires.
The metadata names the qualified repository, upstream
HTTPS source and provenance tag, with SHA-256 digests for the image index and
Linux amd64/arm64 manifests. Command paths name only commands the runtime entry
offers. Image process capabilities separately name the verified shell in both
images and PHP-FPM in the PHP image; they do not add native runtime commands.
Go 1.27.1 and 1.26.8 carry official Bookworm image metadata with pinned index and
Linux amd64/arm64 manifests. Their commands are `/usr/local/go/bin/go` and
`/usr/local/go/bin/gofmt`, with `/bin/sh` as the process shell. Native Go archives
remain available for relocatable tools inside another runtime's image.
Bun 1.4.2 and 1.1.18 carry official `oven/bun` Debian image metadata with pinned
Linux amd64/arm64 manifests, `/usr/local/bin/bun` and `/bin/sh`. Native Bun
archives retain their independently pinned release bytes. The image node fallback
and bunx alias do not extend the catalogue command allowlist.
S3 1.7.0 carries official `versity/versitygw` v1.7.0 image metadata with pinned
index and Linux amd64/arm64 manifests and `/bin/sh` as its process shell; it
declares no image commands because the entry exposes none, and its
`container_connection` repeats the endpoint its sites already use.

PostgreSQL 16, 17 and 18 run on Windows from theseus-rs's
`x86_64-pc-windows-msvc` archives, pinned to the SHA-256 each sidecar states
and GitHub records, under both `windows/amd64` and `windows/arm64` (Windows on
ARM runs them under emulation). Their `runtime.windows` initialises with a
password file and `--locale=C`, starts `postgres.exe` restricted and stops it
with `pg_ctl kill INT ${STACK_PID}`; readiness and provisioning are the shared
scripts, run by BusyBox.

PostgreSQL 18.6.0 carries official `postgres` Bookworm image metadata with
pinned index and Linux amd64/arm64 manifests, its thirteen client commands under
`/usr/bin` and `/bin/sh` as the process shell. Its `runtime.container_connection`
states the same variables as `runtime.connection` with `{host}` and `{port}` in
place of the loopback address a native instance listens on, for a service its
sites reach by name. Its `runtime.client_environment` states the `PG*` values a
client command needs to reach that service without arguments, and
`runtime.database_client_environment` states them for an explicit database with
`{database}` and `{database_user}`; the native backend gives both to commands run
through the group.

Native artifacts and image manifests are distinct release records;
an image digest does not assert native extension parity. `stack docker image`
selects these records without downloading or executing them. Only Linux arm64
runtime versions and declared command paths have execution verification.

MongoDB 8.0.32 (the default, long-term release) and 8.3.11 come from MongoDB's
own downloads: macOS arm64 and the Ubuntu 24.04 builds for Linux amd64 and
arm64, which also run on Ubuntu 26.04, pinned to the sha256 its `full.json`
publishes. The entry has no shell lifecycle beyond `start`: the `mongodb`
provisioner in Stack creates the administrator and each group's account, and
an account per explicit database, whose connection
`runtime.provisioned_database_connection` states with `{database}` and
`{database_user}`.
`mongosh` 2.12.0 is a runtime from the mongodb-js/mongosh GitHub releases,
pinned to the digests GitHub records.

BusyBox 6075 is an internal entry for Windows only: busybox-w32 FRP-6075 from
frippery.org as a bare `busybox.exe`, `busybox-w64` for `windows/amd64` and
`busybox-w64a` for `windows/arm64`, pinned to the SHA-256 in the release's
GPG-signed `SHA256SUM` (Ron Yorston's key `B43E244B92A81389CAAAA171690E10A0513DA84B`,
published at `github.com/rmyorston.gpg`). Stack runs the catalogue's `sh`
scripts and sites' commands with it on Windows, which has no POSIX shell.

NATS 2.15.0 (the default) and 2.14.7 come from the nats-io/nats-server GitHub
releases for macOS arm64 and Linux amd64 and arm64, pinned to the `SHA256SUMS`
each release publishes. The entry is in the `messaging` category; its start
command writes `nats.conf` with `max_payload: 64MB` and runs `nats-server` on the
loopback address with JetStream in the instance's data, and the `nats`
provisioner in Stack writes the accounts that file includes.

PostgreSQL, S3, MongoDB and NATS set `runtime.shareable`: one instance keeps each
group's data apart behind its own credentials, so Stack lets several groups
share it. Valkey does not set it. Each Valkey instance locks its `default` user with the
instance secret `VALKEY_ADMIN_PASSWORD` in a private `users.acl`, provisions one
ACL account per group from the group secret `REDIS_PASSWORD` without `@admin`
commands, and states that account in `REDIS_URL` and in the discrete `REDIS_HOST`,
`REDIS_PORT` and `REDIS_USERNAME` beside the exported `REDIS_PASSWORD`.

PostgreSQL's Linux artifacts come from the `luewell/stack-binaries` release
`postgresql-<version>`: the theseus-rs build with a `libxml2.so.2` added to `lib/`,
because Ubuntu 26.04 no longer ships that library. macOS stays upstream.

PostgreSQL entries refuse an implicit group database another role owns, and
complete an explicit database whose creation stopped before PUBLIC's grants were
revoked, recognised by its connections still being disabled.

PostgreSQL entries provision an implicit database per group or explicit named
databases through `runtime.database_provision`. Explicit databases have distinct
stable credentials and generated roles. The provisioner verifies existing role
markers, privileges, membership, database ownership and access grants before
making changes.
Connection templates expose URLs and discrete host, port, username and database
fields; explicit database templates use `{database}` and `{database_user}`.

Runtime SQL authentication and isolation are verified by Stack's opt-in native
PostgreSQL integration suite using this generated catalogue. Catalogue generation
and consumer tests alone do not establish live authentication behavior.

S3 connections retain AWS SDK variables and expose equivalent `S3_ENDPOINT`,
`S3_ACCESS_KEY_ID` and `S3_SECRET_ACCESS_KEY` aliases through catalogue templates.
Bucket convenience names are composed by Stack from the declared bucket policy.
A service-level `env_prefix` changes the S3 alias prefix while AWS SDK variables
retain their original names.
