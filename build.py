#!/usr/bin/env python3
"""Joins every file under entries/ into the one catalogue that gets served.

The tool fetches a single URL: it cannot walk a directory, so the combined file
has to exist and be committed. Keeping it generated rather than hand-written is
what stops it drifting from its sources, and the check workflow regenerates it
and fails if the committed one differs.

A type's versions repeat almost everything about each other, so a file may put
what they share in "defaults" and leave each version saying only what is its
own, and a type's platforms repeat how the download is unpacked, which goes in
"defaults.every_platform". Both are expanded here and neither leaves: the served
file stays the flat list of whole entries every binary already understands.
"""

import json
import sys
from pathlib import Path

ENTRIES = Path("entries")
# Versioned in the path, not only in the document. A binary reads the URL it was
# built with, so the day the format changes incompatibly the old ones have to
# keep finding a file they understand.
OUTPUT = Path("v1.json")
# What a shared URL says instead of the version it is missing. Expanded only in
# values coming from "defaults": a version that writes its own URL writes it
# whole, and what is served is always the literal URL its digest was taken from.
PLACEHOLDER = "{version}"
# artifacts and runtime are one level under an entry, and their platforms and
# fields one more. Deeper than that lies a digest, and a checksum inherited
# field by field is how a version quietly ends up claiming another's bytes.
DEPTH = 2
# What an entry reads like, so the served file has one shape whatever order a
# source file happened to use: what it is, then which release, then what to
# download. This decides reading order and nothing else, and a key it does not
# name keeps its place after these.
ORDER = ["type", "kind", "category", "support", "version", "description",
         "artifacts", "runtime", "lifecycle"]
# The same for one platform's build: what is downloaded, what it has to hash to,
# and then how it is unpacked.
ARTIFACT_ORDER = ["url", "digest", "archive", "paths", "strip"]
# What every platform's build is told, unless that platform says otherwise. It
# sits beside "artifacts" rather than inside it, so no platform key can ever be
# mistaken for it.
EVERY_PLATFORM = "every_platform"
# What a release has to assert for itself. A default is inherited in silence,
# and every one of these is a claim about one release rather than about the type:
# which release it is, what its bytes hash to, and whether anybody still fixes
# it. An inherited support status is the worst of them, because the generated
# file then always carries one and the checks downstream see nothing missing.
PER_RELEASE = ["version", "digest", "support", "lifecycle"]
# What a release on its own may state. With no second version to differ from,
# every other field is a fact about the type, and a file that keeps them beside
# the release reads differently from every file that has two.
RELEASE_FIELDS = ["version", "support", "lifecycle", "description", "artifacts", "image"]


def expand(value, version):
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, version)
    if isinstance(value, list):
        return [expand(item, version) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, version) for key, item in value.items()}
    return value


def merge(defaults, entry, depth):
    merged = dict(defaults)
    for key, value in entry.items():
        shared = merged.get(key)
        if depth > 0 and isinstance(value, dict) and isinstance(shared, dict):
            merged[key] = merge(shared, value, depth - 1)
        else:
            merged[key] = value
    return merged


def ordered(order, entry):
    named = [key for key in order if key in entry]
    return {key: entry[key] for key in named + [key for key in entry if key not in named]}


def in_order(entry):
    entry = ordered(ORDER, entry)
    if isinstance(entry.get("artifacts"), dict):
        entry["artifacts"] = {platform: ordered(ARTIFACT_ORDER, artifact)
                              for platform, artifact in entry["artifacts"].items()}
    return entry


def carries(value, name):
    if isinstance(value, dict):
        return name in value or any(carries(item, name) for item in value.values())
    if isinstance(value, list):
        return any(carries(item, name) for item in value)
    return False


def problems_with(defaults, source):
    problems = []
    for name in PER_RELEASE:
        if carries(defaults, name):
            problems.append(
                f"{source}: defaults carries {name}, which each release states for itself")
    return problems


def alike(values):
    return len({json.dumps(value, sort_keys=True) for value in values}) == 1


