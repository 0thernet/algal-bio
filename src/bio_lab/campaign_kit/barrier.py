"""Holdout-group barrier: audit/group-barrier.json, written once, required before any fetch.

    python -m bio_lab.campaign_kit.barrier require <campaign_dir> --lane ID --freeze-sha256 SHA
    python -m bio_lab.campaign_kit.barrier write <campaign_dir> --json FILE

The file lists every member of the lane's holdout group, the frozen members
(id, campaign, freeze_sha256, merge_sha of the merged preregistration) and the
members released without freezing. Every member is either frozen or released.
It is compact JSON in a fixed key order, so a file written by the
orchestrator and one written here are byte-identical.

require() refuses unless the file exists and validates, lists this lane as
frozen with this freeze sha and a merge sha, names this campaign directory,
matches lane.json, the freeze.json bytes hash to that sha, and freeze verify
passes. fetch_holdout.py calls it before any network access and passes the
returned proof to receipts.fetch for every sealed destination.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

from .common import (GIT_SHA_RE, SHA256_RE, KitError, die, read_json, sha256_bytes)
from . import freeze as _freeze

SCHEMA = "bio-group-barrier/1"
BARRIER = "audit/group-barrier.json"
TOP_KEYS = ("schema", "run_id", "members", "frozen", "released")
FROZEN_KEYS = ("id", "campaign", "freeze_sha256", "merge_sha")


class BarrierError(KitError):
    pass


@dataclass(frozen=True)
class BarrierProof:
    """Returned only by require(); fetch and import_local demand it for sealed paths."""
    campaign_dir: Path
    lane_id: str
    campaign: str
    freeze_sha256: str
    merge_sha: str
    barrier_sha256: str
    members: tuple
    frozen_campaigns: tuple


def _strings(value, what) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise BarrierError(f"barrier {what} must be a list of nonempty strings")
    if len(set(value)) != len(value):
        raise BarrierError(f"barrier {what} has duplicates")
    return value


def canonical(barrier: dict) -> dict:
    """Validate and return the barrier in its fixed key order."""
    if not isinstance(barrier, dict) or set(barrier) != set(TOP_KEYS):
        raise BarrierError(f"barrier must have exactly the keys {', '.join(TOP_KEYS)}")
    if barrier["schema"] != SCHEMA:
        raise BarrierError(f"barrier schema must be {SCHEMA}")
    if not isinstance(barrier["run_id"], str) or not barrier["run_id"]:
        raise BarrierError("barrier run_id must be a nonempty string")
    members = _strings(barrier["members"], "members")
    released = _strings(barrier["released"], "released")
    if not members:
        raise BarrierError("barrier lists no members")
    frozen = barrier["frozen"]
    if not isinstance(frozen, list):
        raise BarrierError("barrier frozen must be a list")
    items = []
    for item in frozen:
        if not isinstance(item, dict) or set(item) != set(FROZEN_KEYS):
            raise BarrierError(f"each frozen member needs exactly {', '.join(FROZEN_KEYS)}")
        if not all(isinstance(item[k], str) and item[k] for k in ("id", "campaign")):
            raise BarrierError("frozen member id and campaign must be nonempty strings")
        if not SHA256_RE.match(str(item["freeze_sha256"])):
            raise BarrierError(f"frozen member {item['id']} has no valid freeze_sha256")
        if not GIT_SHA_RE.match(str(item["merge_sha"])):
            raise BarrierError(f"frozen member {item['id']} has no valid merge_sha "
                               "(its preregistration must be merged)")
        items.append({k: item[k] for k in FROZEN_KEYS})
    frozen_ids = [i["id"] for i in items]
    if len(set(frozen_ids)) != len(frozen_ids):
        raise BarrierError("barrier lists a frozen member twice")
    if set(frozen_ids) & set(released):
        raise BarrierError("a member cannot be both frozen and released")
    if set(frozen_ids) | set(released) != set(members):
        raise BarrierError("every member must be frozen or released, and only members may be")
    if not items:
        raise BarrierError("barrier has no frozen member")
    return {"schema": SCHEMA, "run_id": barrier["run_id"], "members": list(members),
            "frozen": items, "released": list(released)}


def serialise(barrier: dict) -> bytes:
    return json.dumps(canonical(barrier), ensure_ascii=False, separators=(",", ":")).encode()


def write(campaign_dir: os.PathLike | str, barrier: dict) -> str:
    """Write the barrier once. Identical content is a no-op; different content refuses."""
    path = Path(campaign_dir) / BARRIER
    data = serialise(barrier)
    if path.exists():
        existing = path.read_bytes()
        if existing.rstrip(b"\n") == data:
            return sha256_bytes(existing)
        raise BarrierError("audit/group-barrier.json exists with different content; "
                           "a barrier is never rewritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    return sha256_bytes(data)


def _campaign_matches(campaign_dir: Path, campaign: str) -> bool:
    return campaign_dir.name in (campaign, f"biology-{campaign}")


def require(campaign_dir: os.PathLike | str, lane_id: str, freeze_sha256: str) -> BarrierProof:
    campaign_dir = Path(campaign_dir).resolve()
    path = campaign_dir / BARRIER
    if not path.is_file():
        raise BarrierError("audit/group-barrier.json is missing; the holdout group has not "
                           "cleared its barrier, so nothing may be fetched")
    raw = path.read_bytes()
    try:
        barrier = json.loads(raw)
    except json.JSONDecodeError:
        raise BarrierError("audit/group-barrier.json is not valid JSON") from None
    barrier = canonical(barrier)
    if not isinstance(freeze_sha256, str) or not SHA256_RE.match(freeze_sha256):
        raise BarrierError("freeze_sha256 must be a SHA-256 hex digest")
    entry = next((f for f in barrier["frozen"] if f["id"] == lane_id), None)
    if entry is None:
        if lane_id in barrier["released"]:
            raise BarrierError(f"lane {lane_id} was released without freezing; it may not fetch")
        raise BarrierError(f"the barrier file does not list lane {lane_id} as frozen "
                           "(another group's barrier?)")
    if entry["freeze_sha256"] != freeze_sha256:
        raise BarrierError(f"the barrier lists lane {lane_id} with another freeze sha")
    if not _campaign_matches(campaign_dir, entry["campaign"]):
        raise BarrierError(f"the barrier names campaign {entry['campaign']}, not this directory")
    lane = read_json(campaign_dir / "lane.json", "lane.json")
    if lane.get("id") != lane_id:
        raise BarrierError("lane.json names another lane")
    actual = _freeze.freeze_sha256(campaign_dir)
    if actual != freeze_sha256:
        raise BarrierError("registration/freeze.json does not hash to the barrier's freeze sha")
    try:
        _freeze.verify(campaign_dir)
    except KitError as error:
        raise BarrierError(f"freeze verify failed: {error}") from None
    return BarrierProof(campaign_dir=campaign_dir, lane_id=lane_id, campaign=entry["campaign"],
                        freeze_sha256=freeze_sha256, merge_sha=entry["merge_sha"],
                        barrier_sha256=sha256_bytes(raw), members=tuple(barrier["members"]),
                        frozen_campaigns=tuple(f["campaign"] for f in barrier["frozen"]))


def require_proof(proof, dest: Path) -> BarrierProof:
    """Check that proof came from require() and covers dest's campaign sealed dir."""
    if not isinstance(proof, BarrierProof):
        raise BarrierError("a sealed destination needs the proof returned by barrier.require()")
    sealed = proof.campaign_dir / "data"
    dest = Path(dest).resolve()
    if not dest.is_relative_to(sealed):
        raise BarrierError("the barrier proof belongs to another campaign")
    return proof


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.barrier", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("require", "write"))
    parser.add_argument("campaign_dir")
    parser.add_argument("--lane")
    parser.add_argument("--freeze-sha256")
    parser.add_argument("--json", help="barrier JSON to write")
    args = parser.parse_args(argv)
    try:
        if args.action == "write":
            if not args.json:
                raise BarrierError("write needs --json")
            barrier = json.loads(Path(args.json).read_text(encoding="utf-8"))
            print(json.dumps({"barrier_sha256": write(args.campaign_dir, barrier)}))
        else:
            if not args.lane or not args.freeze_sha256:
                raise BarrierError("require needs --lane and --freeze-sha256")
            proof = require(args.campaign_dir, args.lane, args.freeze_sha256)
            print(json.dumps({"ok": True, "lane": proof.lane_id, "campaign": proof.campaign,
                              "barrier_sha256": proof.barrier_sha256,
                              "members": list(proof.members)}, indent=1))
    except (KitError, json.JSONDecodeError, OSError) as error:
        return die(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
