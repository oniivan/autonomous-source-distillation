#!/usr/bin/env python3
"""Run preserved v3 false-green and malformed-input mutations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "assets" / "starter-bundle"
AUDITOR_PATH = ROOT / "scripts" / "audit_bundle.py"


def load_auditor():
    spec = importlib.util.spec_from_file_location("mutation_audit_bundle", AUDITOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bundle auditor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def mutate_jsonl(
    root: Path,
    name: str,
    mutate: Callable[[list[dict[str, Any]]], None],
) -> None:
    path = root / name
    rows = load_jsonl(path)
    mutate(rows)
    write_jsonl(path, rows)


def mutate_json(
    root: Path,
    name: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    path = root / name
    value = load_json(path)
    mutate(value)
    write_json(path, value)


def skipped_evidence(root: Path) -> None:
    def change(rows: list[dict[str, Any]]) -> None:
        rows[0].update(
            status="skipped",
            skip_reason="duplicate appendix",
            propositions=[],
        )

    mutate_jsonl(root, "chunk-notes.jsonl", change)


def canonical_alias(root: Path) -> None:
    evidence = load_jsonl(root / "evidence.jsonl")
    alias = copy.deepcopy(evidence[0])
    alias["evidence_id"] = "E5"
    alias["duplicate_of"] = "E1"
    evidence.append(alias)
    write_jsonl(root / "evidence.jsonl", evidence)

    mutate_jsonl(
        root,
        "chunk-notes.jsonl",
        lambda rows: rows[0]["evidence_ids"].append("E5"),
    )
    mutate_jsonl(
        root,
        "claims.jsonl",
        lambda rows: rows[0]["evidence_ids"].append("E5"),
    )


def readiness_failures(root: Path) -> None:
    def change(value: dict[str, Any]) -> None:
        for facet in value["facets"]:
            if facet["facet"] == "limitations":
                facet.clear()
                facet.update(
                    facet="limitations",
                    status="unresolved",
                    evidence_ids=[],
                    reason="not adjudicated",
                )
        for risk in value["risk_checks"]:
            if risk["risk"] == "boundary":
                risk["status"] = "fail"

    mutate_json(root, "coverage.json", change)


def all_skipped(root: Path) -> None:
    write_jsonl(root / "evidence.jsonl", [])
    write_jsonl(root / "claims.jsonl", [])

    def change_notes(rows: list[dict[str, Any]]) -> None:
        rows[0] = {
            "schema_version": 3,
            "chunk_id": rows[0]["chunk_id"],
            "status": "skipped",
            "skip_reason": "no relevant content",
            "propositions": [],
            "evidence_ids": [],
        }

    mutate_jsonl(root, "chunk-notes.jsonl", change_notes)

    def change_coverage(value: dict[str, Any]) -> None:
        source = value["sources"][0]
        source["distilled_chunks"] = []
        source["skipped_chunks"] = [
            {
                "chunk_id": source["planned_chunks"][0],
                "reason": "no relevant content",
            }
        ]
        value["facets"] = [
            {
                "facet": "result",
                "status": "absent",
                "evidence_ids": [],
                "search_note": "Reviewed the only planned chunk.",
            },
            {
                "facet": "limitations",
                "status": "absent",
                "evidence_ids": [],
                "search_note": "Reviewed the only planned chunk.",
            },
        ]

    mutate_json(root, "coverage.json", change_coverage)
    mutate_json(
        root,
        "run-manifest.json",
        lambda value: value["handoff"].update(key_claim_ids=[]),
    )


def duplicate_json_key(root: Path) -> None:
    path = root / "sources.jsonl"
    rows = load_jsonl(path)
    first = json.dumps(rows[0], sort_keys=True)
    first = first.replace(
        '"source_id": "S1"',
        '"source_id": "S1", "source_id": "S2"',
        1,
    )
    path.write_text(
        first
        + "\n"
        + "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows[1:]),
        encoding="utf-8",
    )


def nonfinite_json_number(root: Path) -> None:
    path = root / "coverage.json"
    path.write_text(
        path.read_text(encoding="utf-8").rstrip()[:-1]
        + ', "nonstandard": NaN}\n',
        encoding="utf-8",
    )


def forged_chunk_text(root: Path) -> None:
    text = "fabricated\ncontent"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    mutate_jsonl(
        root,
        "chunks.jsonl",
        lambda rows: rows[0].update(
            text=text,
            chunk_sha256=digest,
            content_sha256=digest,
        ),
    )


def wrong_chunk_line_cardinality(root: Path) -> None:
    text = "The launch review recorded a provisional November window."
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    mutate_jsonl(
        root,
        "chunks.jsonl",
        lambda rows: rows[0].update(
            text=text,
            chunk_sha256=digest,
            content_sha256=digest,
        ),
    )


def fake_semantic_receipt(root: Path) -> None:
    mutate_json(
        root,
        "run-manifest.json",
        lambda value: value.update(
            semantic_evaluation_required=True,
            semantic_evaluation_receipt="semantic-receipt.json",
        ),
    )
    (root / "semantic-receipt.json").write_text(
        "not a semantic receipt\n",
        encoding="utf-8",
    )


def mutation_cases() -> list[
    tuple[str, Callable[[Path], None], str, str]
]:
    return [
        ("baseline", lambda root: None, "pass", "pass"),
        (
            "unsupported_schema",
            lambda root: mutate_jsonl(
                root,
                "chunks.jsonl",
                lambda rows: rows[0].update(schema_version=999),
            ),
            "fail",
            "fail",
        ),
        (
            "source_hash_skew",
            lambda root: mutate_jsonl(
                root,
                "chunks.jsonl",
                lambda rows: rows[0].update(source_sha256="0" * 64),
            ),
            "fail",
            "fail",
        ),
        ("forged_chunk_text", forged_chunk_text, "fail", "fail"),
        (
            "wrong_chunk_line_cardinality",
            wrong_chunk_line_cardinality,
            "fail",
            "fail",
        ),
        (
            "unknown_coverage_mode",
            lambda root: mutate_jsonl(
                root,
                "sources.jsonl",
                lambda rows: rows[0].update(
                    coverage_mode="contigous-lines",
                    line_count=999,
                ),
            ),
            "fail",
            "fail",
        ),
        ("skipped_note_owns_evidence", skipped_evidence, "fail", "fail"),
        (
            "superseded_without_lineage",
            lambda root: mutate_jsonl(
                root,
                "claims.jsonl",
                lambda rows: rows[0].update(lifecycle_status="superseded"),
            ),
            "fail",
            "fail",
        ),
        (
            "opposition_declared_as_support",
            lambda root: mutate_jsonl(
                root,
                "evidence.jsonl",
                lambda rows: rows[0].update(polarity="opposes"),
            ),
            "fail",
            "fail",
        ),
        ("canonical_duplicate_inflation", canonical_alias, "fail", "fail"),
        (
            "duplicate_facet_evidence",
            lambda root: mutate_json(
                root,
                "coverage.json",
                lambda value: value["facets"][0].update(
                    evidence_ids=["E2", "E2"]
                ),
            ),
            "fail",
            "fail",
        ),
        (
            "boolean_line_ranges",
            lambda root: mutate_jsonl(
                root,
                "chunks.jsonl",
                lambda rows: rows[0].update(
                    line_start=True,
                    line_end=True,
                    content_line_start=True,
                    content_line_end=True,
                    overlap_line_count=False,
                ),
            ),
            "fail",
            "fail",
        ),
        ("failed_risk_and_unresolved_facet", readiness_failures, "pass", "fail"),
        (
            "heading_only_markdown",
            lambda root: [
                (root / name).write_text(f"# {name}\n", encoding="utf-8")
                for name in ("run-manifest.md", "synthesis.md", "handoff.md")
            ],
            "pass",
            "fail",
        ),
        (
            "invalid_note_status_type",
            lambda root: mutate_jsonl(
                root,
                "chunk-notes.jsonl",
                lambda rows: rows[0].update(status=["distilled"]),
            ),
            "fail",
            "fail",
        ),
        (
            "invalid_claim_status_type",
            lambda root: mutate_jsonl(
                root,
                "claims.jsonl",
                lambda rows: rows[0].update(verification_status=["source-only"]),
            ),
            "fail",
            "fail",
        ),
        (
            "invalid_duplicate_type",
            lambda root: mutate_jsonl(
                root,
                "evidence.jsonl",
                lambda rows: rows[0].update(duplicate_of=["E0"]),
            ),
            "fail",
            "fail",
        ),
        (
            "invalid_evidence_chunk_type",
            lambda root: mutate_jsonl(
                root,
                "evidence.jsonl",
                lambda rows: rows[0].update(chunk_id={"bad": "shape"}),
            ),
            "fail",
            "fail",
        ),
        (
            "invalid_evidence_source_type",
            lambda root: mutate_jsonl(
                root,
                "evidence.jsonl",
                lambda rows: rows[0].update(source_id=["S1"]),
            ),
            "fail",
            "fail",
        ),
        (
            "impossible_line_locator",
            lambda root: mutate_jsonl(
                root,
                "evidence.jsonl",
                lambda rows: rows[0].update(locator="line 112"),
            ),
            "fail",
            "fail",
        ),
        (
            "invalid_utf8",
            lambda root: (root / "evidence.jsonl").write_bytes(b"\xff\n"),
            "fail",
            "fail",
        ),
        ("duplicate_json_key", duplicate_json_key, "fail", "fail"),
        ("nonfinite_json_number", nonfinite_json_number, "fail", "fail"),
        ("fake_semantic_receipt", fake_semantic_receipt, "pass", "fail"),
        ("all_skipped", all_skipped, "pass", "fail"),
    ]


def run_suite() -> dict[str, Any]:
    auditor = load_auditor()
    results: list[dict[str, Any]] = []
    for name, mutate, expected_structure, expected_readiness in mutation_cases():
        with tempfile.TemporaryDirectory(prefix="asd-mutation-") as temp:
            root = Path(temp) / "bundle"
            shutil.copytree(STARTER, root)
            exception = ""
            try:
                mutate(root)
                receipt = auditor.audit_bundle(root)
            except Exception as exc:
                exception = f"{type(exc).__name__}: {exc}"
                receipt = {
                    "structure_status": "exception",
                    "readiness_status": "exception",
                    "errors": [],
                    "readiness_errors": [],
                }
            matches = (
                not exception
                and receipt.get("structure_status") == expected_structure
                and receipt.get("readiness_status") == expected_readiness
            )
            results.append(
                {
                    "case": name,
                    "status": "pass" if matches else "fail",
                    "expected_structure_status": expected_structure,
                    "observed_structure_status": receipt.get("structure_status"),
                    "expected_readiness_status": expected_readiness,
                    "observed_readiness_status": receipt.get("readiness_status"),
                    "exception": exception or None,
                    "errors": receipt.get("errors", []),
                    "readiness_errors": receipt.get("readiness_errors", []),
                }
            )
    return {
        "schema_version": 1,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "pass"
            if all(result["status"] == "pass" for result in results)
            else "fail"
        ),
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    receipt = run_suite()
    rendered = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
