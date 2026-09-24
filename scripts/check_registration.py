#!/usr/bin/env python3
"""Offline, fail-closed registration checks for the descriptive biology pilot.

This is a deliberately bounded JSON Schema vocabulary, not a general validator.
It checks the bundled schemas, source projections, hashes, and study eligibility.
It neither proves trusted registration time nor supplies holdout access control.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import date
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "schemas/bio-study.schema.json"
CANDIDATE_SCHEMA = "schemas/candidate.schema.json"
KEYWORDS = {
    "$schema", "$id", "$defs", "$ref", "title", "description", "type", "const", "enum",
    "additionalProperties", "required", "properties", "items", "minItems", "maxItems",
    "minLength", "pattern", "minimum", "maximum",
}
METADATA_FIELDS = {
    "!Sample_title", "!Sample_geo_accession", "!Sample_status", "!Sample_source_name_ch1",
    "!Sample_organism_ch1", "!Sample_characteristics_ch1", "!Sample_description",
    "!Sample_library_strategy", "!Sample_relation", "!Sample_series_id", "!Sample_data_processing",
}


class RegistrationError(ValueError):
    """The registration or its supporting evidence is inadmissible."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RegistrationError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise RegistrationError(f"Nonfinite JSON constant: {value}")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                          parse_constant=_bad_constant)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistrationError(f"Cannot read JSON {path}: {exc}") from exc


def safe_path(root: Path, relative: str) -> Path:
    require(isinstance(relative, str) and bool(relative), "Artifact path must be a string")
    path = PurePosixPath(relative)
    require(not path.is_absolute() and ".." not in path.parts and str(path) == relative
            and "\\" not in relative, f"Noncanonical artifact path: {relative}")
    resolved = root.joinpath(*path.parts).resolve()
    require(resolved.is_relative_to(root.resolve()), f"Artifact escapes repository: {relative}")
    return resolved


def validate_schema(value: Any, schema: dict, where: str = "$", document: dict | None = None) -> None:
    """Validate the exact vocabulary used in these two checked-in schema files."""
    document = schema if document is None else document
    require(not set(schema) - KEYWORDS, f"Unsupported schema keyword at {where}")
    if "$ref" in schema:
        ref = schema["$ref"]
        require(ref.startswith("#/$defs/"), f"Only local schema references are supported: {ref}")
        validate_schema(value, document["$defs"][ref[len("#/$defs/"):]], where, document)
        return
    if "const" in schema:
        expected = schema["const"]
        require(type(value) is type(expected) and value == expected, f"{where}: wrong constant")
    if "enum" in schema:
        require(value in schema["enum"], f"{where}: unexpected enum value")
    expected_types = schema.get("type", [])
    if isinstance(expected_types, str):
        expected_types = [expected_types]
    type_matches = {
        "object": isinstance(value, dict), "array": isinstance(value, list),
        "string": isinstance(value, str), "boolean": type(value) is bool,
        "integer": type(value) is int, "number": type(value) in (int, float), "null": value is None,
    }
    if expected_types:
        require(any(type_matches[t] for t in expected_types), f"{where}: wrong type (expected {expected_types})")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        require(set(schema.get("required", [])) <= set(value), f"{where}: missing required fields")
        if schema.get("additionalProperties") is False:
            require(not set(value) - set(properties), f"{where}: unknown fields {set(value) - set(properties)}")
        for name, item in value.items():
            if name in properties:
                validate_schema(item, properties[name], f"{where}.{name}", document)
    elif isinstance(value, list):
        require(len(value) >= schema.get("minItems", 0), f"{where}: too few items")
        require(len(value) <= schema.get("maxItems", len(value)), f"{where}: too many items")
        for i, item in enumerate(value):
            validate_schema(item, schema["items"], f"{where}[{i}]", document)
    elif isinstance(value, str):
        require(len(value) >= schema.get("minLength", 0), f"{where}: empty string")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, f"{where}: wrong string format")
    elif type(value) in (int, float):
        require(math.isfinite(value), f"{where}: nonfinite number")
        require(value >= schema.get("minimum", value), f"{where}: below minimum")
        require(value <= schema.get("maximum", value), f"{where}: above maximum")


