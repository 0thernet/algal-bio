#!/usr/bin/env python3
"""Run or verify the registered zero-provider biology qualification."""
from __future__ import annotations
import argparse
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--offline", action="store_true")
    mode.add_argument("--verify", type=Path)
    mode.add_argument("--recompute", type=Path)
    parser.add_argument("--out", type=Path, default=ROOT / "runs/qualification")
    args = parser.parse_args()
    selected = "--offline" if args.offline else "--verify" if args.verify else "--recompute"
    directory = (args.out if args.offline else args.verify or args.recompute).resolve()
    if args.offline:
        directory.parent.mkdir(parents=True, exist_ok=True)
    raise SystemExit(subprocess.run(["bun", str(ROOT / "scripts/run_bio_qualification.ts"), selected, str(directory)],
                                   cwd=ROOT, timeout=180, check=False).returncode)
