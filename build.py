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

Several scripts of one type share the same shell functions and checks, so a
file may name each once under "snippets" and have a script take it in with a
line holding only {snippet:<name>}. Those are inserted here too.

Each file under entries/tunnels/ is one tunnel adapter that "stack share" can
run. They are checked here as Stack checks them and served, in file order,
under "tunnels", which binaries older than the field ignore.
"""

import json
import re
import sys
from pathlib import Path

ENTRIES = Path("entries")
# Versioned in the path, not only in the document. A binary reads the URL it was
# built with, so the day the format changes incompatibly the old ones have to
# keep finding a file they understand.
OUTPUT = Path("v1.json")
# Raised when Stack drops code that a declaration replaced.
GENERATION = 7
# What a shared URL says instead of the version it is missing. Expanded only in
# values coming from "defaults": a version that writes its own URL writes it
# whole, and what is served is always the literal URL its digest was taken from.
PLACEHOLDER = "{version}"
# A script line that is only this takes in the snippet it names. A whole line,
# so a snippet keeps its own indentation and never lands inside a statement.
SNIPPET_LINE = re.compile(r"\{snippet:([a-z0-9-]+)\}")
SNIPPET_MARK = "{snippet:"
# artifacts and runtime are one level under an entry, and their platforms and
# fields one more. Deeper than that lies a digest, and a checksum inherited
# field by field is how a version quietly ends up claiming another's bytes.
DEPTH = 2
# What an entry reads like, so the served file has one shape whatever order a
# source file happened to use: what it is, then which release, then what to
# download. This decides reading order and nothing else, and a key it does not
# name keeps its place after these.
# Help indents a recipe by 4 and stays within 96 columns (catalogue.RecipeLineWidth).
RECIPE_LINE_WIDTH = 92

ORDER = ["type", "kind", "category", "summary", "support", "version", "description",
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
# The digests a machine can recompute, and how many lowercase hexadecimal
# characters each is written with. An image is pinned by its registry digest,
# which is always sha256.
DIGEST_LENGTHS = {"sha256": 64, "sha512": 128}
ARTIFACT_ALGORITHMS = ("sha256", "sha512")
IMAGE_ALGORITHMS = ("sha256",)

TUNNELS = ENTRIES / "tunnels"
# The capability every adapter requires, so one written for a later contract
# names another and an older Stack skips it (catalogue.CapabilityTunnel).
TUNNEL_CAPABILITY = "tunnel_v1"
TUNNEL_PLATFORMS = ("darwin", "linux", "windows")
TUNNEL_PLACEHOLDERS = ("STACK_SHARE_ORIGIN", "STACK_SHARE_METRICS", "STACK_SHARE_DIR")
TUNNEL_INSTALL_PLACEHOLDER = "STACK_INSTALL_DIR"
TUNNEL_METRICS = "${STACK_SHARE_METRICS}"
TUNNEL_NAME = re.compile(r"[a-z][a-z0-9-]{0,31}")
TUNNEL_SETTING_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
TUNNEL_FILE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
TUNNEL_PROGRAM_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
TUNNEL_HTTP_PATH = re.compile(r"/[A-Za-z0-9._~/-]{0,127}")
TUNNEL_JSON_FIELD = re.compile(r"[A-Za-z0-9_]{1,64}")
TUNNEL_REFERENCE = re.compile(r"\$(\$|\{([A-Za-z_][A-Za-z0-9_]*)\})")
HOSTNAME_LABEL = re.compile(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?")
NOTE_NAME = re.compile(r"[a-z]+(_[a-z]+)*")
# Stack compiles patterns with Go's RE2, which has none of these.
RE2_MISSING = re.compile(r"\(\?(=|!|<=|<!|>|P=|\()|\\[1-9]")
# A field's shape: a type, [shape] for a list of them, {"*": shape} for an
# object of any keys, or the fields an object may have.
TUNNEL_SETTING_SHAPE = {"name": str, "summary": str, "required": bool, "default": str,
                        "pattern": str, "choices": [str], "hostname": bool, "path": bool}
TUNNEL_MODE_SHAPE = {"name": str, "summary": str, "default": bool,
                     "settings": [TUNNEL_SETTING_SHAPE],
                     "files": [{"name": str, "content": str}], "arguments": [str],
                     "ready": {"http": str, "output": str},
                     "url": {"http": str, "json": str, "output": str, "setting": str},
                     "host_suffix": str}
TUNNEL_SHAPE = {"name": str, "summary": str, "default": bool, "requires": [str],
                "notes": [{"name": str, "text": str}],
                "executable": {"install": str, "system": [str], "paths": {"*": [str]}},
                "modes": [TUNNEL_MODE_SHAPE]}
SHAPE_NAMES = {str: "a string", bool: "true or false"}


def expand(value, version):
    if isinstance(value, str):
        return value.replace(PLACEHOLDER, version)
    if isinstance(value, list):
        return [expand(item, version) for item in value]
    if isinstance(value, dict):
        return {key: expand(item, version) for key, item in value.items()}
    return value


def with_snippets(value, snippets, used, problems, source):
    """value with every snippet line replaced by the snippet it names."""
    if isinstance(value, list):
        return [with_snippets(item, snippets, used, problems, source) for item in value]
    if isinstance(value, dict):
        return {key: with_snippets(item, snippets, used, problems, source)
                for key, item in value.items()}
    if not isinstance(value, str) or SNIPPET_MARK not in value:
        return value

    lines = []
    for line in value.split("\n"):
        reference = SNIPPET_LINE.fullmatch(line)
        if reference is None:
            if SNIPPET_MARK in line:
                problems.append(f"{source}: {line.strip()!r} is not a snippet line of its own")
            lines.append(line)
        elif reference.group(1) not in snippets:
            problems.append(f"{source}: no snippet is named {reference.group(1)!r}")
        else:
            used.add(reference.group(1))
            lines.append(snippets[reference.group(1)].removesuffix("\n"))
    return "\n".join(lines)


def insert_snippets(document, source):
    """The document without its snippets, each inserted where a script names it."""
    snippets = document.get("snippets", {})
    problems = []
    if not isinstance(snippets, dict) or not all(
            isinstance(text, str) and text.strip() for text in snippets.values()):
        return document, [f"{source}: snippets has to map each name to the text it stands for"]
    for name, text in sorted(snippets.items()):
        if not re.fullmatch("[a-z0-9-]+", name):
            problems.append(f"{source}: snippet {name!r} is not named in lowercase kebab-case")
        if SNIPPET_MARK in text:
            problems.append(f"{source}: snippet {name!r} names another snippet")

    used = set()
    body = {key: value for key, value in document.items() if key != "snippets"}
    body = with_snippets(body, snippets, used, problems, source)
    for name in sorted(snippets.keys() - used):
        problems.append(f"{source}: no script takes in snippet {name!r}")
    return body, problems


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


def help_problems(defaults, source):
    """A declarable type's one-line purpose and recipes, which help prints raw."""
    if defaults.get("kind") == "internal":
        return []
    problems = []
    summary = defaults.get("summary")
    if not isinstance(summary, str) or not summary.strip() or "\n" in summary:
        problems.append(f"{source}: defaults has no one-line summary of what the type is for")
    elif not ascii_printable(summary):
        problems.append(f"{source}: its summary holds a character other than printable ASCII")
    for recipe in defaults.get("recipes", []):
        if sorted(recipe) != ["gives", "title", "yaml"] or not all(
                isinstance(value, str) and value.strip() for value in recipe.values()):
            problems.append(f"{source}: a recipe needs a title, its yaml and what it gives")
            continue
        if not ascii_printable(recipe["title"]) or not ascii_printable(recipe["gives"]):
            problems.append(
                f"{source}: recipe {recipe['title']!r} holds a character other than printable ASCII")
        for line in recipe["yaml"].rstrip("\n").split("\n"):
            if not ascii_printable(line):
                problems.append(f"{source}: a line of recipe {recipe['title']!r} holds a "
                                "character other than printable ASCII")
            elif len(line) > RECIPE_LINE_WIDTH:
                problems.append(f"{source}: a line of recipe {recipe['title']!r} is wider than "
                                f"{RECIPE_LINE_WIDTH} characters, which help cannot wrap")
    return problems


