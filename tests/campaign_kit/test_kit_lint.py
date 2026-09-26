"""Protocol-to-code lint and the public hygiene lint, including a lint of the kit itself."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from bio_lab.campaign_kit import guards, lint
from bio_lab.campaign_kit.common import KitError
from conftest import write

REPO = Path(__file__).resolve().parents[2]
KIT_PATHS = [REPO / "src" / "bio_lab" / "campaign_kit", REPO / "scripts" / "new_campaign.py",
             REPO / "tests" / "campaign_kit", REPO / "docs" / "campaign-kit.md"]

# Synthetic deny-list names, assembled at runtime so no file holds them whole.
NAME_ONE = "Zorb" + "lax"
NAME_TWO = "Quin" + "tavia " + "Morr" + "ow"


@pytest.fixture
def deny_file(tmp_path):
    path = tmp_path / "deny.txt"
    path.write_text(f"# synthetic deny list\n{NAME_ONE}\n\n{NAME_TWO}\n")
    return path


def protocol_campaign(tmp_path, code, constants=None, exempt=None):
    protocol = {"constants": constants if constants is not None else {"ALPHA": 0.05, "TOP_K": 20}}
    if exempt:
        protocol["constants_exempt"] = exempt
    write(tmp_path / "registration" / "protocol.json", json.dumps(protocol))
    write(tmp_path / "code" / "confirm.py", code)
    return tmp_path


# ---------------------------------------------------------------- protocol lint

def test_protocol_lint_passes_consistent_code(tmp_path):
    code = ("from campaign_kit.protocol import load_constants, constant\n"
            "K = load_constants('.')\nALPHA = 0.05\nTOP_K = K['TOP_K']\n"
            "def keep(q):\n    return q <= K.get('ALPHA') and q < constant('.', 'ALPHA')\n")
    assert lint.lint_protocol(protocol_campaign(tmp_path, code)) == []


def test_protocol_lint_flags_a_literal_that_differs(tmp_path):
    problems = lint.lint_protocol(protocol_campaign(tmp_path, "ALPHA = 0.1\n"))
    assert len(problems) == 1 and "ALPHA = 0.1 but protocol.json registers 0.05" in problems[0]


def test_protocol_lint_flags_unregistered_constants_and_reads(tmp_path):
    code = ("K = load_constants('.')\nBETA = 3\nx = K['GAMMA']\ny = K.get('DELTA')\n"
            "z = constant('.', 'EPSILON')\nw = protocol['constants']['ZETA']\n")
    problems = lint.lint_protocol(protocol_campaign(tmp_path, code))
    joined = "\n".join(problems)
    for name in ("BETA", "GAMMA", "DELTA", "EPSILON", "ZETA"):
        assert name in joined
    assert len(problems) == 5


def test_protocol_lint_flags_bare_floats_in_comparisons(tmp_path):
    code = "def keep(q, r):\n    return q < 0.05 and r > -0.3 and q >= 0.0 and r <= 1.0\n"
    problems = lint.lint_protocol(protocol_campaign(tmp_path, code))
    assert len(problems) == 2 and all("bare float" in p for p in problems)


def test_protocol_lint_exemptions_and_missing_constants(tmp_path):
    code = "SEED_NOTE = 'text'\nLABELS = ('A', 'B')\n"
    assert lint.lint_protocol(protocol_campaign(tmp_path / "a", code,
                                                exempt={"SEED_NOTE": "doc", "LABELS": "names"})) == []
    assert "no nonempty" in lint.lint_protocol(protocol_campaign(tmp_path / "b", "", constants={}))[0]


def test_protocol_lint_cli(tmp_path, capsys):
    campaign = protocol_campaign(tmp_path, "ALPHA = 0.2\n")
    assert lint.main(["protocol", str(campaign)]) == 1
    assert "ALPHA" in capsys.readouterr().out


# ---------------------------------------------------------------- hygiene lint

def test_deny_hit_is_reported_without_the_name(tmp_path, deny_file, capsys):
    note = write(tmp_path / "pr-body.md", f"Thanks to {NAME_ONE.lower()} for the idea.\n"
                 f"And {NAME_TWO.split()[0]}\n{NAME_TWO.split()[1]} too.\n")
    hits = lint.hygiene_hits([note], deny_file=deny_file, root=tmp_path)
    assert hits == ["pr-body.md:1: deny-list name", "pr-body.md:2: deny-list name"]
    assert lint.main(["hygiene", "--deny-file", str(deny_file), str(note)]) == 1
    out = capsys.readouterr()
    assert NAME_ONE.lower() not in (out.out + out.err).lower()
    assert NAME_TWO.split()[0].lower() not in (out.out + out.err).lower()


def test_deny_names_match_whole_words_only(tmp_path, deny_file):
    note = write(tmp_path / "ok.md", f"{NAME_ONE}ian and pre{NAME_ONE} are other words.\n")
    assert lint.hygiene_hits([note], deny_file=deny_file) == []


def test_personal_paths_and_large_files(tmp_path, deny_file):
    personal = "/" + "home" + "/someone/data.csv"
    write(tmp_path / "a.md", f"see {personal}\n")
    (tmp_path / "big.bin").write_bytes(b"0" * (4 * 1024 * 1024 + 1))
    hits = lint.hygiene_hits([tmp_path], deny_file=deny_file, root=tmp_path)
    assert "a.md:1: personal path" in hits and "big.bin: file over 4 MB" in hits
    assert all(personal not in h for h in hits)


def test_hygiene_requires_the_deny_file(tmp_path):
    with pytest.raises(KitError, match="deny-file"):
        lint.hygiene_hits([tmp_path], deny_file=None)
    with pytest.raises(KitError, match="cannot read the deny file"):
        lint.hygiene_hits([tmp_path], deny_file=tmp_path / "absent.txt")


def test_hygiene_reads_staged_blobs(tmp_path, deny_file):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    write(repo / "notes.md", f"{NAME_ONE}\n")
    subprocess.run(["git", "-C", str(repo), "add", "notes.md"], check=True)
    (repo / "notes.md").write_text("clean in the worktree, not in the index\n")
    hits = lint.hygiene_hits([], deny_file=deny_file, staged_repo=repo)
    assert hits == ["staged:notes.md:1: deny-list name"]


# ---------------------------------------------------------------- the kit lints itself

def test_kit_files_pass_the_hygiene_lint(deny_file):
    assert lint.hygiene_hits(KIT_PATHS, deny_file=deny_file, root=REPO) == []


def test_kit_files_have_no_conflict_markers():
    assert guards.find_conflict_markers(KIT_PATHS) == []
