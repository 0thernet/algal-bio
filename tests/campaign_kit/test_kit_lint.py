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


TYPED = {"MODE": "strict", "USE_X": True, "COUNT": 1, "GRID": [1, 2, 3],
         "MAP": {"a": 1, "b": [0.5, 2]}, "TAGS": ["x", "y"], "FLAGS": [1, 0], "DUPS": [1, 1],
         "NESTED": [[1, 2]]}


@pytest.mark.parametrize("literal", [
    "MODE = 'strict'", "USE_X = True", "COUNT = 1", "GRID = [1, 2, 3]", "GRID = (1, 2, 3)",
    "MAP = {'a': 1, 'b': [0.5, 2]}", "MAP = {'b': (0.5, 2), 'a': 1}", "TAGS = {'y', 'x'}",
    "TAGS = ['x', 'y']", "GRID = {3, 1, 2}", "FLAGS = {0, 1}", "NESTED = {(1, 2)}",
])
def test_protocol_lint_accepts_literals_equal_to_their_registration(tmp_path, literal):
    assert lint.lint_protocol(protocol_campaign(tmp_path, literal + "\n", constants=TYPED)) == []


@pytest.mark.parametrize("literal", [
    "MODE = 'loose'", "MODE = 'Strict'", "MODE = 1",
    "USE_X = 1", "USE_X = False", "USE_X = 'True'",      # a bool matches only a bool
    "COUNT = True", "COUNT = 1.5",
    "GRID = [1, 2]", "GRID = [1, 2, 4]", "GRID = [3, 2, 1]", "GRID = [1, 2, True]",
    "MAP = {'a': 1}", "MAP = {'a': 2, 'b': [0.5, 2]}", "MAP = {'a': 1, 'b': [0.5, 2], 'c': 0}",
    "MAP = {'a': True, 'b': [0.5, 2]}", "MAP = [('a', 1), ('b', [0.5, 2])]",
    "TAGS = {'x', 'z'}", "TAGS = {'x'}", "TAGS = {'x', 'y', 'z'}", "TAGS = 'xy'",
    "FLAGS = {True, False}", "DUPS = {1}", "NESTED = {1, 2}",
])
def test_protocol_lint_flags_literals_that_differ_from_their_registration(tmp_path, literal):
    problems = lint.lint_protocol(protocol_campaign(tmp_path, literal + "\n", constants=TYPED))
    name = literal.split(" =")[0]
    assert len(problems) == 1 and f"{name} = " in problems[0] and "but protocol.json registers" \
        in problems[0]


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


def joined_forms(single: str, first: str, last: str) -> list[str]:
    """Deny-list names joined by '-', '_' or '.', as they appear in slugs, identifiers
    and e-mail addresses (first-last, first_last, First.Last@, single_word_suffix)."""
    return [f"see notes/{first.lower()}-{last.lower()}.md",
            f'owner = "{first.lower()}_{last.lower()}"',
            f"mail {first}.{last}@example.org",
            f"{single.lower()}_notes.md"]


JOINED = joined_forms(NAME_ONE, *NAME_TWO.split())


@pytest.mark.parametrize("line", JOINED)
def test_deny_names_joined_by_separators_are_hits(tmp_path, deny_file, capsys, line):
    note = write(tmp_path / "body.md", f"intro\n{line}\n")
    assert lint.hygiene_hits([note], deny_file=deny_file, root=tmp_path) == \
        ["body.md:2: deny-list name"]
    assert lint.main(["hygiene", "--deny-file", str(deny_file), str(note)]) == 1
    out = capsys.readouterr()
    for part in (NAME_ONE, *NAME_TWO.split()):
        assert part.lower() not in (out.out + out.err).lower()


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


def _no_name(text: str) -> bool:
    low = text.lower()
    return NAME_ONE.lower() not in low and NAME_TWO.split()[0].lower() not in low


def test_a_deny_name_in_a_file_name_is_a_hit_with_a_neutral_label(tmp_path, deny_file, capsys):
    note = write(tmp_path / "notes" / f"thanks-{NAME_ONE.lower()}.md", "nothing personal\n")
    hits = lint.hygiene_hits([note], deny_file=deny_file)
    assert len(hits) == 1 and hits[0].endswith(": deny-list name (file path)")
    assert hits[0].startswith("<path #1 sha256:") and _no_name(hits[0])
    assert lint.main(["hygiene", "--deny-file", str(deny_file), str(note)]) == 1
    out = capsys.readouterr()
    assert _no_name(out.out + out.err)
    # a relative argument keeps its whole path, so its directories are checked too
    split = write(tmp_path / f"{NAME_TWO.split()[0]}_{NAME_TWO.split()[1]}.txt", "clean\n")
    hits = lint.hygiene_hits([split], deny_file=deny_file, root=tmp_path)
    assert hits and all(_no_name(h) for h in hits)


def test_a_deny_name_in_a_directory_name_is_a_hit(tmp_path, deny_file):
    folder = tmp_path / "work" / f"{NAME_ONE}-review"
    write(folder / "a.md", "clean\n")
    write(folder / "sub" / "b.md", "clean\n")
    for args in ({"root": tmp_path}, {}):
        hits = lint.hygiene_hits([folder], deny_file=deny_file, **args)
        assert len(hits) == 2 and all(h.endswith("deny-list name (file path)") for h in hits)
        assert all(_no_name(h) for h in hits)
    # the parent of the argument does not count: only what can reach Git is checked
    clean = write(tmp_path / f"{NAME_ONE}-outside" / "c.md", "clean\n")
    assert lint.hygiene_hits([clean], deny_file=deny_file) == []


def test_staged_paths_are_checked_with_neutral_labels(tmp_path, deny_file):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    write(repo / f"{NAME_ONE.lower()}" / "notes.md", "clean\n")
    write(repo / "ok" / f"with {NAME_ONE}.md", "clean\n")
    write(repo / "fine.md", "clean\n")
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    hits = lint.hygiene_hits([], deny_file=deny_file, staged_repo=repo)
    assert len(hits) == 2 and all(h.endswith("deny-list name (file path)") for h in hits)
    assert all(h.startswith("<path #") and _no_name(h) for h in hits)


def test_a_personal_path_in_a_file_path_is_a_hit(tmp_path, deny_file):
    nested = write(tmp_path / "copy" / "home" / "someone" / "x.md", "clean\n")
    hits = lint.hygiene_hits([tmp_path / "copy"], deny_file=deny_file, root=tmp_path)
    assert hits == ["copy/" + "home" + "/someone/x.md: personal path (file path)"]
    assert lint.hygiene_hits([nested], deny_file=deny_file) == []


def test_a_missing_path_is_reported_without_a_deny_name(tmp_path, deny_file):
    with pytest.raises(KitError) as error:
        lint.hygiene_hits([tmp_path / f"{NAME_ONE}.md"], deny_file=deny_file)
    assert "no such file" in str(error.value) and _no_name(str(error.value))


# ---------------------------------------------------------------- the kit lints itself

def test_kit_files_pass_the_hygiene_lint(deny_file):
    assert lint.hygiene_hits(KIT_PATHS, deny_file=deny_file, root=REPO) == []


def test_kit_files_have_no_conflict_markers():
    assert guards.find_conflict_markers(KIT_PATHS) == []