def ascii_printable(text):
    return all(" " <= character <= "~" for character in text)


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


def excluded(document, source):
    """Platforms a release leaves out, written as null under its artifacts.

    Only a platform the defaults offer can be left out, and one every release
    leaves out is one the defaults should not offer.
    """
    offered = document.get("defaults", {}).get("artifacts", {})
    services = document["services"]
    problems = []
    left_out = []

    for service in services:
        omitted = {platform for platform, artifact in (service.get("artifacts") or {}).items()
                   if artifact is None}
        left_out.append(omitted)
        for platform in sorted(omitted - offered.keys()):
            problems.append(f"{source}: {service.get('version')} leaves out {platform}, "
                            "which its defaults do not offer")

    for platform in sorted(set.intersection(*left_out) if left_out else set()):
        problems.append(f"{source}: every version leaves out {platform}, "
                        "which defaults should not offer")
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


def digest_problem(digest, algorithms):
    """Why a digest cannot check what it pins, or None when it can."""
    if not isinstance(digest, dict) or not digest.get("algorithm") or not digest.get("value"):
        return "has no digest, and a download nobody can check is not something to run"

    algorithm = digest["algorithm"]
    if algorithm not in algorithms:
        return f"names digest algorithm {algorithm!r}, which is not {' or '.join(algorithms)}"

    length = DIGEST_LENGTHS[algorithm]
    value = digest["value"]
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-f]{{{length}}}", value):
        return f"has a {algorithm} digest that is not {length} lowercase hexadecimal characters"
    return None