def written_twice(entries, skip):
    """Fields every one of these states, and states identically."""
    if len(entries) < 2:
        return []
    shared = []
    for field in sorted({field for entry in entries for field in entry}):
        # What may not be shared may be repeated, so it is not worth reporting.
        if field in PER_RELEASE or field in skip:
            continue
        if all(field in entry for entry in entries) and alike(
                [entry[field] for entry in entries]):
            shared.append(field)
    return shared


def out_of_place(document, source):
    """Type-wide fields a single-release file left beside its release."""
    services = document["services"]
    if len(services) != 1:
        return []

    problems = []
    for key in sorted(services[0]):
        if key not in RELEASE_FIELDS:
            problems.append(f"{source}: the only release states {key!r}, which describes "
                            "the type and belongs in defaults")
    for platform, artifact in sorted(services[0].get("artifacts", {}).items()):
        for field in sorted(artifact):
            if field != "digest":
                problems.append(f"{source}: the only release states {field!r} for {platform}, "
                                "which belongs in defaults")
    return problems


def unexposed(entry, source):
    """A runtime offering several commands has to say which a pin gets."""
    runtime = entry.get("runtime") or {}
    if entry.get("kind") != "runtime" or len(runtime.get("commands") or []) < 2:
        return []
    if runtime.get("exposed"):
        return []
    return [f"{source}: {entry.get('type')} offers several commands and does not say "
            "which of them every pin gets; name them in runtime.exposed"]


def repeats(document, source):
    """What a file says more than once and has somewhere to say once.

    Left to a reviewer this drifts: the file that gets a second version keeps
    the shape it had, and the one nobody touched keeps writing its archive
    layout three times. Nothing here is a matter of taste, because the fields
    that must stay per release are the ones this skips.
    """
    problems = []
    services = document["services"]

    for field in written_twice(services, ("artifacts", "runtime")):
        problems.append(f"{source}: every version repeats {field!r}, which defaults can say once")
    for field in written_twice([service.get("runtime", {}) for service in services], ()):
        problems.append(
            f"{source}: every version repeats runtime.{field}, which defaults can say once")

    platforms = [("defaults", document.get("defaults", {}).get("artifacts", {}))]
    platforms += [(service.get("version"), service.get("artifacts", {})) for service in services]
    for where, artifacts in platforms:
        for field in written_twice(list(artifacts.values()), ()):
            problems.append(f"{source}: every platform of {where} repeats {field!r}, "
                            "which every_platform can say once")
    return problems


def main() -> int:
    sources = sorted(ENTRIES.rglob("*.json"))
    if not sources:
        print("entries/ holds nothing", file=sys.stderr)
        return 1

    services = []
    seen = {}
    for source in sources:
        document = json.loads(source.read_text())
        defaults = document.get("defaults", {})

        problems = (problems_with(defaults, source) + repeats(document, source)
                    + out_of_place(document, source))
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1

        for entry in document.get("services", []):
            version = entry.get("version")
            if defaults and not version:
                print(f"{source}: an entry has no version to expand its defaults with",
                      file=sys.stderr)
                return 1

            if defaults:
                shared = expand(defaults, version)
                platform_wide = shared.pop(EVERY_PLATFORM, {})
                entry = merge(shared, entry, DEPTH)
                if platform_wide:
                    entry["artifacts"] = {
                        platform: merge(platform_wide, artifact, 0)
                        for platform, artifact in entry.get("artifacts", {}).items()}
            entry = in_order(entry)

            problems = unexposed(entry, source)
            for problem in problems:
                print(problem, file=sys.stderr)
            if problems:
                return 1

            name = f"{entry.get('type')}-{version}"
            if name in seen:
                print(f"{name} is in both {seen[name]} and {source}", file=sys.stderr)
                return 1
            seen[name] = source
            services.append(entry)

    combined = {
        "version": 1,
        # Named so whoever opens this knows not to edit it here. There are no
        # comments in JSON, and a generated file that does not say so gets
        # edited by somebody eventually.
        "generated_from": [str(source) for source in sources],
        "services": services,
    }

    rendered = json.dumps(combined, indent=2) + "\n"
    if OUTPUT.exists() and OUTPUT.read_text() == rendered:
        print(f"{OUTPUT} is up to date: {len(services)} entries")
        return 0

    OUTPUT.write_text(rendered)
    print(f"wrote {OUTPUT}: {len(services)} entries from {len(sources)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
