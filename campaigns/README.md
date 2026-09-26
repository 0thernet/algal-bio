# Campaigns

Each directory is one registered study: its registration, frozen protocol, code,
receipts and outcome. Registrations are frozen before any holdout is opened.

> [!WARNING]
> **Prospective predictions need a person to evaluate them. Nothing does it automatically.**
>
> Some campaigns freeze predictions against releases that did not exist at freeze time.
> They list those sources in `registration/protocol.json` with `"usage": "future"`. The
> next DepMap, GO, ClinGen, ORCS, UniProt or Rhea release is their holdout. No scheduled
> job watches for those releases. When one lands:
>
> 1. List the waiting campaigns: `grep -l '"future"' campaigns/*/registration/protocol.json`.
> 2. For each one, run that campaign's own `fetch_holdout.py` and then `confirm.py`
>    exactly as frozen. Do not edit the registration, the thresholds or the code.
> 3. Publish the outcome in an outcome PR, whether it confirms, fails or is inconclusive.
>
> A prediction that is never evaluated is a lost result. It is not a pass.
