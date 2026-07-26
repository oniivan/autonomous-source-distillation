#!/usr/bin/env python3
"""Audit a structured long-material distillation bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ALLOWED_CLAIM_STATUSES = {
    "source-only",
    "externally-verified",
    "contradicted",
    "uncertain",
    "inference",
    "superseded",
}
ALLOWED_FACET_STATUSES = {"covered", "absent", "not-applicable", "unresolved"}
ALLOWED_EVIDENCE_POLARITIES = {
    "supports",
    "opposes",
    "qualifies",
    "context",
    "uncertainty",
}
ALLOWED_RISK_STATUSES = {"pass", "fail", "not-applicable", "unresolved"}
REQUIRED_TEXT_FILES = ("run-manifest.md", "synthesis.md", "handoff.md")


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        errors.append(f"missing file: {path.name}")
        return rows
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc.msg}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:{line_number}: row must be an object")
            continue
        rows.append(value)
    return rows


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"missing file: {path.name}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON: {exc.msg}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name}: root must be an object")
        return {}
    return value


def require_string(row: dict[str, Any], field: str, label: str, errors: list[str]) -> str:
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {field} must be a non-empty string")
        return ""
    return value


def require_string_list(
    row: dict[str, Any], field: str, label: str, errors: list[str]
) -> list[str]:
    value = row.get(field)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{label}: {field} must be a list of non-empty strings")
        return []
    return value


def index_rows(
    rows: list[dict[str, Any]], field: str, file_name: str, errors: list[str]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        label = f"{file_name}:{position}"
        row_id = require_string(row, field, label, errors)
        if not row_id:
            continue
        if row_id in result:
            errors.append(f"{label}: duplicate {field} {row_id}")
            continue
        result[row_id] = row
    return result


def audit_sources(
    rows: list[dict[str, Any]], errors: list[str]
) -> dict[str, dict[str, Any]]:
    sources = index_rows(rows, "source_id", "sources.jsonl", errors)
    for source_id, row in sources.items():
        label = f"source {source_id}"
        for field in (
            "source_ref",
            "revision",
            "material_type",
            "locator_scheme",
        ):
            require_string(row, field, label, errors)
        instruction_trust = require_string(row, "instruction_trust", label, errors)
        if instruction_trust and instruction_trust != "data-only":
            errors.append(f"{label}: instruction_trust must be data-only")
        limits = row.get("representation_limits")
        if not isinstance(limits, list) or any(not isinstance(item, str) for item in limits):
            errors.append(f"{label}: representation_limits must be a list of strings")
        if row.get("coverage_mode") == "contiguous-lines":
            line_count = row.get("line_count")
            if (
                not isinstance(line_count, int)
                or isinstance(line_count, bool)
                or line_count < 0
            ):
                errors.append(
                    f"{label}: contiguous-lines coverage needs a non-negative line_count"
                )
    return sources


def audit_chunks(
    rows: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    chunks = index_rows(rows, "chunk_id", "chunks.jsonl", errors)
    by_source: dict[str, list[dict[str, Any]]] = {}
    for chunk_id, row in chunks.items():
        label = f"chunk {chunk_id}"
        source_id = require_string(row, "source_id", label, errors)
        if source_id not in sources:
            errors.append(f"{label}: unknown source_id {source_id}")
        ordinal = row.get("ordinal")
        if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 1:
            errors.append(f"{label}: ordinal must be a positive integer")
        by_source.setdefault(source_id, []).append(row)

        line_fields = ("content_line_start", "content_line_end")
        if any(field in row for field in line_fields):
            start = row.get("content_line_start")
            end = row.get("content_line_end")
            if not isinstance(start, int) or not isinstance(end, int) or start < 1 or end < start:
                errors.append(f"{label}: invalid unique-content line range")
            loaded_start = row.get("line_start")
            loaded_end = row.get("line_end")
            if (
                not isinstance(loaded_start, int)
                or not isinstance(loaded_end, int)
                or loaded_start < 1
                or loaded_end < loaded_start
                or (isinstance(start, int) and start < loaded_start)
                or (isinstance(end, int) and end > loaded_end)
            ):
                errors.append(f"{label}: invalid loaded line range")
            overlap_count = row.get("overlap_line_count", 0)
            if not isinstance(overlap_count, int) or overlap_count < 0:
                errors.append(f"{label}: overlap_line_count must be a non-negative integer")
            elif overlap_count and isinstance(start, int):
                if not isinstance(loaded_start, int) or loaded_start >= start:
                    errors.append(
                        f"{label}: overlap must precede content_line_start in loaded range"
                    )

    for source_id, source_chunks in by_source.items():
        ordinals = sorted(
            row["ordinal"] for row in source_chunks if isinstance(row.get("ordinal"), int)
        )
        if ordinals and ordinals != list(range(1, len(ordinals) + 1)):
            errors.append(f"source {source_id}: chunk ordinals must be contiguous from 1")

        source = sources.get(source_id, {})
        if source.get("coverage_mode") != "contiguous-lines":
            continue
        ranged = [
            row
            for row in source_chunks
            if isinstance(row.get("content_line_start"), int)
            and isinstance(row.get("content_line_end"), int)
        ]
        ranged.sort(key=lambda row: row["content_line_start"])
        if len(ranged) != len(source_chunks):
            errors.append(
                f"source {source_id}: contiguous-lines coverage requires ranges on every chunk"
            )
            continue
        expected = 1
        for row in ranged:
            start = row["content_line_start"]
            end = row["content_line_end"]
            if start != expected:
                kind = "overlap" if start < expected else "gap"
                errors.append(
                    f"source {source_id}: unique-content {kind} before line {start}; "
                    f"expected {expected}"
                )
            expected = max(expected, end + 1)
        line_count = source.get("line_count")
        if isinstance(line_count, int) and expected - 1 != line_count:
            errors.append(
                f"source {source_id}: unique-content ends at {expected - 1}, "
                f"expected line_count {line_count}"
            )
    return chunks


def audit_notes(
    rows: list[dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    notes = index_rows(rows, "chunk_id", "chunk-notes.jsonl", errors)
    missing = sorted(set(chunks) - set(notes))
    extra = sorted(set(notes) - set(chunks))
    if missing:
        errors.append(f"chunk-notes.jsonl: missing notes for {', '.join(missing)}")
    if extra:
        errors.append(f"chunk-notes.jsonl: unknown chunk IDs {', '.join(extra)}")

    for chunk_id, row in notes.items():
        label = f"chunk note {chunk_id}"
        status = row.get("status")
        if status not in {"distilled", "skipped"}:
            errors.append(f"{label}: status must be distilled or skipped")
        if status == "distilled":
            require_string(row, "gist", label, errors)
        if status == "skipped":
            require_string(row, "skip_reason", label, errors)
        require_string_list(row, "evidence_ids", label, errors)
    return notes


def audit_evidence(
    rows: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    evidence = index_rows(rows, "evidence_id", "evidence.jsonl", errors)
    for evidence_id, row in evidence.items():
        label = f"evidence {evidence_id}"
        source_id = require_string(row, "source_id", label, errors)
        chunk_id = require_string(row, "chunk_id", label, errors)
        require_string(row, "locator", label, errors)
        require_string(row, "statement", label, errors)
        polarity = require_string(row, "polarity", label, errors)
        if polarity and polarity not in ALLOWED_EVIDENCE_POLARITIES:
            errors.append(
                f"{label}: polarity must be one of "
                f"{', '.join(sorted(ALLOWED_EVIDENCE_POLARITIES))}"
            )
        if source_id not in sources:
            errors.append(f"{label}: unknown source_id {source_id}")
        if chunk_id not in chunks:
            errors.append(f"{label}: unknown chunk_id {chunk_id}")
        elif chunks[chunk_id].get("source_id") != source_id:
            errors.append(f"{label}: source_id does not match its chunk")
        duplicate_of = row.get("duplicate_of")
        if duplicate_of is not None and (
            not isinstance(duplicate_of, str) or not duplicate_of.strip()
        ):
            errors.append(f"{label}: duplicate_of must be null or a non-empty string")

    for evidence_id, row in evidence.items():
        duplicate_of = row.get("duplicate_of")
        if duplicate_of is not None:
            if duplicate_of == evidence_id:
                errors.append(f"evidence {evidence_id}: duplicate_of cannot reference itself")
            elif duplicate_of not in evidence:
                errors.append(
                    f"evidence {evidence_id}: unknown duplicate_of {duplicate_of}"
                )
            elif evidence[duplicate_of].get("source_id") != row.get("source_id"):
                errors.append(
                    f"evidence {evidence_id}: duplicate_of must remain within one source"
                )

    for evidence_id in evidence:
        seen: set[str] = set()
        current = evidence_id
        while current in evidence:
            if current in seen:
                errors.append(f"evidence {evidence_id}: duplicate_of cycle detected")
                break
            seen.add(current)
            duplicate_of = evidence[current].get("duplicate_of")
            if not isinstance(duplicate_of, str) or duplicate_of not in evidence:
                break
            current = duplicate_of
    return evidence


def audit_note_evidence(
    notes: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    for chunk_id, row in notes.items():
        evidence_ids = row.get("evidence_ids")
        if not isinstance(evidence_ids, list):
            continue
        valid_ids = [
            evidence_id for evidence_id in evidence_ids if isinstance(evidence_id, str)
        ]
        if len(valid_ids) != len(set(valid_ids)):
            errors.append(f"chunk note {chunk_id}: evidence_ids must be unique")
        for evidence_id in valid_ids:
            if evidence_id not in evidence:
                errors.append(f"chunk note {chunk_id}: unknown evidence_id {evidence_id}")
            elif evidence[evidence_id].get("chunk_id") != chunk_id:
                errors.append(
                    f"chunk note {chunk_id}: evidence {evidence_id} belongs to "
                    f"{evidence[evidence_id].get('chunk_id')}"
                )
    for evidence_id, row in evidence.items():
        chunk_id = row.get("chunk_id")
        note_ids = notes.get(chunk_id, {}).get("evidence_ids", [])
        if not isinstance(note_ids, list) or evidence_id not in note_ids:
            errors.append(
                f"evidence {evidence_id}: not listed by chunk note {chunk_id}"
            )


def audit_claims(
    rows: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    claims = index_rows(rows, "claim_id", "claims.jsonl", errors)
    for claim_id, row in claims.items():
        label = f"claim {claim_id}"
        require_string(row, "claim", label, errors)
        require_string(row, "type", label, errors)
        status = row.get("status")
        if status not in ALLOWED_CLAIM_STATUSES:
            errors.append(
                f"{label}: status must be one of {', '.join(sorted(ALLOWED_CLAIM_STATUSES))}"
            )
        evidence_ids = require_string_list(row, "evidence_ids", label, errors)
        if len(evidence_ids) != len(set(evidence_ids)):
            errors.append(f"{label}: evidence_ids must be unique")
        for evidence_id in evidence_ids:
            if evidence_id not in evidence:
                errors.append(f"{label}: unknown evidence_id {evidence_id}")
        if status != "inference" and not evidence_ids:
            errors.append(f"{label}: non-inference claim needs evidence")
        source_ids = require_string_list(row, "independent_source_ids", label, errors)
        if len(source_ids) != len(set(source_ids)):
            errors.append(f"{label}: independent_source_ids must be unique")
        for source_id in source_ids:
            if source_id not in sources:
                errors.append(f"{label}: unknown independent source {source_id}")
        evidence_source_ids = {
            evidence[evidence_id].get("source_id")
            for evidence_id in evidence_ids
            if evidence_id in evidence
        }
        unsupported_source_ids = set(source_ids) - evidence_source_ids
        if unsupported_source_ids:
            errors.append(
                f"{label}: independent sources lack claim evidence: "
                f"{', '.join(sorted(unsupported_source_ids))}"
            )
        verification_refs = require_string_list(row, "verification_refs", label, errors)
        if status == "externally-verified" and not verification_refs:
            errors.append(f"{label}: externally-verified needs verification_refs")
    return claims


def audit_coverage(
    coverage: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    notes: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    source_entries = coverage.get("sources")
    if not isinstance(source_entries, list):
        errors.append("coverage.json: sources must be a list")
        source_entries = []

    indexed: dict[str, dict[str, Any]] = {}
    for position, entry in enumerate(source_entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"coverage.json source {position}: must be an object")
            continue
        source_id = require_string(
            entry, "source_id", f"coverage source {position}", errors
        )
        if source_id in indexed:
            errors.append(f"coverage.json: duplicate source_id {source_id}")
        elif source_id:
            indexed[source_id] = entry
    if set(indexed) != set(sources):
        errors.append("coverage.json: source IDs must exactly match sources.jsonl")

    for source_id, entry in indexed.items():
        planned_list = require_string_list(
            entry, "planned_chunks", f"coverage {source_id}", errors
        )
        if len(planned_list) != len(set(planned_list)):
            errors.append(f"coverage {source_id}: planned_chunks must be unique")
        planned = set(planned_list)
        actual = {
            chunk_id
            for chunk_id, row in chunks.items()
            if row.get("source_id") == source_id
        }
        if not actual:
            require_string(entry, "source_skip_reason", f"coverage {source_id}", errors)
        if planned != actual:
            errors.append(f"coverage {source_id}: planned_chunks do not match chunks.jsonl")

        distilled_list = require_string_list(
            entry, "distilled_chunks", f"coverage {source_id}", errors
        )
        if len(distilled_list) != len(set(distilled_list)):
            errors.append(f"coverage {source_id}: distilled_chunks must be unique")
        distilled = set(distilled_list)
        expected_distilled = {
            chunk_id
            for chunk_id in actual
            if notes.get(chunk_id, {}).get("status") == "distilled"
        }
        if distilled != expected_distilled:
            errors.append(
                f"coverage {source_id}: distilled_chunks do not match chunk notes"
            )

        skipped_raw = entry.get("skipped_chunks")
        if not isinstance(skipped_raw, list):
            errors.append(f"coverage {source_id}: skipped_chunks must be a list")
            skipped_raw = []
        skipped: set[str] = set()
        for item in skipped_raw:
            if not isinstance(item, dict):
                errors.append(f"coverage {source_id}: skipped entry must be an object")
                continue
            chunk_id = require_string(
                item, "chunk_id", f"coverage {source_id} skipped", errors
            )
            require_string(item, "reason", f"coverage {source_id} skipped", errors)
            if chunk_id:
                if chunk_id in skipped:
                    errors.append(
                        f"coverage {source_id}: skipped_chunks must be unique"
                    )
                skipped.add(chunk_id)
        expected_skipped = {
            chunk_id
            for chunk_id in actual
            if notes.get(chunk_id, {}).get("status") == "skipped"
        }
        if skipped != expected_skipped:
            errors.append(f"coverage {source_id}: skipped_chunks do not match chunk notes")

    facets = coverage.get("facets")
    if not isinstance(facets, list):
        errors.append("coverage.json: facets must be a list")
        return
    facet_names: set[str] = set()
    for position, facet in enumerate(facets, start=1):
        if not isinstance(facet, dict):
            errors.append(f"coverage facet {position}: must be an object")
            continue
        label = f"coverage facet {position}"
        facet_name = require_string(facet, "facet", label, errors)
        if facet_name in facet_names:
            errors.append(f"{label}: duplicate facet {facet_name}")
        elif facet_name:
            facet_names.add(facet_name)
        status = facet.get("status")
        if status not in ALLOWED_FACET_STATUSES:
            errors.append(
                f"{label}: status must be one of {', '.join(sorted(ALLOWED_FACET_STATUSES))}"
            )
        evidence_ids = require_string_list(facet, "evidence_ids", label, errors)
        for evidence_id in evidence_ids:
            if evidence_id not in evidence:
                errors.append(f"{label}: unknown evidence_id {evidence_id}")
        if status == "covered" and not evidence_ids:
            errors.append(f"{label}: covered facet needs evidence_ids")
        if status == "absent":
            require_string(facet, "search_note", label, errors)
        if status in {"not-applicable", "unresolved"}:
            require_string(facet, "reason", label, errors)

    risk_checks = coverage.get("risk_checks")
    if not isinstance(risk_checks, list):
        errors.append("coverage.json: risk_checks must be a list")
        return
    for position, risk_check in enumerate(risk_checks, start=1):
        if not isinstance(risk_check, dict):
            errors.append(f"coverage risk {position}: must be an object")
            continue
        label = f"coverage risk {position}"
        require_string(risk_check, "risk", label, errors)
        status = risk_check.get("status")
        if status not in ALLOWED_RISK_STATUSES:
            errors.append(
                f"{label}: status must be one of "
                f"{', '.join(sorted(ALLOWED_RISK_STATUSES))}"
            )
        reviewed_chunks = require_string_list(
            risk_check, "reviewed_chunks", label, errors
        )
        if len(reviewed_chunks) != len(set(reviewed_chunks)):
            errors.append(f"{label}: reviewed_chunks must be unique")
        for chunk_id in reviewed_chunks:
            if chunk_id not in chunks:
                errors.append(f"{label}: unknown reviewed chunk {chunk_id}")
        if status in {"pass", "fail"} and not reviewed_chunks:
            errors.append(f"{label}: {status} needs reviewed_chunks")
        if status in {"not-applicable", "unresolved"}:
            require_string(risk_check, "reason", label, errors)


def audit_bundle(workdir: Path) -> dict[str, Any]:
    errors: list[str] = []
    for file_name in REQUIRED_TEXT_FILES:
        path = workdir / file_name
        if not path.is_file():
            errors.append(f"missing file: {file_name}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"empty file: {file_name}")

    source_rows = load_jsonl(workdir / "sources.jsonl", errors)
    chunk_rows = load_jsonl(workdir / "chunks.jsonl", errors)
    note_rows = load_jsonl(workdir / "chunk-notes.jsonl", errors)
    evidence_rows = load_jsonl(workdir / "evidence.jsonl", errors)
    claim_rows = load_jsonl(workdir / "claims.jsonl", errors)
    coverage = load_json(workdir / "coverage.json", errors)

    sources = audit_sources(source_rows, errors)
    if not sources:
        errors.append("sources.jsonl: at least one source is required")
    chunks = audit_chunks(chunk_rows, sources, errors)
    notes = audit_notes(note_rows, chunks, errors)
    evidence = audit_evidence(evidence_rows, sources, chunks, errors)
    audit_note_evidence(notes, evidence, errors)
    claims = audit_claims(claim_rows, sources, evidence, errors)
    audit_coverage(coverage, sources, chunks, notes, evidence, errors)

    return {
        "status": "pass" if not errors else "fail",
        "counts": {
            "sources": len(sources),
            "chunks": len(chunks),
            "chunk_notes": len(notes),
            "evidence": len(evidence),
            "claims": len(claims),
        },
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a structured long-material distillation bundle."
    )
    parser.add_argument("workdir", type=Path, help="Bundle directory to audit.")
    args = parser.parse_args()

    receipt = audit_bundle(args.workdir.resolve())
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
