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
- A release leaves out a platform its defaults offer by writing that platform
  as `null` under its `artifacts`; the generated entry then names no artifact
  there. `build.py` refuses `null` for a platform the defaults do not offer, and
  for one every version leaves out, which the defaults should drop instead.
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
  and downloaded digests, hashing each download with the algorithm its digest
  names and refusing a URL or redirect that is not HTTPS. Local validation also
  uses Stack's `stack catalog check v1.json`; a JSON parser alone does not
  validate runtime commands or security behavior.
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
- `runtime.container` is how Stack's Docker backend runs an entry; Docker runs
  only services declaring it, PostgreSQL and S3 here. A service states its
  `port`, `data` volume directory, `healthcheck` and optionally `environment`,
  `command` and an `init` script run once it is healthy, all expanding
  `{group}`, `{host}`, `{port}`, `{data}` and `{buckets}`; an environment value
  names a secret as `${NAME}`, and `$` elsewhere is the container shell's. S3's
  `init` is not its `provision`: it also creates the group's account, and the
  gateway image has awk but no grep, with two heading lines before the rows of
  its admin tables. A runtime states the `environment`, `path` and
  `version_output` its toolchain image adds, the last naming the release as
  `{release}`, which `build.py` does not expand, because a vendor-resolved
  release borrows the newest entry's runtime. `base_priority` picks the base
  image of a toolchain of several runtimes, highest first and unset as 0:
  PHP 1, Node unset, Go -1, Bun -2. Only a runtime declaring the block joins
  a Docker toolchain, so Node, pnpm and Composer declare it with only what
  they need, or empty. A runtime's `site_check` are arguments to its command
  that exit zero once a site running on it answers on `{port}`, and PHP's
  `server_port` is where its image's PHP-FPM listens, which `{port}` names
  for a site that server serves. Docker also reads `windows.run_with`: a
  toolchain with Composer needs a pin providing `php`.
- `runtime.extend` on a service says how a repository's `config:` files reach
  the engine. PostgreSQL uses `include_dir` (`syntax: postgresql`, main file
  `postgresql.conf` reading `engine_file` `pgdata/postgresql.conf` first,
  `arguments` `-c config_file=${STACK_CONFIG_FILE}`); Valkey uses `include`
  (`syntax: valkey`, main file `valkey.conf`, `arguments`
  `${STACK_CONFIG_FILE}`); NATS uses `include` (`syntax: nats`, main file
  `nats.conf`, `settings_file` `nats.conf`, the one its start writes, read
  after every listed file, `arguments` `-c ${STACK_CONFIG_FILE}`,
  `windows_append`). Stack puts the arguments right after the program: the
  shell `start` passes them as `"$@"` there, and Windows `start.arguments`
  are left as they are because Stack inserts them, or appends them with
  `windows_append`. NATS's shell start places `"$@"` after its own `-c`,
  because nats-server takes the last one and a released binary passes none.
  MongoDB, Mailpit and S3 declare no `extend`, so `config:` on them is
  refused. Reserved keys are refused
  in a listed file; reserve every setting that loads a library, runs a
  command, changes where the engine listens, names its data, accounts or
  main file, or detaches it from its supervisor, and write each reason as a
  predicate of the key, as "<key> <reason>" prints it. PostgreSQL's list
  follows the 16 to 18 documentation (`*_preload_libraries`,
  `dynamic_library_path`, `extension_control_path`, `jit_provider`,
  `oauth_validator_libraries`, `archive_library`, the archive and recovery
  commands, the log collector and syslog keys, `krb_server_keyfile`, `ssl`,
  `ssl_*` and `debug_print_*`, which would log provisioning passwords),
  Valkey's its `config.c` directives and
  aliases (`masterauth`, `masteruser`, `slaveof`), NATS's the top-level keys
  and aliases of nats-server's `opts.go` that touch accounts, sign-in,
  listeners, TLS, clustering, files written outside the data directory and
  `max_payload`, which Stack sets, with a nested key written `block.key`
  (`jetstream.store_dir` and its aliases, `jetstream.tpm`). A key ending in
  `*` reserves every key with that prefix. Stack also reserves a minimum per
  syntax in code, the keys that load code, write files, decide sign-in, open
  a listener Stack does not set up, hide commands or log secrets, so
  a key missing here is still refused; list them anyway, with their reasons.
