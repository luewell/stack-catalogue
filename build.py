#!/usr/bin/env python3
"""Joins every file under entries/ into the one catalogue that gets served.

The tool fetches a single URL: it cannot walk a directory, so the combined file
has to exist and be committed. Keeping it generated rather than hand-written is
what stops it drifting from its sources, and the check workflow regenerates it
and fails if the committed one differs.
"""

import json
import sys
from pathlib import Path

ENTRIES = Path("entries")
# Versioned in the path, not only in the document. A binary reads the URL it was
# built with, so the day the format changes incompatibly the old ones have to
# keep finding a file they understand.
OUTPUT = Path("v1.json")


def main() -> int:
    sources = sorted(ENTRIES.rglob("*.json"))
    if not sources:
        print("entries/ holds nothing", file=sys.stderr)
        return 1

    services = []
    seen = {}
    for source in sources:
        document = json.loads(source.read_text())
        for entry in document.get("services", []):
            name = f"{entry.get('type')}-{entry.get('version')}"
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