def unverifiable(entry, source):
    """Builds a machine could not check, and images it could not pin."""
    name = f"{entry.get('type')}-{entry.get('version')}"
    problems = []

    for platform, artifact in sorted((entry.get("artifacts") or {}).items()):
        url = artifact.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            problems.append(f"{source}: {name} {platform} is not fetched over https")

        reason = digest_problem(artifact.get("digest"), ARTIFACT_ALGORITHMS)
        if reason:
            problems.append(f"{source}: {name} {platform} {reason}")

    image = entry.get("image")
    if image is not None:
        pinned = [("image index", image.get("digest"))]
        pinned += [(f"{platform} image", digest)
                   for platform, digest in sorted((image.get("platforms") or {}).items())]
        for what, digest in pinned:
            reason = digest_problem(digest, IMAGE_ALGORITHMS)
            if reason:
                problems.append(f"{source}: {name} {what} {reason}")
    return problems


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
        built = [artifact for artifact in artifacts.values() if artifact is not None]
        for field in written_twice(built, ()):
            problems.append(f"{source}: every platform of {where} repeats {field!r}, "
                            "which every_platform can say once")
    return problems


def is_hostname(name, labels=1):
    parts = name.split(".")
    return (len(name) <= 253 and len(parts) >= labels
            and all(HOSTNAME_LABEL.fullmatch(part) for part in parts))


def compiles(pattern):
    """Whether both Python and Go's RE2 accept the pattern, as far as a scan tells."""
    try:
        re.compile(pattern)
    except (re.error, TypeError):
        return False
    outside_classes = re.sub(r"\\[^1-9]|\[\^?\]?(\\.|[^\]])*\]", "", pattern)
    return RE2_MISSING.search(outside_classes) is None


def shape_problems(value, shape, where):
    if isinstance(shape, type):
        if not isinstance(value, shape):
            return [f"{where} is not {SHAPE_NAMES[shape]}"]
        return []
    if isinstance(shape, list):
        if not isinstance(value, list):
            return [f"{where} is not a list"]
        return [problem for position, item in enumerate(value)
                for problem in shape_problems(item, shape[0], f"{where}[{position}]")]
    if not isinstance(value, dict):
        return [f"{where} is not an object"]
    if "*" in shape:
        return [problem for key, item in sorted(value.items())
                for problem in shape_problems(item, shape["*"], f"{where}.{key}")]
    problems = [f"{where} has an unknown field {key!r}"
                for key in sorted(value.keys() - shape.keys())]
    for key, field_shape in shape.items():
        if key in value:
            problems += shape_problems(value[key], field_shape, f"{where}.{key}")
    return problems


