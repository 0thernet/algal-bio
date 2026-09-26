#!/usr/bin/env python3
"""Scaffold a private campaign directory around a vendored copy of the campaign kit.

Usage: python scripts/new_campaign.py <name> <private-dir> [--lane-json FILE]

<name> is the public campaign name (lowercase, for example
depmap-26q1-new-lines-2026-09-26); <private-dir> must be named <name> or
biology-<name>, because the group barrier matches the campaign by directory
name. The generator creates missing parts only and never overwrites an
existing file: a lane.json written earlier stays, and so does any code.

Layout:
  code/campaign_kit/   vendored kit (+ VENDORED.json with file hashes)
  code/freeze.py       kit freeze wrapper
  code/fetch_holdout.py, code/confirm.py   templates that refuse until filled in
  registration/ tests/ data/{discovery,prep,sealed}/ results/ review/ audit/
  errata/ prior-art/ fanout/ README.md
  tests/conftest.py    points the tests at this campaign
  tests/test_<slug>_scaffold.py   vendored-kit integrity check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / "src" / "bio_lab" / "campaign_kit"
NAME_RE = re.compile(r"^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")
DIRS = ("code", "registration", "tests", "data/discovery", "data/prep", "data/sealed", "results",
        "review", "audit", "errata", "prior-art", "fanout")


def _kit_version() -> str:
    text = (KIT / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^KIT_VERSION = "([^"]+)"', text, re.M)
    if not match:
        raise SystemExit("refusing: cannot read the kit version")
    return match.group(1)


FREEZE_PY = '''#!/usr/bin/env python3
"""Freeze or verify this campaign with the vendored kit.

    python code/freeze.py build [--include REL]... [--deny-file F]
    python code/freeze.py verify
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from campaign_kit import freeze  # noqa: E402

if __name__ == "__main__":
    args = sys.argv[1:] or ["verify"]
    raise SystemExit(freeze.main([args[0], os.path.dirname(HERE), *args[1:]]))
'''

FETCH_PY = '''#!/usr/bin/env python3
"""Post-freeze sealed fetch for this lane. TEMPLATE: fill SOURCES before the freeze.

    python code/fetch_holdout.py --freeze-sha256 <sha256 of registration/freeze.json>

The barrier check runs before any network access and its proof is passed to
every sealed fetch. Set BIO_MINING_DIR, BIO_RUN_ID and BIO_DATA_BUDGET_GB.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from campaign_kit import barrier, receipts, seal  # noqa: E402
from campaign_kit.common import KitError  # noqa: E402
from campaign_kit.receipts import Expect  # noqa: E402,F401

with open(os.path.join(ROOT, "lane.json"), encoding="utf-8") as handle:
    LANE_ID = json.load(handle)["id"]

# Registered holdout files: sealed file name -> (url, Expect(...)). Each Expect
# needs a content check (first line, magic bytes, required columns or a
# provider-published sha256). Validation never trusts the HTTP status.
SOURCES = {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--freeze-sha256", required=True)
    args = parser.parse_args(argv)
    proof = barrier.require(ROOT, LANE_ID, args.freeze_sha256)
    if not SOURCES:
        raise SystemExit("refusing: SOURCES is empty; register the holdout files first")
    with seal.writable(ROOT):
        for name, (url, expect) in sorted(SOURCES.items()):
            dest = os.path.join(ROOT, "data", "sealed", name)
            receipt = receipts.fetch(url, dest, expect, barrier=proof)
            print(name, receipt["bytes"], receipt["sha256"][:16], receipt["source"])


if __name__ == "__main__":
    try:
        main()
    except KitError as error:
        raise SystemExit(f"refusing: {error}")
'''

CONFIRM_PY = '''#!/usr/bin/env python3
"""Single sealed confirmation run for this lane. TEMPLATE: implement evaluate().

    python code/confirm.py [--erratum errata/E<n>.md]

Every constant comes from registration/protocol.json ("constants"). The run
guard verifies the freeze and the group barrier, refuses a second run
without an erratum, and records the run in results/confirmation.runs.jsonl.
Sealed files open only through seal.open_sealed(ROOT, name, run).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from campaign_kit import protocol, runguard, seal  # noqa: E402,F401
from campaign_kit.common import KitError  # noqa: E402

with open(os.path.join(ROOT, "lane.json"), encoding="utf-8") as handle:
    LANE_ID = json.load(handle)["id"]
K = protocol.load_constants(ROOT)


def evaluate(run):
    """Return (label, [campaign-relative output files]) under the registered rule."""
    raise NotImplementedError("template: implement the registered evaluation")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--erratum", help="errata/E<n>.md justifying a rerun")
    args = parser.parse_args(argv)
    with runguard.run(ROOT, lane_id=LANE_ID, erratum=args.erratum) as run:
        label, outputs = evaluate(run)
        run.finish(label, outputs=outputs)
    print(label)


if __name__ == "__main__":
    try:
        main()
    except KitError as error:
        raise SystemExit(f"refusing: {error}")
