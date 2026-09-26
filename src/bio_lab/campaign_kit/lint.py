"""Lints: protocol-to-code consistency, and public hygiene.

    python -m bio_lab.campaign_kit.lint protocol <campaign_dir> [--code code/confirm.py]...
    python -m bio_lab.campaign_kit.lint hygiene --deny-file F [--staged [--repo DIR]] [PATH]...

protocol: registration/protocol.json must carry a "constants" object. In each
linted code file (default code/confirm.py) every module-level UPPER_CASE
literal must be registered there with an equal value; every name read
through load_constants()/constant()/["constants"][...] must be registered;
and a float literal inside a comparison is flagged (name it and register it).
Names listed in protocol "constants_exempt" (name -> reason) are skipped.

hygiene: over files, directories, PR body and commit message files (and with
--staged, the staged blobs): personal paths, names from the private deny
file (one per line, '#' comments, case-insensitive whole words) and files
over 4 MB, in file contents and in file and directory names. Hits are
reported as file:line and kind, never with the matched text, and a file
label that itself holds a deny-list name is printed as a neutral
'<path #n sha256:...>', so the deny list does not leak into logs.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys

from .common import KitError, MAX_PUBLIC_BYTES, PERSONAL_RE, die, read_json

UPPER_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
TRIVIAL_FLOATS = {0.0, 1.0, -1.0}


# ---------------------------------------------------------------- protocol lint

def _same(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, (set, frozenset)) and isinstance(b, (list, tuple)):
        # a set literal matches a registered list of distinct values in any order,
        # compared element by element so True never stands in for 1
        items = list(a)
        return len(items) == len(b) and all(any(_same(x, y) for y in b) for x in items) \
            and all(any(_same(x, y) for x in items) for y in b)
    return type(a) is type(b) and a == b


def _targets(node):
    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
    for target in targets:
        if isinstance(target, ast.Name):
            yield target.id, node.value
        elif isinstance(target, (ast.Tuple, ast.List)) and isinstance(node.value, (ast.Tuple, ast.List)) \
                and len(target.elts) == len(node.value.elts):
            for t, v in zip(target.elts, node.value.elts):
                if isinstance(t, ast.Name):
                    yield t.id, v


def _registered_reads(tree, loaders: set[str]):
    """(name, line) of every constant read by key."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if fname == "constant" and node.args:
                arg = node.args[-1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    yield arg.value, node.lineno
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant) \
                and isinstance(node.slice.value, str):
            base = node.value
            if isinstance(base, ast.Name) and base.id in loaders:
                yield node.slice.value, node.lineno
            elif isinstance(base, ast.Subscript) and isinstance(base.slice, ast.Constant) \
                    and base.slice.value == "constants":
                yield node.slice.value, node.lineno
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and isinstance(node.func.value, ast.Name) \
                and node.func.value.id in loaders and node.args \
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            yield node.args[0].value, node.lineno


def lint_protocol(campaign_dir, code_files=("code/confirm.py",)) -> list[str]:
    """Problems as 'file:line: message'; an empty list means consistent."""
    campaign_dir = Path(campaign_dir)
    protocol = read_json(campaign_dir / "registration" / "protocol.json", "registration/protocol.json")
    constants = protocol.get("constants")
    if not isinstance(constants, dict) or not constants:
        return ["registration/protocol.json: no nonempty \"constants\" object"]
    exempt = protocol.get("constants_exempt") or {}
    if not isinstance(exempt, dict):
        return ["registration/protocol.json: constants_exempt must map names to reasons"]
    problems = []
    for rel in code_files:
        path = campaign_dir / rel
        if not path.is_file():
            problems.append(f"{rel}: missing")
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except SyntaxError as error:
            problems.append(f"{rel}:{error.lineno}: syntax error")
            continue
        loaders = set()
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                continue
            for name, value in _targets(node):
                if isinstance(value, ast.Call):
                    func = value.func
                    fname = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                    if fname == "load_constants":
                        loaders.add(name)
                        continue
                if not UPPER_RE.match(name) or name in exempt:
                    continue
                try:
                    literal = ast.literal_eval(value)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    continue
                if name not in constants:
                    problems.append(f"{rel}:{node.lineno}: {name} is a literal constant not "
                                    "registered in protocol.json constants")
                elif not _same(literal, constants[name]):
                    problems.append(f"{rel}:{node.lineno}: {name} = {literal!r} but protocol.json "
                                    f"registers {constants[name]!r}")
        for name, line in _registered_reads(tree, loaders):
            if name not in constants:
                problems.append(f"{rel}:{line}: reads constant {name}, which protocol.json does "
                                "not register")
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for side in [node.left, *node.comparators]:
                    value = side
                    if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                        value = value.operand
                    if isinstance(value, ast.Constant) and isinstance(value.value, float) \
                            and value.value not in TRIVIAL_FLOATS:
                        problems.append(f"{rel}:{node.lineno}: bare float {value.value!r} in a "
                                        "comparison; register it as a constant")
    return problems


# ---------------------------------------------------------------- hygiene lint

def load_deny(deny_file) -> list[re.Pattern]:
    """Whole-word, case-insensitive patterns from the deny file. Never printed."""
    path = Path(deny_file)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise KitError(f"cannot read the deny file ({error.strerror})") from None
    patterns = []
    for line in lines:
        name = line.strip()
        if not name or name.startswith("#"):
            continue
        body = r"\s+".join(re.escape(part) for part in name.split())
        patterns.append(re.compile(rf"(?<![0-9A-Za-z_]){body}(?![0-9A-Za-z_])", re.IGNORECASE))
    return patterns


