#!/usr/bin/env python3
"""Run the hash-bound campaign tests from the published flat layout (unbound helper).

`test_replicate.py` (bound at freeze) loads the registration draft from
`<campaign root>/registration/protocol.draft.json`, the private working layout. In the
public directory the draft is published as `registration.reviewed-draft.json` beside the
tests. This helper recreates the original layout in a temporary directory by copying the
published files (bytes unchanged) and runs `unittest` there, so the bound test file need
not be edited. Usage: python run_tests.py [-v]
"""
import pathlib, shutil, subprocess, sys, tempfile
HERE = pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as d:
    root = pathlib.Path(d)
    (root / "code").mkdir(); (root / "registration").mkdir()
    for f in ("replicate.py", "compartment.py", "pc1.py", "test_replicate.py", "test_pc1.py", "requirements.lock", "requirements.in"):
        shutil.copyfile(HERE / f, root / "code" / f)
    draft = HERE / "registration.reviewed-draft.json"
    if not draft.exists():
        draft = HERE.parent / "registration" / "protocol.draft.json"
    shutil.copyfile(draft, root / "registration" / "protocol.draft.json")
    sys.exit(subprocess.run([sys.executable, "-m", "unittest", *sys.argv[1:], "test_replicate", "test_pc1"], cwd=root / "code").returncode)
