# The stack catalogue

What `stack` can install, beyond what its binary already carries.

A catalogue says what to download and what digest to expect of it, so this
repository decides what runs on every machine that reads it. That is why it is
separate from the one that builds binaries: a release job holds write access to
the repository it publishes into, and the manifest saying which downloads are
trusted should not be somewhere an automated job can rewrite it.

## Using it

There is no default source. A URL nobody chose would be a supply chain nobody
agreed to, so it is named on purpose:

```
stack catalog update --from https://raw.githubusercontent.com/luewell/stack-catalogue/main/catalogue.json
```

What was fetched is cached, so a machine with no network keeps working, and
`stack catalog forget` goes back to the entries the binary shipped with.

## What may go in

An entry **adds** a type or a version. It never replaces one that shipped with
the binary: those were audited alongside it, and a collision keeps the embedded
entry and says so. Publishing one that collides is not an error, but nothing
will use it.

Every build an entry offers needs an `https` URL and a digest with its
algorithm. A download nobody can check is not something to run, and the tool
refuses entries that offer one.

Before committing a change:

```
stack catalog check catalogue.json
```

That applies the same rules the tool applies when it fetches, so a file that
passes here is a file a machine will accept. It also says when an entry is
already shipped and will therefore be ignored.

## What is in here now

PHP versions built by [stack-binaries](https://github.com/luewell/stack-binaries),
which is where anything upstream does not publish gets built. Nobody ships a PHP
carrying `pdo_pgsql` and `pdo_mysql` for these platforms, which is the reason
that foundry exists.

Entries here are the ones newer than the binary in hand. A version already
embedded does not need to be listed.