def printable_line(text, required=True):
    if not isinstance(text, str):
        return False
    if not text:
        return not required
    return len(text) <= 200 and ascii_printable(text)


def template_problem(text, known):
    """Why a template names something other than a known placeholder, or None."""
    if not isinstance(text, str):
        return "is not a string"
    for match in TUNNEL_REFERENCE.finditer(text):
        if match.group(2) is not None and match.group(2) not in known:
            return f"names {match.group(2)}, which is not a placeholder it may use"
    if "$" in TUNNEL_REFERENCE.sub("", text):
        return "uses $ other than as ${NAME} or $$"
    return None


def setting_accepts(setting, value):
    if not isinstance(value, str) or not value or not ascii_printable(value):
        return False
    if "pattern" in setting:
        return re.fullmatch(setting["pattern"], value) is not None
    if "choices" in setting:
        return value in setting["choices"]
    if setting.get("hostname"):
        return is_hostname(value, labels=2)
    return value.startswith("/") and not any(quote in value for quote in "'\"")


def setting_problems(setting, where):
    problems = []
    kinds = [kind for kind in ("pattern", "choices", "hostname", "path") if setting.get(kind)]
    if not TUNNEL_SETTING_NAME.fullmatch(str(setting.get("name", ""))):
        problems.append(f"{where} is not named in lowercase letters, digits and underscores")
    if not printable_line(setting.get("summary", ""), required=False):
        problems.append(f"{where} has a summary that is not one printable line")
    if len(kinds) != 1:
        problems.append(f"{where} does not declare exactly one of pattern, choices, hostname and path")
    elif "pattern" in setting and not compiles(setting["pattern"]):
        problems.append(f"{where} has a pattern that does not compile, or uses what RE2 lacks")
    elif "choices" in setting and not all(
            isinstance(choice, str) and choice and ascii_printable(choice) for choice in setting["choices"]):
        problems.append(f"{where} offers an empty or unprintable choice")
    elif "default" in setting and not setting_accepts(setting, setting["default"]):
        problems.append(f"{where} has a default it does not accept")
    return problems


def executable_problems(executable, where, internal_types):
    problems = []
    installed = executable.get("install")
    system = executable.get("system") or executable.get("paths")
    if bool(installed) == bool(system):
        return [f"{where} is not exactly one of an installed type and system programs"]
    if installed:
        if installed not in internal_types:
            problems.append(f"{where} installs {installed!r}, which no internal entry offers")
        return problems

    for name in executable.get("system", []):
        if not TUNNEL_PROGRAM_NAME.fullmatch(str(name)):
            problems.append(f"{where} names {name!r}, which is not a program name")
    for platform, paths in sorted(executable.get("paths", {}).items()):
        if platform not in TUNNEL_PLATFORMS:
            problems.append(f"{where} names the platform {platform!r}")
            continue
        for path in paths:
            separator = "\\" if platform == "windows" else "/"
            absolute = (re.match(r"[A-Za-z]:\\", path) if platform == "windows"
                        else path.startswith("/"))
            if (not absolute or not ascii_printable(path)
                    or any(part in (".", "..") for part in path.split(separator))
                    or not TUNNEL_PROGRAM_NAME.fullmatch(path.rsplit(separator, 1)[-1])):
                problems.append(f"{where} has the {platform} path {path!r}, which is not a clean "
                                "absolute path to a program")
    return problems


