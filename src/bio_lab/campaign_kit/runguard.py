"""Single-run guard and append-only run ledger for confirm.py.

    with runguard.run(CAMPAIGN_DIR, lane_id=LANE, erratum=args.erratum) as active:
        ...                                  # seal.open_sealed(CAMPAIGN_DIR, name, active)
        active.finish(label, outputs=["results/confirmation.summary.json", ...])

run() refuses unless the freeze verifies and the group barrier lists this
lane with this freeze (barrier.require). It refuses a second run: once
results/confirmation.runs.jsonl holds a start, or any results/confirmation.*
file exists, another run needs erratum="errata/E<n>.md", an existing,
nonempty file not used by an earlier run. Only one process may hold the run
at a time. Every run appends start, then finish or crash or incomplete,
to results/confirmation.runs.jsonl; nothing is ever removed from it.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from .common import KitError, append_jsonl, file_lock, read_jsonl, safe_relative, sha256_file, utc_now
from . import barrier as _barrier
from . import freeze as _freeze

LEDGER = "results/confirmation.runs.jsonl"
LOCK = "results/.confirmation.lock"


class RunGuardError(KitError):
    pass


class ActiveRun:
    def __init__(self, campaign_dir: Path, run: int, proof):
        self.campaign_dir = campaign_dir
        self.run = run
        self.proof = proof
        self.active = True
        self.finished = False
        self.opened: dict[str, str] = {}

    def note_open(self, name: str, sha: str) -> None:
        self.opened[name] = sha

    def finish(self, label: str, outputs=()) -> dict:
        """Record the outcome label and the sha256 of each output file."""
        if not self.active or self.finished:
            raise RunGuardError("this run is not active")
        if not isinstance(label, str) or not label:
            raise RunGuardError("finish needs the outcome label")
        hashes = {}
        for rel in outputs:
            safe_relative(rel)
            path = self.campaign_dir / rel
            if not path.is_file():
                raise RunGuardError(f"output {rel} does not exist")
            hashes[rel] = sha256_file(path)
        record = {"event": "finish", "run": self.run, "utc": utc_now(), "label": label,
                  "outputs": hashes, "sealed_opened": dict(sorted(self.opened.items()))}
        append_jsonl(self.campaign_dir / LEDGER, record)
        self.finished = True
        return record


def history(campaign_dir) -> list[dict]:
    return read_jsonl(Path(campaign_dir) / LEDGER)


def _prior_runs(campaign_dir: Path, records: list[dict]) -> bool:
    if records:
        return True
    results = campaign_dir / "results"
    return results.is_dir() and any(p.name.startswith("confirmation.") for p in results.iterdir())


@contextlib.contextmanager
def run(campaign_dir, *, lane_id: str, erratum: str | None = None):
    campaign_dir = Path(campaign_dir).resolve()
    _freeze.freeze_sha256(campaign_dir)      # before the lock file exists: no freeze, no trace
    (campaign_dir / "results").mkdir(exist_ok=True)
    with file_lock(campaign_dir / LOCK, blocking=False):
        freeze_sha = _freeze.freeze_sha256(campaign_dir)
        proof = _barrier.require(campaign_dir, lane_id, freeze_sha)
        # an earlier run killed inside open_sealed may have left a file readable
        from .seal import relock_if_open
        relock_if_open(campaign_dir)
        records = history(campaign_dir)
        if _prior_runs(campaign_dir, records):
            if not erratum:
                raise RunGuardError("confirm.py has already run for this campaign; a rerun "
                                    "needs an erratum (errata/E<n>.md) passed explicitly")
            rel = safe_relative(erratum).as_posix()
            if not rel.startswith("errata/"):
                raise RunGuardError("the erratum must be a file under errata/")
            path = campaign_dir / rel
            if not path.is_file() or not path.read_text(encoding="utf-8").strip():
                raise RunGuardError(f"erratum {rel} does not exist or is empty")
            if any(r.get("erratum") == rel for r in records):
                raise RunGuardError(f"erratum {rel} already justified an earlier run; "
                                    "write a new one")
            erratum_sha = sha256_file(path)
        elif erratum:
            raise RunGuardError("an erratum is only for reruns; this is the first run")
        else:
            rel = erratum_sha = None
        number = 1 + sum(1 for r in records if r.get("event") == "start")
        append_jsonl(campaign_dir / LEDGER, {
            "event": "start", "run": number, "utc": utc_now(), "lane_id": lane_id,
            "freeze_sha256": freeze_sha, "barrier_sha256": proof.barrier_sha256,
            "erratum": rel, "erratum_sha256": erratum_sha, "pid": os.getpid()})
        active = ActiveRun(campaign_dir, number, proof)
        crashed = False
        try:
            yield active
        except BaseException as error:
            crashed = True
            # the type only: a message could quote a sealed value into a public ledger
            append_jsonl(campaign_dir / LEDGER, {"event": "crash", "run": number,
                                                 "utc": utc_now(), "error": type(error).__name__})
            raise
        finally:
            if not active.finished and not crashed:
                append_jsonl(campaign_dir / LEDGER, {"event": "incomplete", "run": number,
                                                     "utc": utc_now()})
            active.active = False
