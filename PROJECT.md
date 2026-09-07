# Stack catalogue context

This repository publishes native service and language runtime metadata for Stack.
Source entries live under `entries/`; `python3 build.py` validates identities and
combines them into the committed `v1.json`. A source file may share what its
versions have in common through a `defaults` block, which is expanded at build
time: the served document stays a flat list of whole entries, each carrying its
own URL and digest. Version, digest, support and lifecycle are refused there,
because each states something about one release. The consumer validates runtime
and artifact contracts with `stack catalog check v1.json`.

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