def mode_problems(mode, where, installed):
    problems = []
    if not TUNNEL_NAME.fullmatch(str(mode.get("name", ""))):
        problems.append(f"{where} is not named in lowercase letters, digits and hyphens")
    if not printable_line(mode.get("summary", ""), required=False):
        problems.append(f"{where} has a summary that is not one printable line")

    settings = mode.get("settings", [])
    names = [setting.get("name") for setting in settings]
    if len(settings) > 16 or len(set(names)) != len(settings):
        problems.append(f"{where} declares more than 16 settings or one twice")
    for setting in settings:
        problems += setting_problems(setting, f"{where} setting {setting.get('name')!r}")

    known = set(TUNNEL_PLACEHOLDERS) | {"STACK_SHARE_SETTING_" + str(name).upper() for name in names}
    if installed:
        known.add(TUNNEL_INSTALL_PLACEHOLDER)
    arguments = mode.get("arguments", [])
    if not 1 <= len(arguments) <= 64:
        problems.append(f"{where} does not have between 1 and 64 arguments")
        arguments = []
    for argument in arguments:
        reason = template_problem(argument, known)
        if reason:
            problems.append(f"{where} has an argument {argument!r} that {reason}")

    files = mode.get("files", [])
    if len(files) > 8 or len({file.get("name") for file in files}) != len(files):
        problems.append(f"{where} writes more than 8 files or one twice")
    for file in files:
        name, content = file.get("name", ""), file.get("content", "")
        if not TUNNEL_FILE_NAME.fullmatch(str(name)) or name in (".", ".."):
            problems.append(f"{where} writes {name!r}, which is not a plain lowercase file name")
        reason = template_problem(content, known)
        if reason:
            problems.append(f"{where} file {name} {reason}")
        elif len(content) > 64 << 10 or not ascii_printable(content.replace("\n", "")):
            problems.append(f"{where} file {name} is too long or holds a control character")

    metrics = any(TUNNEL_METRICS in argument for argument in arguments) or any(
        TUNNEL_METRICS in str(file.get("content")) for file in files)
    return problems + progress_problems(mode, where, names, metrics)


def progress_problems(mode, where, names, metrics):
    problems = []
    ready = mode.get("ready")
    if ready is not None:
        if bool(ready.get("http")) == bool(ready.get("output")):
            problems.append(f"{where} ready names neither or both of http and output")
        elif ready.get("http") and (not TUNNEL_HTTP_PATH.fullmatch(ready["http"]) or not metrics):
            problems.append(f"{where} ready.http is not a plain path read on STACK_SHARE_METRICS")
        elif ready.get("output") and not compiles(ready["output"]):
            problems.append(f"{where} ready.output does not compile, or uses what RE2 lacks")

    url = mode.get("url", {})
    sources = [source for source in ("http", "output", "setting") if url.get(source)]
    if len(sources) != 1:
        problems.append(f"{where} url is not exactly one of http, output and setting")
    elif bool(url.get("http")) != bool(url.get("json")):
        problems.append(f"{where} url.http and url.json go together")
    elif url.get("http") and (not TUNNEL_HTTP_PATH.fullmatch(url["http"]) or not metrics
                              or not TUNNEL_JSON_FIELD.fullmatch(url["json"])):
        problems.append(f"{where} url.http is not a plain path read on STACK_SHARE_METRICS "
                        "with a plain json field")
    elif url.get("output") and (not compiles(url["output"]) or re.compile(url["output"]).groups != 1):
        problems.append(f"{where} url.output does not compile to a pattern with one group, "
                        "or uses what RE2 lacks")
    elif url.get("setting") and not any(
            setting.get("name") == url["setting"] and setting.get("hostname")
            for setting in mode.get("settings", [])):
        problems.append(f"{where} url.setting does not name a hostname setting")

    suffix = mode.get("host_suffix")
    if suffix is None and not url.get("setting"):
        problems.append(f"{where} has no host_suffix for the hostnames its provider chooses")
    elif suffix is not None and not (isinstance(suffix, str) and suffix.startswith(".")
                                     and is_hostname(suffix[1:], labels=2)):
        problems.append(f"{where} host_suffix is not a dot and a hostname of at least two labels")
    return problems


