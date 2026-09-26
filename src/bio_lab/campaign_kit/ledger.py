"""Locked, additive updates of the private holdout ledger, and its public export.

    python -m bio_lab.campaign_kit.ledger record-discovery --ledger L --source ID --campaign NAME
    python -m bio_lab.campaign_kit.ledger record-open --ledger L --source ID --campaign NAME \
        --barrier audit/group-barrier.json [--date YYYY-MM-DD]
    python -m bio_lab.campaign_kit.ledger export-public --ledger L

Updates run under an fcntl lock (<ledger>.lock) and only ever add: a status
transition, a campaign name appended to a list, fields that were absent, and
history items at the end. After each update the kit checks that every earlier
entry and history item survives (same order, and no earlier value changed
beyond the transition this operation makes); otherwise nothing is written.

record_open records a holdout group's transition once per source (status
OPENED, opened_for = every frozen member's campaign, opened_on, campaign,
frozen_set_sha256 = the barrier file's sha256) and appends a group-member
history item for each later member. A source that an earlier group opened is
reused disjointly: its first opening stays as it was and the new group is
added to "openings". Every call is idempotent per campaign and source.
"""

from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
from pathlib import Path
import sys

from .common import KitError, SHA256_RE, die, file_lock, read_json, sha256_file, write_json_atomic

PUBLIC_FIELDS = ("id", "kind", "name", "status", "opened_for", "opened_on", "campaigns", "verified")
DISCOVERY_FROM = {"FRESH": "DISCOVERY", "METADATA": "DISCOVERY", "UNOBSERVED_SUBSET": "DISCOVERY",
                  "DISCOVERY": "DISCOVERY", "OPENED": "OPENED", "ANNOTATION": "ANNOTATION"}
OPEN_FROM = {"FRESH", "UNOBSERVED_SUBSET", "METADATA", "FUTURE"}


class LedgerError(KitError):
    pass


def _today() -> str:
    return _dt.datetime.now(_dt.timezone.utc).date().isoformat()


def _check_date(date: str) -> str:
    try:
        _dt.date.fromisoformat(date)
    except (TypeError, ValueError):
        raise LedgerError("date must be YYYY-MM-DD") from None
    return date


def _entry(ledger: dict, source: str) -> dict:
    entries = ledger.get("entries")
    if not isinstance(entries, list):
        raise LedgerError("the ledger has no entries list")
    found = [e for e in entries if isinstance(e, dict) and e.get("id") == source]
    if len(found) != 1:
        raise LedgerError(f"source {source} is {'missing from' if not found else 'duplicated in'} "
                          "the ledger; propose an entry instead")
    return found[0]


def _history(ledger: dict) -> list:
    history = ledger.setdefault("history", [])
    if not isinstance(history, list):
        raise LedgerError("the ledger history is not a list")
    return history


def _grew_only(old, new, path="") -> None:
    """new may add to old (keys, list tail items) but never change or drop what old had."""
    if isinstance(old, dict):
        if not isinstance(new, dict):
            raise LedgerError(f"{path or 'ledger'} changed type")
        for key, value in old.items():
            if key not in new:
                raise LedgerError(f"{path}.{key} would be deleted")
            _grew_only(value, new[key], f"{path}.{key}")
    elif isinstance(old, list):
        if not isinstance(new, list) or new[:len(old)] != old:
            raise LedgerError(f"{path} would be rewritten (lists only grow at the end)")
    elif old != new:
        raise LedgerError(f"{path} would be rewritten")


def _verify_additive(before: dict, after: dict, source: str) -> None:
    """Everything but the one entry's status is append-only."""
    old_entries, new_entries = before.get("entries", []), after.get("entries", [])
    if len(new_entries) != len(old_entries):
        raise LedgerError("entries would be added or removed")
    for old, new in zip(old_entries, new_entries):
        if isinstance(old, dict) and old.get("id") == source:
            old = dict(old)
            new = dict(new)
            old.pop("status", None)
            new.pop("status", None)
        _grew_only(old, new, f"entries[{old.get('id') if isinstance(old, dict) else '?'}]")
    for key in before:
        if key not in ("entries",):
            if key not in after:
                raise LedgerError(f"top-level {key} would be deleted")
            _grew_only(before[key], after[key], key)


def _update(ledger_path, source: str, change) -> str:
    ledger_path = Path(ledger_path)
    with file_lock(ledger_path.with_name(ledger_path.name + ".lock"), timeout=300):
        ledger = read_json(ledger_path, "holdout ledger")
        before = copy.deepcopy(ledger)
        result = change(ledger, _entry(ledger, source))
        if result == "unchanged":
            return result
        _verify_additive(before, ledger, source)
        write_json_atomic(ledger_path, ledger, indent=1)
        return result


def _append_unique(entry: dict, key: str, values) -> None:
    current = entry.get(key)
    if current is None:
        current = entry[key] = []
    if not isinstance(current, list):
        raise LedgerError(f"entry field {key} is not a list")
    for value in values:
        if value not in current:
            current.append(value)


def record_discovery(ledger_path, source: str, campaign: str, date: str | None = None) -> str:
    """Record that campaign reads source as discovery data. Returns recorded|unchanged."""
    if not isinstance(campaign, str) or not campaign:
        raise LedgerError("campaign must be a nonempty name")
    date = _check_date(date or _today())

    def change(ledger, entry):
        history = _history(ledger)
        if any(isinstance(h, dict) and h.get("action") == "discovery" and h.get("entry") == source
               and h.get("campaign") == campaign for h in history):
            return "unchanged"
        status = entry.get("status")
        if status not in DISCOVERY_FROM:
            raise LedgerError(f"source {source} is {status}; it cannot serve as discovery data")
        entry["status"] = DISCOVERY_FROM[status]
        _append_unique(entry, "campaigns", [campaign])
        history.append({"date": date, "entry": source, "action": "discovery", "campaign": campaign,
                        "from_status": status, "to_status": entry["status"],
                        "change": f"discovery use by {campaign}"})
        return "recorded"

    return _update(ledger_path, source, change)