def verify_artifact(root: Path, entry: dict, schema: dict) -> Path:
    validate_schema(entry, schema["$defs"]["artifact"], "artifact", schema)
    path = safe_path(root, entry["path"])
    require(path.is_file(), f"Missing artifact: {entry['path']}")
    payload = path.read_bytes()
    require(len(payload) == entry["bytes"] and digest(payload) == entry["sha256"],
            f"Artifact hash/size mismatch: {entry['path']}")
    return path


def unique(values: list[Any], label: str) -> None:
    require(len(set(values)) == len(values), f"Duplicate {label}")


def valid_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise RegistrationError(f"Invalid date: {value}") from exc


def project_sample(record: dict) -> dict:
    """Derive source facts while leaving animal/culture identity unresolved."""
    lines = record["lines"]
    require(lines[0]["text"] == f"^SAMPLE = {record['sample_id']}", "Projection sample identity mismatch")
    fields: dict[str, list[str]] = {}
    last = 0
    for item in lines:
        require(item["line_number"] > last, "Projection line numbers must increase")
        last = item["line_number"]
    for item in lines[1:]:
        parts = item["text"].split(" = ", 1)
        require(len(parts) == 2 and parts[0] in METADATA_FIELDS, "Unapproved metadata field")
        key, value = parts
        if key == "!Sample_data_processing":
            require(value.startswith(("Assembly:", "Genome_build:")), "Only genome-build facts belong in the projection")
        fields.setdefault(key, []).append(value)
    for key in ("!Sample_geo_accession", "!Sample_title", "!Sample_organism_ch1", "!Sample_data_processing"):
        require(len(fields.get(key, [])) == 1, f"Expected exactly one {key}")
    require(fields["!Sample_geo_accession"] == [record["sample_id"]], "GSM accession mismatch")
    characteristics = [v.split(": ", 1) for v in fields.get("!Sample_characteristics_ch1", [])]
    require(all(len(v) == 2 for v in characteristics), "Malformed sample characteristics")
    unique([v[0] for v in characteristics], "sample characteristic")
    chars = dict(characteristics)
    require("cell type" in chars and "genotype" in chars, "Missing cell/genotype metadata")
    title = fields["!Sample_title"][0]
    series = fields.get("!Sample_series_id", [])
    unique(series, "series accession")
    assay = "bulk_rna"
    for token, result in (("scRNA", "scrna"), ("ATAC", "atac"), ("CUT&RUN", "cutandrun"), ("Hi-C", "hic"), ("HiC", "hic")):
        if token in title:
            assay = result
    if "GSE89520" in series and "RNASeq" not in title and "HiC" not in title:
        assay = "chip"
    age = chars.get("timepoint")
    age_match = re.search(r"P\d+\.\d+", title)
    title_age = age_match.group() if age_match else None
    replicate = re.search(r"Rep(\d+)", title)
    biosamples = [v.rsplit("/", 1)[-1] for v in fields.get("!Sample_relation", []) if v.startswith("BioSample:")]
    require(len(biosamples) <= 1, "Ambiguous BioSample identity")
    issues = ["biological_unit_and_pooling_not_identified"]
    if age != title_age:
        issues.append("age_title_characteristics_conflict")
    if "Flox/" in title and chars["genotype"] == "Wildtype":
        issues.append("genotype_title_characteristics_conflict")
    if assay == "scrna":
        require({note["excerpt"] for note in record["source_notes"]} == {
            "Gene–cell count matrices from four samples were imported", "across the three datasets"},
            "scRNA processing-text discrepancy requires retained source evidence")
        issues.extend(["three_geo_libraries_vs_four_in_processing_text", "one_control_library"])
    if assay == "hic" and "GSE330298" in series:
        require([note["excerpt"] for note in record["source_notes"]] == ["for each genotype were used as input"],
                "Genotype-aggregate warning requires retained source evidence")
        issues.append("processed_cscore_is_genotype_aggregate")
    return {
        "id": record["sample_id"], "series": series, "title": title,
        "organism": fields["!Sample_organism_ch1"][0], "assay": assay,
        "cell_preparation": chars["cell type"], "genotype_reported": chars["genotype"],
        "age_reported": age, "age_in_title": title_age,
        "replicate_label": int(replicate.group(1)) if replicate else None,
        "biosample_id": biosamples[0] if biosamples else None,
        "biological_unit_id": None, "independence": "unresolved", "pooling": "unknown",
        "genome_build": fields["!Sample_data_processing"][0].split(": ", 1)[1], "issues": issues,
    }