'''

CONFTEST_PY = '''"""Point this campaign's tests at its own code/ (and its vendored kit)."""
import os
import sys

import pytest

CAMPAIGN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(CAMPAIGN_DIR, "code"))


@pytest.fixture
def campaign_dir():
    return CAMPAIGN_DIR


@pytest.fixture(autouse=True)
def _isolated_mining(tmp_path, monkeypatch):
    """Tests never reach the real mining dir, run ledger, budget or slots."""
    mining = tmp_path / "mining"
    mining.mkdir()
    monkeypatch.setenv("BIO_MINING_DIR", str(mining))
    for name in ("BIO_RUN_ID", "BIO_DATA_BUDGET_GB", "BIO_SLOT"):
        monkeypatch.delenv(name, raising=False)
    return mining
'''

SCAFFOLD_TEST = '''"""Scaffold checks: the vendored kit is intact and lane.json names a lane."""
import hashlib
import json
import os

CAMPAIGN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KIT_DIR = os.path.join(CAMPAIGN_DIR, "code", "campaign_kit")


def test_vendored_kit_matches_its_manifest():
    with open(os.path.join(KIT_DIR, "VENDORED.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    assert manifest["files"]
    for name, sha in manifest["files"].items():
        with open(os.path.join(KIT_DIR, name), "rb") as handle:
            assert hashlib.sha256(handle.read()).hexdigest() == sha, name


def test_lane_json_names_a_lane():
    path = os.path.join(CAMPAIGN_DIR, "lane.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            assert json.load(handle).get("id")
'''

README = '''# {name}

Private campaign directory scaffolded by `scripts/new_campaign.py` (campaign kit {version}).
See `docs/campaign-kit.md` in the public repository for the lane lifecycle.

- [ ] lane.json (the lane card, written once)
- [ ] audit/metadata.json, prior-art/prior-art.md
- [ ] registration/protocol.json with a "constants" object; selection in code
- [ ] code/ and tests/; `python -m campaign_kit.lint protocol .` and the hygiene lint pass
- [ ] independent pre-freeze review in review/
- [ ] `python code/freeze.py build`; public preregistration merged
- [ ] audit/group-barrier.json; `python code/fetch_holdout.py --freeze-sha256 ...`
- [ ] `python code/confirm.py` once; report.md; post-outcome audit; outcome PR
'''


def _write_new(path: Path, text: str, created: list) -> None:
    if path.exists() or path.is_symlink():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "x", encoding="utf-8") as handle:
        handle.write(text)
    created.append(path)


def scaffold(name: str, private_dir, lane_json=None) -> list[Path]:
    if not NAME_RE.match(name):
        raise SystemExit("refusing: name must be lowercase letters, digits, dots and dashes")
    target = Path(private_dir)
    if target.name not in (name, f"biology-{name}"):
        raise SystemExit(f"refusing: the directory must be named {name} or biology-{name}")
    if target.exists() and not target.is_dir():
        raise SystemExit("refusing: the private dir path is a file")
    if lane_json is not None and not Path(lane_json).is_file():
        raise SystemExit("refusing: --lane-json does not exist")
    created: list[Path] = []
    for rel in DIRS:
        path = target / rel
        if not path.exists():
            path.mkdir(parents=True)
            created.append(path)
    kit_dest = target / "code" / "campaign_kit"
    kit_dest.mkdir(exist_ok=True)
    hashes = {}
    for src in sorted(KIT.glob("*.py")):
        dst = kit_dest / src.name
        if not dst.exists():
            shutil.copyfile(src, dst)
            created.append(dst)
        hashes[src.name] = hashlib.sha256(src.read_bytes()).hexdigest()
    vendored = {"schema": "bio-kit-vendored/1", "kit_version": _kit_version(), "files": hashes}
    _write_new(kit_dest / "VENDORED.json", json.dumps(vendored, indent=1, sort_keys=True) + "\n",
               created)
    _write_new(target / "code" / "freeze.py", FREEZE_PY, created)
    _write_new(target / "code" / "fetch_holdout.py", FETCH_PY, created)
    _write_new(target / "code" / "confirm.py", CONFIRM_PY, created)
    _write_new(target / "tests" / "conftest.py", CONFTEST_PY, created)
    slug = name.replace("-", "_").replace(".", "_")
    _write_new(target / "tests" / f"test_{slug}_scaffold.py", SCAFFOLD_TEST, created)
    _write_new(target / "README.md", README.format(name=name, version=_kit_version()), created)
    if lane_json is not None:
        _write_new(target / "lane.json", Path(lane_json).read_text(encoding="utf-8"), created)
    return created


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name")
    parser.add_argument("private_dir")
    parser.add_argument("--lane-json", help="copy this lane card to lane.json if none exists")
    args = parser.parse_args(argv)
    created = scaffold(args.name, args.private_dir, args.lane_json)
    base = Path(args.private_dir)
    for path in created:
        print("created", os.path.relpath(path, base))
    if not created:
        print("nothing to create; the scaffold is complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
