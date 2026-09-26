"""Campaign kit: fail-closed guards shared by sealed-holdout campaigns.

The kit generalises what the completed transfer campaigns did by hand:
receipted downloads validated by content, a write-once freeze with relative
paths, a group barrier before any holdout fetch, a single-run guard with an
append-only run ledger, hash-verified sealed reads, locked holdout-ledger
updates, compute slots, a data budget, lints and a public assembly step.

Standard library only. Every module uses relative imports so the same files
work as ``bio_lab.campaign_kit`` in this repository and as ``campaign_kit``
when ``scripts/new_campaign.py`` vendors them into a campaign's ``code/``.
Locations come from explicit arguments or the ``BIO_MINING_DIR`` environment
variable, never from paths written into the code.
"""

KIT_VERSION = "1.0.0"

MODULES = (
    "common",
    "protocol",
    "receipts",
    "freeze",
    "runguard",
    "stats",
    "seal",
    "barrier",
    "guards",
    "slot",
    "ledger",
    "lint",
    "assemble_public",
)