def check_manifest(root: Path, entry: dict, schema: dict, source_directory: Path | None = None) -> dict:
    manifest = read_json(verify_artifact(root, entry, schema))
    validate_schema(manifest, schema["$defs"]["dataset_manifest"], "manifest", schema)
    valid_date(manifest["retrieved_on"])
    projection = read_json(verify_artifact(root, manifest["projection"], schema))
    validate_schema(projection, schema["$defs"]["metadata_projection"], "projection", schema)
    require(projection["source_sha256"] == manifest["source"]["sha256"], "Projection full-source hash mismatch")
    records = projection["records"]
    unique([r["sample_id"] for r in records], "projected sample")
    source_lines = [item["line_number"] for record in records for item in record["lines"]]
    unique(source_lines, "source line")
    expected = [project_sample(record) for record in records]
    require(manifest["samples"] == expected, "Normalized samples disagree with retained source facts or overstate biological identity")
    require(manifest["sample_count"] == len(expected), "Sample count mismatch")
    require(all(manifest["accession"] in s["series"] for s in expected), "Sample outside declared series")
    require(not manifest["annotation"]["annotation_file_qualified"], "Annotation qualification needs an admitted reference-file artifact")
    if source_directory is not None:
        filename = manifest["source"]["local_filename"]
        require(PurePosixPath(filename).name == filename, "Full source filename must be a basename")
        full = safe_path(source_directory, filename)
        require(full.is_file(), f"Missing full source: {filename}")
        payload = full.read_bytes()
        require(len(payload) == manifest["source"]["bytes"] and digest(payload) == manifest["source"]["sha256"], "Full source hash/size mismatch")
        lines = payload.decode("utf-8").splitlines()
        for record in records:
            for item in record["lines"]:
                number = item["line_number"]
                require(number <= len(lines) and lines[number - 1] == item["text"], "Projection differs from original source line")
            for note in record["source_notes"]:
                number = note["line_number"]
                require(number <= len(lines) and note["excerpt"] in lines[number - 1], "Retained method excerpt differs from original source line")
    return manifest


