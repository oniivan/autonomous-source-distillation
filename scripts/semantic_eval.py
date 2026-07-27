#!/usr/bin/env python3
"""Stage and score sealed fresh-agent semantic distillation evaluations."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from evaluation_contract import file_surface  # noqa: E402
from locator_utils import exact_line_set  # noqa: E402
from runtime_contract import (  # noqa: E402
    runtime_digest,
    stage_runtime,
    validate_runtime_root,
)

EVAL_ROOT = ROOT / "evals" / "semantic"
FIXTURES = EVAL_ROOT / "fixtures"
ORACLE = EVAL_ROOT / "oracles" / "expected.json"
AUDIT_SCRIPT = ROOT / "scripts" / "audit_bundle.py"
CASE_NAMES = (
    "C-boundary-overlap",
    "D-source-composition-order-a",
    "D-source-composition-order-b",
    "G-incremental-correction",
    "I-cold-reconstruction",
)
EVALUATOR_SURFACE_PATHS = (
    "scripts/evaluation_contract.py",
    "scripts/locator_utils.py",
    "scripts/runtime_contract.py",
    "scripts/semantic_eval.py",
)


def load_auditor(audit_script: Path = AUDIT_SCRIPT):
    spec = importlib.util.spec_from_file_location("semantic_eval_auditor", audit_script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bundle auditor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluator_surface() -> dict[str, Any]:
    return file_surface(ROOT, EVALUATOR_SURFACE_PATHS)


def tree_digest(root: Path, *, excluded_parts: set[str] | None = None) -> str:
    excluded_parts = excluded_parts or set()
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative = path.relative_to(root)
        if any(part in excluded_parts for part in relative.parts):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw.strip():
            continue
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def prepare(run_dir: Path, skill_root: Path = ROOT) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    validate_runtime_root(skill_root)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError("run directory must be absent or empty")
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = run_dir / "runtime"
    runtime_manifest = stage_runtime(skill_root, runtime_root)
    cases_dir = run_dir / "cases"
    cases_dir.mkdir()

    fixture_hashes: dict[str, str] = {}
    case_input_hashes: dict[str, str] = {}
    cases: list[dict[str, str]] = []
    for case_name in CASE_NAMES:
        source = FIXTURES / case_name
        target = cases_dir / case_name
        shutil.copytree(source, target)
        fixture_hashes[case_name] = tree_digest(source)
        case_input_hashes[case_name] = tree_digest(
            target,
            excluded_parts={"output"},
        )
        cases.append(
            {
                "case_id": case_name,
                "case_dir": str(target),
                "task": str(target / "task.md"),
                "output_dir": str(target / "output"),
            }
        )

    current_evaluator_surface = evaluator_surface()
    metadata = {
        "schema_version": 1,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "skill_root": str(runtime_root),
        "skill_tree_sha256": runtime_manifest["skill_tree_sha256"],
        "evaluator_sha256": sha256_file(Path(__file__)),
        "evaluator_surface": current_evaluator_surface,
        "oracle_sha256": sha256_file(ORACLE),
        "runtime_isolation": runtime_manifest,
        "fixture_hashes": fixture_hashes,
        "case_input_hashes": case_input_hashes,
        "oracle_copied_to_run": False,
        "cases": cases,
    }
    write_json(run_dir / "run-metadata.json", metadata)
    return metadata


def term_groups_present(text: str, groups: Iterable[Iterable[str]]) -> bool:
    normalized = text.casefold()
    return all(any(term.casefold() in normalized for term in group) for group in groups)


def require_equal(
    errors: list[str],
    actual: Any,
    expected: Any,
    label: str,
) -> None:
    if actual != expected:
        errors.append(f"{label}: expected {expected!r}, got {actual!r}")


def require_set(
    errors: list[str],
    actual: Any,
    expected: list[str],
    label: str,
) -> None:
    if not isinstance(actual, list) or any(not isinstance(item, str) for item in actual):
        errors.append(f"{label}: expected a list of strings")
        return
    if set(actual) != set(expected) or len(actual) != len(set(actual)):
        errors.append(f"{label}: expected exactly {sorted(expected)!r}, got {actual!r}")


def index_rows(
    output: Path,
    file_name: str,
    id_field: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    path = output / file_name
    try:
        rows = load_jsonl(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"{file_name}: cannot load: {exc}")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        row_id = row.get(id_field)
        if isinstance(row_id, str):
            indexed[row_id] = row
    return indexed


def load_semantic_result(output: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return load_json(output / "semantic-result.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        errors.append(f"semantic-result.json: cannot load: {exc}")
        return {}


def audit_output(
    output: Path,
    errors: list[str],
    auditor: Any,
) -> dict[str, Any]:
    receipt = auditor.audit_bundle(output)
    if receipt.get("structure_status") != "pass":
        errors.append("bundle structure_status is not pass")
    if receipt.get("readiness_status") != "pass":
        errors.append("bundle readiness_status is not pass")
    return receipt


def score_boundary(
    output: Path,
    oracle: dict[str, Any],
    auditor: Any,
) -> dict[str, Any]:
    errors: list[str] = []
    audit = audit_output(output, errors, auditor)
    result = load_semantic_result(output, errors)
    require_equal(errors, result.get("case_id"), "C-boundary-overlap", "case_id")
    require_equal(errors, result.get("probe_id"), oracle["probe_id"], "probe_id")
    answer = result.get("answer")
    if not isinstance(answer, str) or not term_groups_present(
        answer,
        oracle["answer_term_groups"],
    ):
        errors.append("answer does not recover the complete launch gate")
    require_equal(
        errors,
        result.get("support_observation_count"),
        oracle["support_observation_count"],
        "support_observation_count",
    )
    claim_ids = result.get("claim_ids")
    if not isinstance(claim_ids, list) or len(claim_ids) != 1:
        errors.append("claim_ids must identify exactly one canonical launch-gate claim")
        claim_ids = []
    canonical_ids = result.get("canonical_evidence_ids")
    if not isinstance(canonical_ids, list) or len(canonical_ids) != 1:
        errors.append(
            "canonical_evidence_ids must identify exactly one support observation"
        )
        canonical_ids = []

    claims = index_rows(output, "claims.jsonl", "claim_id", errors)
    evidence = index_rows(output, "evidence.jsonl", "evidence_id", errors)
    for claim_id in claim_ids:
        if claim_id not in claims:
            errors.append(f"unknown result claim_id {claim_id}")
    for evidence_id in canonical_ids:
        row = evidence.get(evidence_id)
        if row is None:
            errors.append(f"unknown canonical evidence_id {evidence_id}")
            continue
        require_equal(
            errors,
            row.get("source_revision_id"),
            oracle["source_revision_id"],
            f"evidence {evidence_id} source revision",
        )
        locator = str(row.get("locator", ""))
        if not exact_line_set(locator, oracle["locator_line_numbers"]):
            errors.append(
                f"evidence {evidence_id} locator does not exactly match "
                f"lines {oracle['locator_line_numbers']}"
            )
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "audit": audit,
        "semantic_result": result,
        "output_tree_sha256": tree_digest(output),
    }


def score_composition(
    output: Path,
    case_id: str,
    oracle: dict[str, Any],
    auditor: Any,
) -> dict[str, Any]:
    errors: list[str] = []
    audit = audit_output(output, errors, auditor)
    result = load_semantic_result(output, errors)
    require_equal(errors, result.get("case_id"), case_id, "case_id")
    require_equal(errors, result.get("probe_id"), oracle["probe_id"], "probe_id")
    require_equal(
        errors,
        result.get("global_rollout_supported"),
        oracle["global_rollout_supported"],
        "global_rollout_supported",
    )
    require_set(
        errors,
        result.get("region_limited_source_ids"),
        oracle["region_limited_source_ids"],
        "region_limited_source_ids",
    )
    require_set(
        errors,
        result.get("blocking_source_ids"),
        oracle["blocking_source_ids"],
        "blocking_source_ids",
    )
    require_set(
        errors,
        result.get("excluded_as_derived_source_ids"),
        oracle["excluded_as_derived_source_ids"],
        "excluded_as_derived_source_ids",
    )
    answer = result.get("answer")
    if not isinstance(answer, str) or not term_groups_present(
        answer,
        (("global",), ("october",), ("no", "not", "insufficient", "cannot")),
    ):
        errors.append("answer does not clearly reject unsupported global readiness")
    confidence = result.get("confidence")
    if not isinstance(confidence, str) or not confidence.strip():
        errors.append("confidence must be a non-empty string")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "audit": audit,
        "semantic_result": result,
        "output_tree_sha256": tree_digest(output),
    }


def evidence_revisions(
    claim: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
) -> set[str]:
    return {
        str(evidence[evidence_id].get("source_revision_id"))
        for evidence_id in claim.get("evidence_ids", [])
        if evidence_id in evidence
    }


MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def normalize_date(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    stripped = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", stripped):
        return stripped
    match = re.fullmatch(
        r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})",
        stripped,
    )
    if match and match.group(1).casefold() in MONTHS:
        month = MONTHS[match.group(1).casefold()]
        return f"{int(match.group(3)):04d}-{month:02d}-{int(match.group(2)):02d}"
    return stripped


def score_incremental(
    output: Path,
    oracle: dict[str, Any],
    auditor: Any,
) -> dict[str, Any]:
    errors: list[str] = []
    audit = audit_output(output, errors, auditor)
    result = load_semantic_result(output, errors)
    require_equal(
        errors,
        result.get("case_id"),
        "G-incremental-correction",
        "case_id",
    )
    require_equal(errors, result.get("probe_id"), oracle["probe_id"], "probe_id")
    require_equal(
        errors,
        normalize_date(result.get("current_deadline")),
        oracle["current_deadline"],
        "current_deadline",
    )
    require_equal(
        errors,
        normalize_date(result.get("previous_deadline")),
        oracle["previous_deadline"],
        "previous_deadline",
    )

    claims = index_rows(output, "claims.jsonl", "claim_id", errors)
    evidence = index_rows(output, "evidence.jsonl", "evidence_id", errors)
    old_id = result.get("old_claim_id")
    new_id = result.get("new_claim_id")
    old_claim = claims.get(old_id) if isinstance(old_id, str) else None
    new_claim = claims.get(new_id) if isinstance(new_id, str) else None
    if old_claim is None:
        errors.append("old_claim_id does not resolve")
    if new_claim is None:
        errors.append("new_claim_id does not resolve")
    if old_claim and new_claim:
        require_equal(
            errors,
            old_claim.get("lifecycle_status"),
            "superseded",
            "old claim lifecycle",
        )
        require_equal(
            errors,
            new_claim.get("lifecycle_status"),
            "active",
            "new claim lifecycle",
        )
        if new_id not in old_claim.get("superseded_by_claim_ids", []):
            errors.append("old claim lacks reciprocal superseded_by link")
        if old_id not in new_claim.get("supersedes_claim_ids", []):
            errors.append("new claim lacks reciprocal supersedes link")
        require_equal(
            errors,
            evidence_revisions(old_claim, evidence),
            {oracle["old_revision_id"]},
            "old claim revision",
        )
        require_equal(
            errors,
            evidence_revisions(new_claim, evidence),
            {oracle["new_revision_id"]},
            "new claim revision",
        )
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "audit": audit,
        "semantic_result": result,
        "output_tree_sha256": tree_digest(output),
    }


def score_reconstruction(
    output: Path,
    oracle: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    result = load_semantic_result(output, errors)
    require_equal(
        errors,
        result.get("case_id"),
        "I-cold-reconstruction",
        "case_id",
    )
    require_equal(errors, result.get("probe_id"), oracle["probe_id"], "probe_id")
    blocker = result.get("release_blocker")
    if not isinstance(blocker, str) or not term_groups_present(
        blocker,
        oracle["blocker_term_groups"],
    ):
        errors.append("release_blocker does not recover the critical gate")
    caveat = result.get("scope_caveat")
    if not isinstance(caveat, str) or not term_groups_present(
        caveat,
        oracle["caveat_term_groups"],
    ):
        errors.append("scope_caveat does not recover the mobile exclusion")
    verification_status = result.get("verification_status")
    if (
        not isinstance(verification_status, str)
        or oracle["verification_status"] not in verification_status.casefold()
    ):
        errors.append(
            f"verification_status: expected {oracle['verification_status']!r} "
            f"within {verification_status!r}"
        )
    require_equal(
        errors,
        result.get("reload_paths"),
        oracle["reload_paths"],
        "reload_paths",
    )
    gaps = result.get("unresolved_gaps")
    gap_text = " ".join(gaps) if isinstance(gaps, list) else ""
    if not all(term in gap_text.casefold() for term in oracle["unresolved_gap_terms"]):
        errors.append("unresolved_gaps omits the unknown completion date")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "semantic_result": result,
        "output_tree_sha256": tree_digest(output),
    }


def score(run_dir: Path, receipt_path: Path) -> dict[str, Any]:
    metadata = load_json(run_dir / "run-metadata.json")
    observed_evaluator_hash = sha256_file(Path(__file__))
    observed_evaluator_surface = evaluator_surface()
    expected_evaluator_surface = metadata.get("evaluator_surface")
    evaluator_binding = {
        "expected_evaluator_sha256": metadata.get("evaluator_sha256"),
        "observed_evaluator_sha256": observed_evaluator_hash,
        "expected_evaluator_surface": expected_evaluator_surface,
        "observed_evaluator_surface": observed_evaluator_surface,
        "status": (
            "pass"
            if metadata.get("evaluator_sha256") == observed_evaluator_hash
            and expected_evaluator_surface == observed_evaluator_surface
            else "fail"
        ),
    }
    observed_oracle_hash = sha256_file(ORACLE)
    oracle_binding = {
        "expected_oracle_sha256": metadata.get("oracle_sha256"),
        "observed_oracle_sha256": observed_oracle_hash,
        "status": (
            "pass"
            if metadata.get("oracle_sha256") == observed_oracle_hash
            else "fail"
        ),
    }
    skill_root = Path(str(metadata.get("skill_root", "")))
    if not skill_root.is_dir():
        raise ValueError("run metadata skill_root is not an existing directory")
    expected_skill_hash = metadata.get("skill_tree_sha256")
    observed_skill_hash = runtime_digest(skill_root)
    runtime_binding = {
        "expected_skill_tree_sha256": expected_skill_hash,
        "observed_skill_tree_sha256": observed_skill_hash,
        "status": (
            "pass"
            if observed_skill_hash == expected_skill_hash
            else "fail"
        ),
    }
    observed_case_hashes = {
        case_id: tree_digest(
            run_dir / "cases" / case_id,
            excluded_parts={"output"},
        )
        for case_id in CASE_NAMES
    }
    expected_case_hashes = metadata.get("case_input_hashes")
    if not isinstance(expected_case_hashes, dict):
        expected_case_hashes = {}
    case_input_binding = {
        "status": (
            "pass"
            if observed_case_hashes == expected_case_hashes
            else "fail"
        ),
        "expected_case_input_sha256": expected_case_hashes,
        "observed_case_input_sha256": observed_case_hashes,
    }
    if (
        evaluator_binding["status"] != "pass"
        or oracle_binding["status"] != "pass"
        or runtime_binding["status"] != "pass"
        or case_input_binding["status"] != "pass"
    ):
        receipt = {
            "schema_version": 1,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "status": "fail",
            "proof_boundary": (
                "Scoring stopped before oracle evaluation because the evaluator, "
                "oracle, staged runtime, or case inputs changed after preparation."
            ),
            "run_metadata": metadata,
            "evaluator_binding": evaluator_binding,
            "oracle_binding": oracle_binding,
            "runtime_binding": runtime_binding,
            "case_input_binding": case_input_binding,
            "cases": {},
            "source_order_invariance": {
                "status": "not-evaluated",
                "different_fields": [],
            },
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(receipt_path, receipt)
        return receipt

    oracle = load_json(ORACLE)
    auditor = load_auditor(skill_root / "scripts" / "audit_bundle.py")
    cases_dir = run_dir / "cases"
    case_receipts: dict[str, dict[str, Any]] = {}
    case_receipts["C-boundary-overlap"] = score_boundary(
        cases_dir / "C-boundary-overlap" / "output",
        oracle["C-boundary-overlap"],
        auditor,
    )
    for case_id in (
        "D-source-composition-order-a",
        "D-source-composition-order-b",
    ):
        case_receipts[case_id] = score_composition(
            cases_dir / case_id / "output",
            case_id,
            oracle["D-source-composition"],
            auditor,
        )
    case_receipts["G-incremental-correction"] = score_incremental(
        cases_dir / "G-incremental-correction" / "output",
        oracle["G-incremental-correction"],
        auditor,
    )
    case_receipts["I-cold-reconstruction"] = score_reconstruction(
        cases_dir / "I-cold-reconstruction" / "output",
        oracle["I-cold-reconstruction"],
    )

    order_a = case_receipts["D-source-composition-order-a"]["semantic_result"]
    order_b = case_receipts["D-source-composition-order-b"]["semantic_result"]
    order_fields = (
        "global_rollout_supported",
        "region_limited_source_ids",
        "blocking_source_ids",
        "excluded_as_derived_source_ids",
        "confidence",
    )
    order_differences = [
        field_name
        for field_name in order_fields
        if (
            sorted(order_a.get(field_name, []))
            if isinstance(order_a.get(field_name), list)
            else order_a.get(field_name)
        )
        != (
            sorted(order_b.get(field_name, []))
            if isinstance(order_b.get(field_name), list)
            else order_b.get(field_name)
        )
    ]
    order_receipt = {
        "status": "pass" if not order_differences else "fail",
        "different_fields": order_differences,
    }
    overall_pass = all(
        case["status"] == "pass" for case in case_receipts.values()
    ) and order_receipt["status"] == "pass" and runtime_binding["status"] == "pass"
    receipt = {
        "schema_version": 1,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "status": "pass" if overall_pass else "fail",
        "proof_boundary": (
            "Fresh-agent semantic evidence for cases C, D, G, and I only; "
            "artifact-level runtime quarantine without host filesystem attestation; "
            "not a general factuality guarantee."
        ),
        "run_metadata": metadata,
        "evaluator_binding": evaluator_binding,
        "oracle_binding": oracle_binding,
        "runtime_binding": runtime_binding,
        "case_input_binding": case_input_binding,
        "cases": case_receipts,
        "source_order_invariance": order_receipt,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage or score sealed semantic distillation evaluations."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument(
        "--skill-root",
        type=Path,
        default=ROOT,
        help="Exact skill tree fresh agents will use.",
    )
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--run-dir", type=Path, required=True)
    score_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "prepare":
            result = prepare(args.run_dir, args.skill_root)
        else:
            result = score(args.run_dir, args.receipt)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status", "pass") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