- Fields are only ever added: released Stack binaries ignore fields they do not
  know, and fail on a renamed field or a changed JSON type. A new requirement
  on Stack goes in an entry's `requires`, a list of capability names (a
  lowercase letter, then up to 62 lowercase letters, digits or underscores);
  a release that does not know a name skips the entry with a warning. Raise
  `GENERATION` in `build.py`, which writes it as the top-level `generation`,
  when Stack drops code that a declaration replaced: releases needing the newer
  generation then refuse an older cached copy and fetch it again.
- A `provisioner` states what its entry must declare: `versitygw` needs nothing
  more, `mongodb` and `nats` their administrator secret, group secret and
  `initialised_marker` with no `initialise`, and only `mongodb` takes
  `provisioned_database_connection`. Each has a home type (`s3`, `mongodb`,
  `nats`); an entry selecting one on another type requires
  `provisioner_contracts`, because releases without that capability refuse it.
- `database_provision` and `database_connection` come together; a type other
  than `postgres` declaring them requires `database_provision_any_type`.
  `group_rename` makes a renamed group's data follow it: it runs in the moved,
  serving instance with the new group's provisioning environment and the old
  name in `STACK_OLD_GROUP`. `database_rename` needs it and explicit databases,
  and runs once per database with `STACK_OLD_DATABASE_USER` and
  `STACK_DATABASE_USER`. Each statement must be safe to repeat, and names reach
  the script only as variables.
- `runtime.windows.stop_request` (`protocol`, `secret`) asks a server to exit
  on Windows, where no signal reaches it, in place of a Windows `stop`. `resp`
  signs in as the default user with the named instance secret and sends
  `SHUTDOWN`; `mongodb` sends `shutdown` as the `mongodb` provisioner's
  administrator, so it names that provisioner's administrator secret. A release
  reading `stop_request` skips an entry whose protocol it does not know, and
  earlier ones ignore the field.
- `runtime.buckets` (`protocol`, `gateway_label`) says an entry holds the
  buckets a group declares under its service, behind a gateway at
  `<gateway_label>.<group>.<tld>`; `s3` is the one protocol, a release skips an
  entry naming another, and earlier ones ignore the field and decide by the
  `s3` type. The label is a lowercase DNS label of 2 to 32 characters other than
  the entry's `hostname` label, and must stay `s3` on the `s3` type, which
  Stack's `stack.yaml` grammar and a Stack test assume. `gateway_label` names the gateway alone: published buckets answer on
  `<bucket>.s3.<group>.<tld>` whatever the label, because that `s3` suffix is a
  persisted Stack contract, and a site may take neither name in a group
  declaring such an entry. Its optional
  `laravel_variable` names the variable Laravel sites receive the storage name
  of the group's first bucket in (S3's `AWS_BUCKET`). It is a field of its own,
  never a `laravel_connection` template: releases before it expand no bucket
  placeholder, and 2.25.0 and 2.25.1 would hand one to Laravel sites as written,
  while 2.26.0 to 2.28.0 set S3's `AWS_BUCKET` themselves.
- `aliases` lists other types a `stack.yaml` may write for an entry's type
  while no entry has that type of its own; the first source claiming an alias
  keeps it. Valkey's is `redis`. An alias is a hostname label, never the
  entry's own type, a type the catalogue offers or another type's alias.
- A new `provisioner`, stop protocol or archive format needs a Stack release
  that implements it before the entry is published. For a provisioner or
  format, Stack 2.11.0 and later skip such an entry with a warning; 2.10.0 and
  earlier refuse every service and command once their catalogue holds one.
- `runtime.ports`, `runtime.hostname` and `runtime.laravel_connection` need
  Stack 2.25.1. Earlier releases ignore them, so an entry using them must fail
  to start there, as Mailpit's does with `${STACK_PORT_HTTP:?}` and
  `${STACK_HOSTNAMES:?}`, rather than bind a port nobody allocated; publish such
  an entry only after that release.