def check_semantics(registration: dict, manifests: list[dict]) -> None:
    valid_date(registration["registered_on"])
    valid_date(registration["prior_art"]["searched_on"])
    samples = {s["id"]: s for m in manifests for s in m["samples"]}
    all_ids = [s["id"] for m in manifests for s in m["samples"]]
    unique(all_ids, "GSM across manifests; reused samples require explicit reconciliation")
    biosamples = [samples[s]["biosample_id"] for s in all_ids if samples[s]["biosample_id"] is not None]
    unique(biosamples, "BioSample across libraries; related/reused material requires explicit reconciliation")
    datasets = {m["accession"] for m in manifests}
    require(len(datasets) == len(manifests), "Duplicate dataset manifest")
    require(datasets == {"GSE330298", "GSE89520"}, "This checker version admits only the audited pilot intake")
    # This v1 intake lacks independently identified animals/cultures or an admitted
    # evaluator manifest. Changing labels cannot convert it into confirmation.
    require(registration["mode"] == "descriptive_qualification", "This data intake cannot authorize confirmatory mode")
    require(registration["decision"]["status"] == "data_limited", "Unqualified cohort requires data_limited decision")
    require(registration["decision"]["domain_review"] == "pending" and registration["decision"]["reviewer"] is None,
            "Domain review needs a separately admitted review artifact")
    require(registration["precision"]["biological_replicates"] is None and registration["precision"]["status"] == "not_estimable",
            "Libraries/cells/windows are not verified biological replicate counts")
    require(not registration["multiple_testing"]["inference_enabled"], "Biological inference is unavailable for this intake")
    splits = registration["splits"]
    for name in ("reproduction_sample_ids", "discovery_sample_ids"):
        unique(splits[name], name)
        require(set(splits[name]) <= samples.keys(), f"Unknown samples in {name}")
    require(not set(splits["reproduction_sample_ids"]) & set(splits["discovery_sample_ids"]), "Reproduction/discovery overlap")
    require(set(splits["reproduction_sample_ids"]) == set(all_ids) and not splits["discovery_sample_ids"],
            "All inspected public sources belong to reproduction, not prospective discovery")
    holdout = splits["holdout"]
    require(holdout["status"] == "unselected" and holdout["identity_commitment"] is None, "No independent holdout has been admitted")
    unique([c["id"] for c in registration["contrasts"]], "contrast id")
    for contrast in registration["contrasts"]:
        unique(contrast["sample_ids"], "contrast sample")
        require(set(contrast["sample_ids"]) <= samples.keys(), "Unknown contrast sample")
        chosen = [samples[s] for s in contrast["sample_ids"]]
        require(set(contrast["dataset_ids"]) <= datasets, "Unknown contrast dataset")
        require(all(set(s["series"]) & set(contrast["dataset_ids"]) for s in chosen), "Contrast samples outside datasets")
        require(set(contrast["assays"]) == {s["assay"] for s in chosen}, "Contrast assay mismatch")
        require(contrast["status"] != "confirmatory_eligible" and not contrast["biological_units_known"], "Unsupported confirmatory contrast/biological identity")
        require(not contrast["genome_compatible"] or len({s["genome_build"] for s in chosen}) == 1, "Genome build mismatch")
        require(not contrast["age_compatible"] or (None not in {s["age_reported"] for s in chosen}
                and len({s["age_reported"] for s in chosen}) == 1
                and all("age_title_characteristics_conflict" not in s["issues"] for s in chosen)), "Age compatibility unsupported")
        require(not contrast["preparation_compatible"] or len({s["cell_preparation"] for s in chosen}) == 1, "Cell preparation mismatch")
        if len(contrast["dataset_ids"]) > 1:
            require(contrast["status"] == "excluded" and not contrast["perturbation_matched"], "Study/context/perturbation confounding cannot support confirmation")
        if not all(contrast[k] for k in ("genome_compatible", "age_compatible", "preparation_compatible", "perturbation_matched")):
            require(contrast["status"] != "confirmatory_eligible", "Incompatible contrast admitted")
        if any("genotype_title_characteristics_conflict" in s["issues"] for s in chosen):
            require(contrast["status"] == "excluded", "Ambiguous genotype controls cannot enter analysis")
    unique([f["id"] for f in registration["features"]], "feature id")
    for feature in registration["features"]:
        require(set(feature["source_sample_ids"]) <= samples.keys(), "Unknown feature source")
        if feature["use"] == "prediction":
            require(feature["kind"] == "unperturbed_reference" and feature["availability"] == "unperturbed", "Post-perturbation or unknown features cannot predict pre-perturbation outcomes")
            require(not feature["eligible"], "No predictive feature is admitted before a compatible independent design")
    endpoint_ids = [e["id"] for e in registration["endpoints"]]
    unique(endpoint_ids, "endpoint id")
    for endpoint in registration["endpoints"]:
        require(not endpoint["confirmatory"], "Confirmatory endpoint unavailable")
        if endpoint["kind"] == "biological_prediction":
            require(endpoint["status"] == "blocked" and endpoint["unit"] == "independent_biological_sample", "Biological endpoint requires qualified independent units")
        else:
            require(endpoint["unit"] == "source_row", "Software rows cannot be called biological samples")
    unique([c["id"] for c in registration["controls"]], "control id")
    for control in registration["controls"]:
        require(control["endpoint_id"] in endpoint_ids, "Control endpoint missing")
        if control["kind"] != "unknown_candidate":
            require(not control["eligible_for_novelty"], "Controls and decoys cannot be promoted as novel findings")


