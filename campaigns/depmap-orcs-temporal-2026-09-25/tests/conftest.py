import os, sys, pytest

# The published record keeps the depmap machinery under
# campaigns/depmap-context-dependency-sealed-holdout-2026-09-25/code; the
# private working tree used a sibling checkout. Point the campaign at the
# in-repo copy so the tests run standalone; tests that need the external
# data roots still skip/fail by their own guards.
_DEPMAP = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..",
    "depmap-context-dependency-sealed-holdout-2026-09-25"))
os.environ.setdefault("DEPMAP_CAMPAIGN_DIR", _DEPMAP)
sys.path.insert(1, os.path.join(_DEPMAP, "code"))
sys.path.insert(0, os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "code")))