def record_open(ledger_path, source: str, frozen_campaigns, campaign: str, date: str,
                barrier_sha256: str) -> str:
    """Record a holdout group's opening of source. Returns opened|reused|member|unchanged."""
    frozen = list(frozen_campaigns)
    if not frozen or not all(isinstance(c, str) and c for c in frozen) or len(set(frozen)) != len(frozen):
        raise LedgerError("frozen_campaigns must be a nonempty list of distinct names")
    if campaign not in frozen:
        raise LedgerError(f"{campaign} is not one of the group's frozen campaigns")
    if not isinstance(barrier_sha256, str) or not SHA256_RE.match(barrier_sha256):
        raise LedgerError("barrier_sha256 must be a SHA-256 hex digest")
    date = _check_date(date)
    frozen_sorted = sorted(frozen)

    def change(ledger, entry):
        history = _history(ledger)
        openings = entry.get("openings") or []
        group = [o for o in openings if isinstance(o, dict)
                 and o.get("frozen_set_sha256") == barrier_sha256]
        if group:
            if sorted(group[0].get("opened_for") or []) != frozen_sorted:
                raise LedgerError("this barrier was recorded with another frozen set")
            if group[0].get("campaign") == campaign or any(
                    isinstance(h, dict) and h.get("action") == "group_member"
                    and h.get("entry") == source and h.get("campaign") == campaign
                    and h.get("frozen_set_sha256") == barrier_sha256 for h in history):
                return "unchanged"
            history.append({"date": date, "entry": source, "action": "group_member",
                            "campaign": campaign, "frozen_set_sha256": barrier_sha256,
                            "change": f"group member {campaign} of an opening already recorded"})
            return "member"
        status = entry.get("status")
        opening = {"opened_on": date, "campaign": campaign, "frozen_set_sha256": barrier_sha256,
                   "opened_for": frozen_sorted}
        if status == "OPENED":
            opening["usage"] = "reused_disjoint"
            _append_unique(entry, "opened_for", frozen_sorted)
            action, result = "reuse_disjoint", "reused"
        elif status in OPEN_FROM:
            opening["usage"] = "holdout"
            entry["status"] = "OPENED"
            _append_unique(entry, "opened_for", frozen_sorted)
            for key, value in (("opened_on", date), ("campaign", campaign),
                               ("frozen_set_sha256", barrier_sha256)):
                entry.setdefault(key, value)
            action, result = "open", "opened"
        else:
            raise LedgerError(f"source {source} is {status}; it is not a clean holdout")
        _append_unique(entry, "openings", [opening])
        history.append({"date": date, "entry": source, "action": action, "campaign": campaign,
                        "frozen_set_sha256": barrier_sha256, "from_status": status,
                        "to_status": entry["status"], "opened_for": frozen_sorted,
                        "change": f"{entry['status']} for a group of {len(frozen_sorted)} "
                                  f"frozen campaign(s), recorded by {campaign}"})
        return result

    return _update(ledger_path, source, change)


def export_public(ledger_path) -> str:
    """Deterministic public copy: fixed fields only, no notes, locators or free text."""
    ledger = read_json(ledger_path, "holdout ledger")
    rows = []
    for entry in ledger.get("entries") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise LedgerError("a ledger entry has no id")
        row = {}
        for key in PUBLIC_FIELDS:
            value = entry.get(key)
            if key in ("opened_for", "campaigns"):
                value = [str(v) for v in (value or [])]
            row[key] = value
        rows.append(row)
    rows.sort(key=lambda r: r["id"])
    public = {"schema": "bio-holdout-ledger-public/1", "entries": rows}
    return json.dumps(public, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="campaign_kit.ledger", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", choices=("record-discovery", "record-open", "export-public"))
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--source")
    parser.add_argument("--campaign")
    parser.add_argument("--date")
    parser.add_argument("--barrier", help="group-barrier.json: its sha256 and frozen campaigns")
    parser.add_argument("--frozen-campaign", action="append", default=[])
    parser.add_argument("--barrier-sha256")
    args = parser.parse_args(argv)
    try:
        if args.action == "export-public":
            sys.stdout.write(export_public(args.ledger))
            return 0
        if not args.source or not args.campaign:
            raise LedgerError("--source and --campaign are required")
        if args.action == "record-discovery":
            print(record_discovery(args.ledger, args.source, args.campaign, args.date))
            return 0
        frozen, sha = args.frozen_campaign, args.barrier_sha256
        if args.barrier:
            from .barrier import canonical
            data = json.loads(Path(args.barrier).read_text(encoding="utf-8"))
            barrier_frozen = [f["campaign"] for f in canonical(data)["frozen"]]
            if frozen and sorted(frozen) != sorted(barrier_frozen):
                raise LedgerError("--frozen-campaign disagrees with the barrier file")
            if sha and sha != sha256_file(args.barrier):
                raise LedgerError("--barrier-sha256 disagrees with the barrier file")
            frozen, sha = barrier_frozen, sha256_file(args.barrier)
        if not frozen or not sha:
            raise LedgerError("record-open needs --barrier, or --frozen-campaign and --barrier-sha256")
        print(record_open(args.ledger, args.source, frozen, args.campaign, args.date or _today(), sha))
    except (KitError, OSError, json.JSONDecodeError) as error:
        return die(error)
    return 0


if __name__ == "__main__":
    sys.exit(main())