def check_candidate(path: Path, registration: dict, root: Path, registration_hash: str) -> None:
    candidate = read_json(path)
    validate_schema(candidate, read_json(root / CANDIDATE_SCHEMA))
    if candidate["novelty"]["reviewed_on"] is not None:
        valid_date(candidate["novelty"]["reviewed_on"])
    require(candidate["study_id"] == registration["study_id"], "Candidate study mismatch")
    require(candidate["provenance"]["registration_sha256"] == registration_hash, "Candidate registration hash mismatch")
    require(set(candidate["provenance"]["source_sample_ids"]) <= set(registration["splits"]["reproduction_sample_ids"]), "Unknown candidate samples")
    schema = read_json(root / SCHEMA)
    for item in candidate["provenance"]["input_artifacts"] + candidate["validation"]["evidence"]:
        verify_artifact(root, item, schema)
    require(not candidate["validation"]["holdout_opened"], "No holdout was admitted")
    require(candidate["observation"]["biological_replicates"] is None, "Candidate overstates biological replication")
    require(candidate["inference"]["scope"] != "independent_association", "No independent association is supported")
    require(candidate["validation"]["status"] != "independent_support", "Independent validation is unavailable")
    require(candidate["novelty"]["status"] != "candidate_unreported", "Novelty review is incomplete")
    if candidate["validation"]["independent_recomputation"]:
        require(bool(candidate["validation"]["evidence"]), "Independent recomputation requires evidence artifacts")
    if candidate["validation"]["status"] == "reproduced_software":
        require(candidate["validation"]["independent_recomputation"], "Reproduction needs independent computation evidence")
    if candidate["classification"] == "software_control":
        require(candidate["inference"]["scope"] == "software_reproduction" and candidate["novelty"]["status"] == "not_applicable_control", "Software controls cannot become biological discoveries")
    if candidate["classification"] == "known_biology":
        require(candidate["novelty"]["status"] == "known", "Known biology cannot be novel")


def check_registration(campaign: Path, root: Path = ROOT, source_directory: Path | None = None, candidate: Path | None = None) -> dict:
    schema = read_json(root / SCHEMA)
    registration_path = campaign / "registration.json"
    registration = read_json(registration_path)
    validate_schema(registration, schema)
    freeze = read_json(campaign / "freeze.json")
    expected_freeze = {
        "schema_version": "1", "study_id": registration["study_id"],
        "registration_sha256": digest(registration_path.read_bytes()),
        "study_schema_sha256": digest((root / SCHEMA).read_bytes()),
        "candidate_schema_sha256": digest((root / CANDIDATE_SCHEMA).read_bytes()),
    }
    require(freeze == expected_freeze, "Registration/schema freeze changed; create and review an explicit new registration")
    manifests = [check_manifest(root, item, schema, source_directory) for item in registration["dataset_manifests"]]
    check_semantics(registration, manifests)
    audit = read_json(verify_artifact(root, registration["author_code"]["audit_artifact"], schema))
    require(audit["revision"] == registration["author_code"]["revision"]
            and audit["url"] == registration["author_code"]["url"]
            and audit["tree_truncated"] is False and audit["license_file_found"] is False,
            "Author code audit does not match its declared identity or qualification")
    fixture = registration["qualification_fixture"]
    require(fixture["expected"]["path"] == "tests/fixtures/bio/expected.json", "Unexpected qualification reference")
    fixture_paths = [item["path"] for item in fixture["inputs"]]
    unique(fixture_paths, "qualification fixture input")
    require(set(fixture_paths) == {f"tests/fixtures/bio/{name}" for name in (
        "rna-counts.tsv", "rna-provenance.json", "cscore-plus.bedgraph", "cscore-minus.bedgraph",
        "cscore-plus-provenance.json", "cscore-minus-provenance.json")}, "Qualification input manifest is incomplete")
    expected = read_json(verify_artifact(root, fixture["expected"], schema))
    require(expected == {"rna_genes": 128, "rna_passing": 28, "chromatin_intervals": 64, "chromatin_mean_delta": "0.04620996875"}, "Registered qualification expectations changed")
    for item in fixture["inputs"]:
        verify_artifact(root, item, schema)
    if candidate is not None:
        check_candidate(candidate, registration, root, expected_freeze["registration_sha256"])
    counts = Counter(s["assay"] for manifest in manifests for s in manifest["samples"])
    return {"status": "ok", "study_id": registration["study_id"], "outcome": "data_limited",
            "datasets": len(manifests), "libraries": sum(counts.values()), "assays": dict(sorted(counts.items())),
            "verified_independent_biological_units": 0, "confirmatory_contrasts": 0,
            "full_source_verification": source_directory is not None}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--source-directory", type=Path, help="Optional external full-source directory; no downloads are performed")
    parser.add_argument("--candidate", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(check_registration(args.campaign, source_directory=args.source_directory, candidate=args.candidate), sort_keys=True))
    except (RegistrationError, OSError, KeyError, TypeError, UnicodeError) as exc:
        print(f"registration rejected: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