- `runtime.extend` (`mechanism`, `syntax`, `suffix`, `directory_variable`,
  an optional `base` with a `variable` and a `file`, and `reserved` with a `key`
  and a `reason` each) on a runtime says which configuration files a project
  may list in a pin and how Stack layers them with `scan_dir`: the files and
  Stack's own go into a directory
  `directory_variable` names, and `base.variable` names a directory holding an
  empty `base.file`, so no copy installed on the machine applies. A top-level
  `documentation` links the vendor's reference for them, with `{major}`
  available for a versioned manual. Of the runtimes only PHP declares one
  (`scan_dir`, `ini`, `.ini`, `PHP_INI_SCAN_DIR`, base `PHPRC` and
  `php.ini`), reserving the trust-bundle keys Stack sets; `scan_dir` takes
  none of a service mechanism's `file`, `engine_file`, `settings_file`,
  `arguments` or `windows_append`. Variable names are a letter or underscore
  followed by letters, digits or underscores; `base.file` is one file name
  ending in the suffix; the entry's type is a lowercase letter followed by
  lowercase letters, digits, underscores or hyphens, because it names the
  directory. Releases that do not read `extend` ignore both fields;
  a new mechanism or syntax needs a Stack release that implements it before an
  entry using it is published, like a provisioner.
  Every text Stack prints (type, version, description, category, commands,
  platforms, reasons, documentation links, connection variable names) holds
  only printable characters, and a reserved `reason` is at most 200 characters.
  A `reason` is a predicate whose subject is the key, because Stack prints it
  as "Stack's <key>, read last, <reason>".