def _scan_text(label: str, data: bytes, patterns) -> list[str]:
    """Content hits only, labelled with label as given (the caller makes it safe)."""
    hits = []
    if len(data) > MAX_PUBLIC_BYTES:
        hits.append(f"{label}: file over 4 MB")
    text = data.decode("utf-8", errors="replace")
    for number, line in enumerate(text.splitlines(), 1):
        if PERSONAL_RE.search(line):
            hits.append(f"{label}:{number}: personal path")
        if any(p.search(line) for p in patterns):
            hits.append(f"{label}:{number}: deny-list name")
    # names split across a line break still count
    for pattern in patterns:
        for match in pattern.finditer(text):
            if "\n" in match.group(0):
                hits.append(f"{label}:{text.count(chr(10), 0, match.start()) + 1}: deny-list name")
    return hits


def _deny_match(text: str, patterns) -> bool:
    # path separators and dots split words; a name may also span two path parts
    spaced = re.sub(r"[/\\._-]+", " ", text)
    return any(p.search(text) or p.search(spaced) for p in patterns)


def safe_label(label: str, patterns, index: int) -> str:
    """label, or a neutral '<path #n sha256:...>' when it holds a deny-list name."""
    if _deny_match(label, patterns):
        return f"<path #{index} sha256:{hashlib.sha256(label.encode()).hexdigest()[:12]}>"
    return label


def scan_blob(label: str, checked_path: str, data: bytes, patterns, index: int = 1) -> list[str]:
    """Hygiene hits for one file: its path as it will appear in Git (checked_path) and
    its content. A label that holds a deny-list name is replaced with a neutral one
    before it is printed or raised."""
    shown = safe_label(label, patterns, index)
    hits = []
    if PERSONAL_RE.search(checked_path):
        hits.append(f"{shown}: personal path (file path)")
    if _deny_match(checked_path, patterns):
        hits.append(f"{shown}: deny-list name (file path)")
    return hits + _scan_text(shown, data, patterns)


def _expand(paths, patterns=()) -> list[tuple[Path, str]]:
    """(file, the part of its path that can reach Git) for every file under paths.

    A relative argument keeps its whole path; an absolute one keeps its own name
    and everything below it.
    """
    out = []
    for raw in paths:
        path = Path(raw)
        base = Path() if not path.is_absolute() else path.parent
        if path.is_dir():
            for root, dirs, files in os.walk(path):
                dirs[:] = sorted(d for d in dirs if d not in (".git", "__pycache__", ".pytest_cache"))
                for name in sorted(files):
                    if not name.endswith(".pyc"):
                        full = Path(root) / name
                        out.append((full, full.relative_to(base).as_posix()))
        elif path.is_file():
            out.append((path, path.relative_to(base).as_posix()))
        else:
            raise KitError(f"no such file or directory: {safe_label(str(raw), patterns, 0)}")
    return out


def hygiene_hits(paths, *, deny_file, root=None, staged_repo=None) -> list[str]:
    """Every hygiene hit as 'file:line: kind' or 'file: kind (file path)'.

    File paths are checked as well as contents, and a file label that holds a
    deny-list name is printed as a neutral '<path #n sha256:...>'. deny_file is
    required.
    """
    if deny_file is None:
        raise KitError("the hygiene lint needs --deny-file")
    patterns = load_deny(deny_file)
    hits = []
    index = 0
    for path, checked in _expand(paths, patterns):
        index += 1
        label = str(path)
        if root is not None:
            try:
                label = checked = path.resolve().relative_to(Path(root).resolve()).as_posix()
            except ValueError:
                pass
        hits.extend(scan_blob(label, checked, path.read_bytes(), patterns, index))
    if staged_repo is not None:
        listing = subprocess.run(["git", "-C", str(staged_repo), "diff", "--cached", "--name-only",
                                  "--diff-filter=ACMR", "-z"], capture_output=True, check=False)
        if listing.returncode:
            raise KitError("git could not list the staged files")
        for name in [n for n in listing.stdout.decode().split("\0") if n]:
            index += 1
            blob = subprocess.run(["git", "-C", str(staged_repo), "show", f":{name}"],
                                  capture_output=True, check=False)
            if blob.returncode:
                raise KitError(f"git could not read the staged blob of "
                               f"{safe_label(name, patterns, index)}")
            hits.extend(scan_blob(f"staged:{name}", name, blob.stdout, patterns, index))
    return hits


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.lint", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    proto = sub.add_parser("protocol")
    proto.add_argument("campaign_dir")
    proto.add_argument("--code", action="append", help="campaign-relative code file to lint")
    hyg = sub.add_parser("hygiene")
    hyg.add_argument("paths", nargs="*")
    hyg.add_argument("--deny-file", required=True)
    hyg.add_argument("--staged", action="store_true", help="also lint the staged blobs")
    hyg.add_argument("--repo", default=".", help="repository for --staged")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "protocol":
            problems = lint_protocol(args.campaign_dir, tuple(args.code or ("code/confirm.py",)))
        else:
            if not args.paths and not args.staged:
                raise KitError("give paths to lint, or --staged")
            problems = hygiene_hits(args.paths, deny_file=args.deny_file,
                                    staged_repo=args.repo if args.staged else None)
    except KitError as error:
        return die(error)
    for problem in problems:
        print(problem)
    if problems:
        print(f"{len(problems)} problem(s)", file=sys.stderr)
        return 1
    print("clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