def tunnel_problems(adapter, source, internal_types):
    """Why Stack would skip an adapter, checked as catalogue/tunnels.go checks it."""
    problems = shape_problems(adapter, TUNNEL_SHAPE, f"{source}: the adapter")
    if problems:
        return problems
    if not TUNNEL_NAME.fullmatch(str(adapter.get("name", ""))):
        problems.append(f"{source}: the name is not lowercase letters, digits and hyphens")
    if source.stem != adapter.get("name"):
        problems.append(f"{source}: the file is not named after the adapter")
    if not printable_line(adapter.get("summary")):
        problems.append(f"{source}: the summary is not one printable line of at most 200 characters")
    if TUNNEL_CAPABILITY not in adapter.get("requires", []):
        problems.append(f"{source}: it does not require {TUNNEL_CAPABILITY}")

    notes = adapter.get("notes", [])
    if len({note.get("name") for note in notes}) != len(notes):
        problems.append(f"{source}: a note is named twice")
    for note in notes:
        name = str(note.get("name", ""))
        if not NOTE_NAME.fullmatch(name) or len(name) > 22 or not printable_line(note.get("text")):
            problems.append(f"{source}: note {name!r} is badly named or not one printable line")

    problems += executable_problems(adapter.get("executable", {}), f"{source}: the executable",
                                    internal_types)
    installed = bool(adapter.get("executable", {}).get("install"))

    modes = adapter.get("modes", [])
    if not 1 <= len(modes) <= 8 or len({mode.get("name") for mode in modes}) != len(modes):
        problems.append(f"{source}: it does not declare between 1 and 8 differently named modes")
    if sum(1 for mode in modes if mode.get("default")) > 1:
        problems.append(f"{source}: more than one mode is the default")
    for mode in modes:
        problems += mode_problems(mode, f"{source}: mode {mode.get('name')!r}", installed)
    return problems


def tunnel_adapters(services):
    internal_types = {service["type"] for service in services if service.get("kind") == "internal"}
    adapters = []
    problems = []
    for source in sorted(TUNNELS.glob("*.json")):
        try:
            adapter = json.loads(source.read_text())
        except json.JSONDecodeError as decode_error:
            problems.append(f"{source}: not JSON: {decode_error}")
            continue
        problems += tunnel_problems(adapter, source, internal_types)
        adapters.append(adapter)
    if problems:
        return adapters, problems
    if sum(1 for adapter in adapters if adapter.get("default")) > 1:
        problems.append(f"{TUNNELS}: more than one adapter is the default")
    return adapters, problems


def main() -> int:
    sources = sorted(source for source in ENTRIES.rglob("*.json") if TUNNELS not in source.parents)
    if not sources:
        print("entries/ holds nothing", file=sys.stderr)
        return 1

    services = []
    seen = {}
    for source in sources:
        try:
            parsed = json.loads(source.read_text())
        except json.JSONDecodeError as decode_error:
            print(f"{source}: not JSON: {decode_error}", file=sys.stderr)
            return 1
        document, problems = insert_snippets(parsed, source)
        for problem in problems:
            print(problem, file=sys.stderr)
        if problems:
            return 1
        defaults = document.get("defaults", {})

        problems = excluded(document, source)
        if not problems:
            problems = (problems_with(defaults, source) + help_problems(defaults, source)
                        + repeats(document, source) + out_of_place(document, source))
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
                entry["artifacts"] = {
                    platform: artifact
                    for platform, artifact in entry.get("artifacts", {}).items()
                    if artifact is not None}
                if platform_wide:
                    entry["artifacts"] = {
                        platform: merge(platform_wide, artifact, 0)
                        for platform, artifact in entry.get("artifacts", {}).items()}
            entry = in_order(entry)

            problems = unexposed(entry, source) + unverifiable(entry, source)
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

    tunnels, problems = tunnel_adapters(services)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    sources += sorted(TUNNELS.glob("*.json"))

    combined = {
        "version": 1,
        "generation": GENERATION,
        # Named so whoever opens this knows not to edit it here. There are no
        # comments in JSON, and a generated file that does not say so gets
        # edited by somebody eventually.
        "generated_from": [str(source) for source in sources],
        "services": services,
        "tunnels": tunnels,
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