- `runtime.trust` hands a runtime Stack's trust bundle. `bundle` is `replace`
  (the system's roots and Stack's, for a setting that replaces a runtime's
  own roots) or `add` (the certificates the variable already names and
  Stack's); `settings` names keys Stack writes into its own file of the
  entry's `extend` layering, `variable` an environment variable a site
  receives, and `serves` the site kinds (`vite`, `nuxt`, `next`, …) that get
  the variable without pinning the runtime; a proxy site pinning it gets it
  too. PHP declares `replace` with `openssl.cafile` and `curl.cainfo`, Node
  `add` with `NODE_EXTRA_CA_CERTS` serving Vite, Nuxt and Next, and Bun `add`
  with the same variable. A variable, like `buckets.laravel_variable`, is never
  `PATH`, a shell or loader variable, a `STACK_*` name or one of the entry's
  connection or secret names, in any case; connection names follow the same
  rule apart from the entry's own names. `add` takes a variable and no settings, `serves`
  needs a variable, and a new `bundle` mode needs a Stack release that
  implements it before an entry using it is published.
- `runtime.site_server` is the application server Stack runs for each site of
  the kinds it `serves` from the runtime the site pins. PHP declares PHP-FPM
  for `php` and `laravel` over `fastcgi`, with its pool template in `config`
  (marked by `marker`, listening on `${STACK_LISTEN}`), Unix `arguments`
  naming `${STACK_CONFIG}` and `${STACK_PID_FILE}`, the `image_process` and
  `image_arguments` a container runs, the `split_path` and `index` its route
  uses, and `windows` arguments and environment for `php-cgi`. An image's
  `processes` hold only `shell` and that `image_process`. PHP's container
  also states `settings_directory`, where its image reads Stack's trust
  settings, and `server_arguments`, which start the image's own PHP-FPM under
  Docker. `resolve: "image"` resolves a version the catalogue lacks from its
  image alone. A new `protocol` or `resolve` value needs a Stack release that
  implements it before an entry using it is published.
- `resolver` names how Stack reads the releases of a family the catalogue
  lacks from their publisher: `nodejs.org`, `go.dev`,
  `github.com/oven-sh/bun`, `github.com/pnpm/pnpm` and `getcomposer.org`.
  The family's newest entry decides; a family declaring none resolves no
  vendor release, and an unknown name skips the entry as one for a newer Stack.
- `runtime.shareable` marks an entry whose one instance keeps each group's data
  apart behind its own credentials; Stack refuses `shared:` for any other. Only
  PostgreSQL, S3, MongoDB and NATS set it.
- The NATS entry selects `provisioner: nats` and has no `initialise`: Stack writes
  `accounts.conf` itself, so the entry must keep `NATS_ADMIN_PASSWORD`,
  `NATS_PASSWORD` and `initialised_marker`, and its start command must include
  `./accounts.conf` from the `nats.conf` it writes, which is also its
  `extend.settings_file`. On Windows, whose `start`
  runs without a shell, its Windows `initialise` writes that `nats.conf` once,
  before Stack writes the accounts; it has no Windows `stop`, since
  nats-server takes stop requests there only from the service manager.
- The MongoDB entry selects `provisioner: mongodb` and has no `initialise`: Stack
  creates the administrator and group accounts itself, so the entry must keep
  `MONGODB_ADMIN_PASSWORD`, `MONGODB_PASSWORD` and `initialised_marker`. Its
  explicit-database templates live in `provisioned_database_connection`, never
  `database_connection`: Stack 2.11 and 2.12 refuse the latter outside PostgreSQL
  and stop selecting every service, while ignoring a field they do not know.
  Windows has only MongoDB's x64 build, also listed under `windows/arm64`,
  keeping only `bin/mongod.exe`; its Windows `start` has no socket arguments,
  because mongod offers none there, and no `stop`: its `stop_request` is
  `mongodb` with `MONGODB_ADMIN_PASSWORD`.
- Valkey locks its `default` user with `VALKEY_ADMIN_PASSWORD` in a private
  `users.acl` and provisions one ACL account per group from `REDIS_PASSWORD`
  through `valkey-cli` stdin with `VALKEYCLI_AUTH`, never argv. Provisioning
  compares the exact `OK` replies, because `-e` does not fail on stdin errors.
  `initialised_marker: users.acl` lets its Windows `initialise` write that file
  once, since the Windows start runs without the shell that writes it on Unix;
  Stack consults the marker only to decide whether to initialise. Windows takes
  the foundry's MSYS2 build (`valkey-<version>-windows`), x64 under both
  Windows platforms, and has no Windows `stop`: its `stop_request` is `resp`
  with `VALKEY_ADMIN_PASSWORD`.
- PostgreSQL uses SCRAM for TCP and Unix sockets, a reserved administrator,
  per-group passwords and a `pgdata` cluster directory. Connection templates may
  interpolate only declared group secrets. S3 publishing declares both policy
  and ACL ownership attributes. Stack's `internal/service/AGENTS.md` documents
  the matching consumer contracts.
- A runtime is verified after installation by running its first command with
  `runtime.version_arguments`, `--version` when absent. Go declares `version`.
  That command is the runtime's own name everywhere but Rust, whose first is
  `cargo`; Stack releases before that ran a command named after the type.
- `runtime.commands` is everything an entry can put in a shell and
  `runtime.exposed` is which of them every pin gets; the rest are opt-in per
  repository, so pinning Node does not hand somebody three package managers.
  Exposed names must be among the commands, and `build.py` refuses a runtime
  offering several commands that does not say. An entry naming none exposes all
  of them, which keeps an older catalogue working.
- Every downloadable artifact requires an HTTPS URL and a pinned lowercase
  `sha256` or `sha512` digest, and every image digest is `sha256`; `build.py`
  refuses an entry without them. Changes to runtime commands must not silently
  alter artifact URLs, digests or versions.
- A service runs on Windows only through `runtime.windows`, which published
  Stack releases ignore: `start` and `stop` are `{"arguments": [...]}` run
  without a shell, each argument naming the environment only as `${NAME}`
  (`$$` for a literal `$`), `stop` also sees `${STACK_PID}`, `restricted:
  true` runs a server that refuses administrators under a restricted token,
  and `initialise` replaces the shared script there. Other scripts (`ready`,
  `provision`) stay shared and run under the pinned BusyBox, so they must not
  rely on `/dev/stdin` or `umask`, which it does not emulate. A Windows
  artifact may be the x64 build under `windows/arm64` when the vendor ships no
  ARM64 one. `sidecar` names where a store's gateway keeps each store's
  metadata there, `<root>/<store>/meta/<name>`, with the files standing for
  `published.attribute` and `ownership_attribute`: S3 runs versitygw with
  `--sidecar`, since it refuses to start without extended attributes.
  `bin_dir` replaces a runtime's `bin_dir` there, for a Windows build that keeps
  its commands elsewhere: Node's zip keeps `node.exe` and `npm.cmd` at its root.
  `exposed` replaces a runtime's `exposed` there, for a Windows build naming
  its commands differently: Python's has `python.exe` and no `python3`.
  `run_with` names the program that runs a runtime's commands there, for
  scripts Unix runs by their `#!` line: installing Composer writes
  `composer.cmd`, handing `composer` to `php`.
- Ruby's macOS and Linux builds come from jdx/ruby, whose `<version>` release
  floats to its newest rebuild. Pin the build revision release,
  `<version>-<revision>`, whose bytes do not change, in each release's own URL,
  and take a new revision only after `gh attestation verify --repo jdx/ruby`
  accepts its archives.
- The internal `busybox` entry `provides: "posix-shell"`, the shell Stack
  runs commands with on Windows, found by what it provides and run as
  `<type>.exe sh -c`; it offers only Windows builds. Stack takes a provider
  only from the official catalogue. Take its digests from frippery.org's
  `SHA256SUM` only after `SHA256SUM.sig` verifies against the author's key,
  then mirror that release with the foundry's `busybox-windows.yml` and point
  the entry at `busybox-w32-<release>` there: frippery.org refuses some
  networks outright, and deletes builds about three years old.
- Never publish, stage, commit or modify real service data without explicit
  authorization.
