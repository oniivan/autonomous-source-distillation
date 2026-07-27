#!/usr/bin/env python3
"""Replay retained behavioral outputs against an exact skill runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from evaluation_contract import file_surface  # noqa: E402
from runtime_contract import runtime_digest  # noqa: E402

DEFAULT_SEMANTIC_RELEASE = "2026-07-27"
DEFAULT_ROUTING_RELEASES = (
    "2026-07-27-15m",
    "2026-07-27-60m",
)
SEMANTIC_EVALUATOR_SURFACE_PATHS = (
    "scripts/evaluation_contract.py",
    "scripts/locator_utils.py",
    "scripts/runtime_contract.py",
    "scripts/semantic_eval.py",
)
ROUTING_EVALUATOR_SURFACE_PATHS = (
    "scripts/evaluation_contract.py",
    "scripts/locator_utils.py",
    "scripts/route_comparison.py",
    "scripts/runtime_contract.py",
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


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


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluation_binding(
    receipt: dict[str, Any],
    *,
    skill_root: Path,
    evaluator_path: Path,
    evaluator_surface_paths: tuple[str, ...],
    oracle_path: Path,
) -> dict[str, Any]:
    evaluator = receipt.get("evaluator_binding")
    oracle = receipt.get("oracle_binding")
    if not isinstance(evaluator, dict):
        evaluator = {}
    if not isinstance(oracle, dict):
        oracle = {}
    current_evaluator_hash = sha256_file(evaluator_path)
    current_evaluator_surface = file_surface(
        skill_root,
        evaluator_surface_paths,
    )
    current_oracle_hash = sha256_file(oracle_path)
    status = (
        "pass"
        if evaluator.get("status") == "pass"
        and evaluator.get("expected_evaluator_sha256")
        == evaluator.get("observed_evaluator_sha256")
        == current_evaluator_hash
        and evaluator.get("expected_evaluator_surface")
        == evaluator.get("observed_evaluator_surface")
        == current_evaluator_surface
        and oracle.get("status") == "pass"
        and oracle.get("expected_oracle_sha256")
        == oracle.get("observed_oracle_sha256")
        == current_oracle_hash
        else "fail"
    )
    return {
        "status": status,
        "evaluator_sha256": current_evaluator_hash,
        "evaluator_surface": current_evaluator_surface,
        "oracle_sha256": current_oracle_hash,
    }


def safe_component(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or len(Path(value).parts) != 1
    ):
        raise ValueError(f"{label} must be one safe path component")
    return value


def replay_output(
    *,
    skill_root: Path,
    bundle: Path,
    expected_hash: Any,
    auditor: Any,
    audit_required: bool,
) -> dict[str, Any]:
    exists = bundle.is_dir()
    observed_hash = tree_digest(bundle) if exists else None
    hash_status = (
        "pass"
        if exists
        and isinstance(expected_hash, str)
        and observed_hash == expected_hash
        else "fail"
    )
    audit = auditor.audit_bundle(bundle) if audit_required else None
    audit_status = (
        "pass"
        if not audit_required
        or (
            isinstance(audit, dict)
            and audit.get("structure_status") == "pass"
            and audit.get("readiness_status") == "pass"
        )
        else "fail"
    )
    return {
        "bundle": bundle.relative_to(skill_root).as_posix(),
        "expected_output_tree_sha256": expected_hash,
        "observed_output_tree_sha256": observed_hash,
        "output_hash_status": hash_status,
        "audit_required": audit_required,
        "audit": audit,
        "status": (
            "pass"
            if hash_status == "pass" and audit_status == "pass"
            else "fail"
        ),
    }


def same_value(
    errors: list[str],
    label: str,
    *values: Any,
) -> None:
    if not values or any(value != values[0] for value in values[1:]):
        errors.append(f"{label} does not match across retained evidence")


def completed_ids(path: Path, id_field: str) -> set[str]:
    receipt = load_json(path)
    rows = receipt.get("runs")
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get(id_field))
        for row in rows
        if isinstance(row, dict)
        and row.get("status") == "completed"
        and isinstance(row.get(id_field), str)
    }


def semantic_provenance_check(
    release_root: Path,
    receipt: dict[str, Any],
    observed_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    provenance = load_json(release_root / "generation-provenance.json")
    generation_metadata = load_json(
        release_root / "generation-run-metadata.json"
    )
    output_manifest = load_json(
        release_root / "generation-output-manifest.json"
    )
    receipt_cases = receipt.get("cases")
    if not isinstance(receipt_cases, dict):
        receipt_cases = {}
    case_ids = set(receipt_cases)
    expected_outputs = {
        case_id: case.get("output_tree_sha256")
        for case_id, case in receipt_cases.items()
        if isinstance(case, dict)
    }
    observed_hashes = {
        case_id: observed_outputs[f"semantic/{case_id}"].get(
            "observed_output_tree_sha256"
        )
        for case_id in case_ids
        if f"semantic/{case_id}" in observed_outputs
    }
    if provenance.get("schema_version") != 1:
        errors.append("semantic provenance schema_version must be 1")
    if provenance.get("status") != "pass":
        errors.append("semantic provenance status must be pass")
    if (
        provenance.get("mode")
        != "byte-identical-output-migration-into-prebound-scoring-envelope"
    ):
        errors.append("semantic provenance mode is invalid")
    if provenance.get("agents_reran_in_scoring_run") is not False:
        errors.append("semantic provenance must state that agents did not rerun")
    same_value(
        errors,
        "semantic runtime hash",
        provenance.get("generation_runtime_sha256"),
        provenance.get("scoring_runtime_sha256"),
        generation_metadata.get("skill_tree_sha256"),
        receipt.get("runtime_binding", {}).get(
            "expected_skill_tree_sha256"
        ),
        receipt.get("runtime_binding", {}).get(
            "observed_skill_tree_sha256"
        ),
    )
    same_value(
        errors,
        "semantic case-input hashes",
        provenance.get("case_input_sha256"),
        generation_metadata.get("case_input_hashes"),
        receipt.get("case_input_binding", {}).get(
            "expected_case_input_sha256"
        ),
        receipt.get("case_input_binding", {}).get(
            "observed_case_input_sha256"
        ),
        receipt.get("run_metadata", {}).get("case_input_hashes"),
    )
    same_value(
        errors,
        "semantic output hashes",
        provenance.get("output_tree_sha256"),
        output_manifest.get("output_tree_sha256"),
        expected_outputs,
        observed_hashes,
    )
    if output_manifest.get("schema_version") != 1:
        errors.append("semantic generation output manifest schema_version must be 1")
    if output_manifest.get("status") != "pass":
        errors.append("semantic generation output manifest status must be pass")
    same_value(
        errors,
        "semantic output-manifest runtime",
        output_manifest.get("runtime_sha256"),
        generation_metadata.get("skill_tree_sha256"),
    )
    same_value(
        errors,
        "semantic output-manifest inputs",
        output_manifest.get("case_input_sha256"),
        generation_metadata.get("case_input_hashes"),
    )
    case_input_hashes = provenance.get("case_input_sha256")
    if not isinstance(case_input_hashes, dict) or set(case_input_hashes) != case_ids:
        errors.append("semantic provenance case set is incomplete")
    if completed_ids(release_root / "agent-runs.json", "case_id") != case_ids:
        errors.append("semantic completed-agent case set is incomplete")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def routing_provenance_check(
    release_root: Path,
    receipt: dict[str, Any],
    observed_outputs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    precorrection = load_json(
        release_root / "precorrection-locator-receipt.json"
    )
    metadata = receipt.get("run_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    provenance = metadata.get("generation_provenance")
    if not isinstance(provenance, dict):
        provenance = {}
    routes = receipt.get("routes")
    old_routes = precorrection.get("routes")
    if not isinstance(routes, dict):
        routes = {}
    if not isinstance(old_routes, dict):
        old_routes = {}
    route_ids = set(routes)
    fixture = receipt.get("fixture")
    if not isinstance(fixture, dict):
        fixture = {}
    duration = fixture.get("duration_proxy_minutes")
    prefix = f"routing/{duration}m"
    corrected_outputs = {
        route: value.get("output_tree_sha256")
        for route, value in routes.items()
        if isinstance(value, dict)
    }
    old_outputs = {
        route: value.get("output_tree_sha256")
        for route, value in old_routes.items()
        if isinstance(value, dict)
    }
    observed_hashes = {
        route: observed_outputs[f"{prefix}/{route}"].get(
            "observed_output_tree_sha256"
        )
        for route in route_ids
        if f"{prefix}/{route}" in observed_outputs
    }
    if (
        provenance.get("mode")
        != "byte-identical-output-and-dispatch-migration-after-evaluator-correction"
    ):
        errors.append("routing provenance mode is invalid")
    if precorrection.get("status") != "fail":
        errors.append("precorrection routing receipt must retain its failed status")
    for label, value in (
        ("precorrection evaluator", precorrection.get("evaluator_binding")),
        ("precorrection oracle", precorrection.get("oracle_binding")),
        ("precorrection runtime", precorrection.get("runtime_binding")),
        ("precorrection case inputs", precorrection.get("case_input_binding")),
        ("precorrection dispatch", precorrection.get("dispatch_binding")),
    ):
        if not isinstance(value, dict) or value.get("status") != "pass":
            errors.append(f"{label} binding must pass")
    same_value(
        errors,
        "routing source evaluator hash",
        provenance.get("source_evaluator_sha256"),
        precorrection.get("evaluator_binding", {}).get(
            "expected_evaluator_sha256"
        ),
        precorrection.get("evaluator_binding", {}).get(
            "observed_evaluator_sha256"
        ),
    )
    same_value(
        errors,
        "routing runtime hash",
        provenance.get("source_runtime_sha256"),
        precorrection.get("runtime_binding", {}).get(
            "expected_skill_tree_sha256"
        ),
        precorrection.get("runtime_binding", {}).get(
            "observed_skill_tree_sha256"
        ),
        receipt.get("runtime_binding", {}).get(
            "expected_skill_tree_sha256"
        ),
        receipt.get("runtime_binding", {}).get(
            "observed_skill_tree_sha256"
        ),
    )
    same_value(
        errors,
        "routing case-input hashes",
        provenance.get("source_case_input_hashes"),
        precorrection.get("case_input_binding", {}).get(
            "expected_case_input_sha256"
        ),
        precorrection.get("case_input_binding", {}).get(
            "observed_case_input_sha256"
        ),
        receipt.get("case_input_binding", {}).get(
            "expected_case_input_sha256"
        ),
        receipt.get("case_input_binding", {}).get(
            "observed_case_input_sha256"
        ),
    )
    same_value(
        errors,
        "routing dispatch hashes",
        provenance.get("preserved_dispatch_start_sha256"),
        precorrection.get("dispatch_binding", {}).get(
            "expected_dispatch_start_sha256"
        ),
        precorrection.get("dispatch_binding", {}).get(
            "observed_dispatch_start_sha256"
        ),
        receipt.get("dispatch_binding", {}).get(
            "expected_dispatch_start_sha256"
        ),
        receipt.get("dispatch_binding", {}).get(
            "observed_dispatch_start_sha256"
        ),
    )
    same_value(
        errors,
        "routing output hashes",
        old_outputs,
        corrected_outputs,
        observed_hashes,
    )
    if set(old_routes) != route_ids:
        errors.append("precorrection and corrected route sets differ")
    if completed_ids(release_root / "agent-runs.json", "route") != route_ids:
        errors.append("routing completed-agent route set is incomplete")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
    }


def replay(
    skill_root: Path,
    *,
    semantic_release_name: str = DEFAULT_SEMANTIC_RELEASE,
    routing_release_names: tuple[str, ...] = DEFAULT_ROUTING_RELEASES,
    release: str | None = None,
    skill_root_label: str = "<skill-root>",
) -> dict[str, Any]:
    skill_root = skill_root.resolve()
    if release is not None:
        semantic_release_name = release
        routing_release_names = (release,)
    if not routing_release_names:
        raise ValueError("at least one routing release is required")
    auditor = load_module(
        "release_replay_auditor",
        skill_root / "scripts" / "audit_bundle.py",
    )

    semantic_release = (
        skill_root
        / "evals"
        / "semantic"
        / "releases"
        / semantic_release_name
    )
    semantic_receipt_path = semantic_release / "semantic-evaluation-receipt.json"
    semantic_receipt = load_json(semantic_receipt_path)
    routing_releases = {
        release_name: (
            skill_root / "evals" / "routing" / "releases" / release_name
        )
        for release_name in routing_release_names
    }
    routing_receipts = {
        release_name: load_json(release_root / "route-comparison-receipt.json")
        for release_name, release_root in routing_releases.items()
    }

    results: dict[str, Any] = {}
    semantic_cases = semantic_receipt.get("cases")
    if not isinstance(semantic_cases, dict) or not semantic_cases:
        raise ValueError("semantic receipt must name at least one case")
    for raw_case_id, case_receipt in semantic_cases.items():
        case_id = safe_component(raw_case_id, "semantic case id")
        if not isinstance(case_receipt, dict):
            raise ValueError(f"semantic case {case_id} receipt must be an object")
        result_id = f"semantic/{case_id}"
        results[result_id] = replay_output(
            skill_root=skill_root,
            bundle=semantic_release / "cases" / case_id / "output",
            expected_hash=case_receipt.get("output_tree_sha256"),
            auditor=auditor,
            audit_required=isinstance(case_receipt.get("audit"), dict),
        )

    for release_name, release_root in routing_releases.items():
        routing_receipt = routing_receipts[release_name]
        fixture = routing_receipt.get("fixture")
        if not isinstance(fixture, dict):
            raise ValueError(f"routing release {release_name} has no fixture")
        duration = fixture.get("duration_proxy_minutes")
        route_receipts = routing_receipt.get("routes")
        if not isinstance(route_receipts, dict) or not route_receipts:
            raise ValueError(f"routing release {release_name} has no routes")
        for raw_route, route_receipt in route_receipts.items():
            route = safe_component(raw_route, "route id")
            if not isinstance(route_receipt, dict):
                raise ValueError(f"route {route} receipt must be an object")
            result_id = f"routing/{duration}m/{route}"
            if result_id in results:
                raise ValueError(f"duplicate replay case {result_id}")
            results[result_id] = replay_output(
                skill_root=skill_root,
                bundle=release_root / "cases" / route / "output",
                expected_hash=route_receipt.get("output_tree_sha256"),
                auditor=auditor,
                audit_required=isinstance(route_receipt.get("audit"), dict),
            )

    starter_bundle = skill_root / "assets" / "starter-bundle"
    results["starter-bundle"] = replay_output(
        skill_root=skill_root,
        bundle=starter_bundle,
        expected_hash=tree_digest(starter_bundle),
        auditor=auditor,
        audit_required=True,
    )

    source_receipts_status = (
        "pass"
        if semantic_receipt.get("status") == "pass"
        and all(
            isinstance(case, dict) and case.get("status") == "pass"
            for case in semantic_cases.values()
        )
        and all(
            receipt.get("status") == "pass"
            for receipt in routing_receipts.values()
        )
        and all(
            isinstance(route, dict) and route.get("status") == "pass"
            for receipt in routing_receipts.values()
            for route in (
                receipt.get("routes", {}).values()
                if isinstance(receipt.get("routes"), dict)
                else ()
            )
        )
        else "fail"
    )
    compatibility_status = (
        "pass"
        if source_receipts_status == "pass"
        and all(result["status"] == "pass" for result in results.values())
        else "fail"
    )
    current_runtime_hash = runtime_digest(skill_root)
    fresh_runtime_bindings = {
        "semantic": semantic_receipt["runtime_binding"][
            "observed_skill_tree_sha256"
        ],
        **{
            f"routing/{receipt['fixture']['duration_proxy_minutes']}m": receipt[
                "runtime_binding"
            ]["observed_skill_tree_sha256"]
            for receipt in routing_receipts.values()
        },
    }
    generation_runtime_hashes = set(fresh_runtime_bindings.values())
    behavioral_binding_status = (
        "pass"
        if generation_runtime_hashes == {current_runtime_hash}
        else "fail"
    )
    evaluation_bindings = {
        "semantic": evaluation_binding(
            semantic_receipt,
            skill_root=skill_root,
            evaluator_path=skill_root / "scripts" / "semantic_eval.py",
            evaluator_surface_paths=SEMANTIC_EVALUATOR_SURFACE_PATHS,
            oracle_path=(
                skill_root
                / "evals"
                / "semantic"
                / "oracles"
                / "expected.json"
            ),
        )
    }
    for release_name, receipt in routing_receipts.items():
        duration = receipt["fixture"]["duration_proxy_minutes"]
        oracle_name = "oracle.json" if duration == 15 else "oracle-60m.json"
        evaluation_bindings[f"routing/{duration}m"] = evaluation_binding(
            receipt,
            skill_root=skill_root,
            evaluator_path=skill_root / "scripts" / "route_comparison.py",
            evaluator_surface_paths=ROUTING_EVALUATOR_SURFACE_PATHS,
            oracle_path=skill_root / "evals" / "routing" / oracle_name,
        )
    evaluation_binding_status = (
        "pass"
        if all(
            binding["status"] == "pass"
            for binding in evaluation_bindings.values()
        )
        else "fail"
    )
    provenance_checks = {
        "semantic": semantic_provenance_check(
            semantic_release,
            semantic_receipt,
            results,
        )
    }
    for release_name, release_root in routing_releases.items():
        receipt = routing_receipts[release_name]
        duration = receipt["fixture"]["duration_proxy_minutes"]
        provenance_checks[f"routing/{duration}m"] = routing_provenance_check(
            release_root,
            receipt,
            results,
        )
    provenance_status = (
        "pass"
        if all(
            check["status"] == "pass"
            for check in provenance_checks.values()
        )
        else "fail"
    )
    status = (
        "pass"
        if compatibility_status == "pass"
        and behavioral_binding_status == "pass"
        and evaluation_binding_status == "pass"
        and provenance_status == "pass"
        else "fail"
    )
    return {
        "schema_version": 1,
        "replayed_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "mode": "deterministic-final-runtime-replay",
        "proof_boundary": (
            "Revalidates unchanged retained bundle bytes against this runtime; "
            "it does not rerun agent behavior or expand the semantic proof."
        ),
        "compatibility_status": compatibility_status,
        "behavioral_binding_status": behavioral_binding_status,
        "evaluation_binding_status": evaluation_binding_status,
        "provenance_status": provenance_status,
        "behavioral_case_count": len(results) - 1,
        "total_replayed_case_count": len(results),
        "runtime_binding": {
            "skill_root": skill_root_label,
            "skill_tree_sha256": current_runtime_hash,
            "auditor_sha256": sha256_file(
                skill_root / "scripts" / "audit_bundle.py"
            ),
        },
        "fresh_generation_runtime_bindings": fresh_runtime_bindings,
        "evaluation_bindings": evaluation_bindings,
        "provenance_checks": provenance_checks,
        "releases": {
            "semantic": semantic_release_name,
            "routing": list(routing_release_names),
        },
        "source_receipts_status": source_receipts_status,
        "cases": results,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replay retained behavioral outputs against an exact skill runtime."
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=ROOT,
        help="Skill package/runtime root. Defaults to this script's package.",
    )
    parser.add_argument(
        "--semantic-release",
        default=DEFAULT_SEMANTIC_RELEASE,
        help=(
            "Semantic release evidence directory name. Defaults to "
            f"{DEFAULT_SEMANTIC_RELEASE}."
        ),
    )
    parser.add_argument(
        "--routing-release",
        action="append",
        help=(
            "Routing release evidence directory name. Repeat for multiple profiles. "
            "Defaults to the current 15m and 60m releases."
        ),
    )
    parser.add_argument(
        "--release",
        help=(
            "Compatibility alias: use one release name for semantic and routing "
            "evidence."
        ),
    )
    parser.add_argument(
        "--skill-root-label",
        default="<skill-root>",
        help="Portable label to record instead of a machine-local path.",
    )
    parser.add_argument(
        "--receipt",
        type=Path,
        help="Optional JSON receipt path. The receipt is always printed.",
    )
    args = parser.parse_args()

    try:
        receipt = replay(
            args.skill_root,
            semantic_release_name=args.semantic_release,
            routing_release_names=tuple(
                args.routing_release or DEFAULT_ROUTING_RELEASES
            ),
            release=args.release,
            skill_root_label=args.skill_root_label,
        )
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        print(f"release replay failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    if args.receipt:
        try:
            write_json(args.receipt, receipt)
        except OSError as exc:
            print(f"cannot write receipt: {exc}", file=sys.stderr)
            return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
