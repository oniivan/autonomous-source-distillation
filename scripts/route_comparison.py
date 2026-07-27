#!/usr/bin/env python3
"""Prepare and score direct/light/serious proportionality comparisons."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from evaluation_contract import file_surface  # noqa: E402
from locator_utils import exact_line_set, parse_line_ranges  # noqa: E402
from runtime_contract import (  # noqa: E402
    runtime_digest,
    stage_runtime,
    validate_runtime_root,
)

EVAL_ROOT = ROOT / "evals" / "routing"
ORACLE = EVAL_ROOT / "oracle.json"
ORACLE_60M = EVAL_ROOT / "oracle-60m.json"
TEMPLATE = EVAL_ROOT / "task-template.md"
AUDITOR_PATH = ROOT / "scripts" / "audit_bundle.py"
ROUTES = ("direct", "light", "serious")
EVALUATOR_SURFACE_PATHS = (
    "scripts/evaluation_contract.py",
    "scripts/locator_utils.py",
    "scripts/route_comparison.py",
    "scripts/runtime_contract.py",
)
SOURCE_PATH_LINE_RE = re.compile(
    r"(?<![\w./-])inputs/source\.txt:(\d+)(?!\d)",
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluator_surface() -> dict[str, Any]:
    return file_surface(ROOT, EVALUATOR_SURFACE_PATHS)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return value


def tree_digest(
    root: Path,
    *,
    excluded_parts: set[str] | None = None,
) -> str:
    excluded_parts = excluded_parts or set()
    digest = hashlib.sha256()
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        relative_path = path.relative_to(root)
        if (
            ".git" in relative_path.parts
            or "__pycache__" in relative_path.parts
            or any(part in excluded_parts for part in relative_path.parts)
        ):
            continue
        relative = relative_path.as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def oracle_path(duration_minutes: int) -> Path:
    if duration_minutes == 15:
        return ORACLE
    if duration_minutes == 60:
        return ORACLE_60M
    raise ValueError("duration_minutes must be 15 or 60")


def source_lines(duration_minutes: int = 15) -> list[str]:
    oracle_path(duration_minutes)
    fact_lines = (
        {
            "budget_cap": 12,
            "launch_date": 58,
            "release_blocker": 113,
            "minority_dissent": 171,
            "scope_limitation": 219,
        }
        if duration_minutes == 15
        else {
            "budget_cap": 47,
            "launch_date": 232,
            "release_blocker": 451,
            "minority_dissent": 683,
            "scope_limitation": 877,
        }
    )
    facts = {
        fact_lines["budget_cap"]: (
            "The approved Project Atlas budget cap is $240,000."
        ),
        fact_lines["launch_date"]: (
            "The target launch date is November 18, 2026."
        ),
        fact_lines["release_blocker"]: (
            "Release remains blocked until the data-retention review closes."
        ),
        fact_lines["minority_dissent"]: (
            "The reliability lead opposes launch unless the rollback test completes "
            "in under 8 minutes."
        ),
        fact_lines["scope_limitation"]: (
            "The pilot sample excluded mobile users, limiting generalization."
        ),
    }
    lines: list[str] = []
    line_total = duration_minutes * 15
    for index in range(1, line_total + 1):
        minutes, seconds = divmod(index * 4, 60)
        content = facts.get(
            index,
            (
                f"Status item {index} recorded no new decision or risk."
            ),
        )
        lines.append(f"{minutes:02d}:{seconds:02d} {content}")
    return lines


def prepare(
    run_dir: Path,
    skill_root: Path,
    duration_minutes: int = 15,
) -> dict[str, Any]:
    selected_oracle = oracle_path(duration_minutes)
    skill_root = skill_root.resolve()
    validate_runtime_root(skill_root)
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError("run directory must be absent or empty")
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = run_dir / "runtime"
    runtime_manifest = stage_runtime(skill_root, runtime_root)
    template = TEMPLATE.read_text(encoding="utf-8")
    source = "\n".join(source_lines(duration_minutes)) + "\n"
    cases = []
    for route in ROUTES:
        case = run_dir / "cases" / route
        inputs = case / "inputs"
        inputs.mkdir(parents=True)
        (inputs / "source.txt").write_text(source, encoding="utf-8")
        task = (
            template.replace("ROUTE_NAME", route.title())
            .replace("ROUTE_ID", route)
        )
        (case / "task.md").write_text(task, encoding="utf-8")
        cases.append(
            {
                "route": route,
                "case_dir": str(case),
                "task": str(case / "task.md"),
                "output_dir": str(case / "output"),
            }
        )
    case_input_hashes = {
        route: tree_digest(
            run_dir / "cases" / route,
            excluded_parts={"output", "dispatch-start.json"},
        )
        for route in ROUTES
    }
    current_evaluator_surface = evaluator_surface()
    metadata = {
        "schema_version": 1,
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "duration_proxy_minutes": duration_minutes,
        "skill_root": str(runtime_root),
        "skill_tree_sha256": runtime_manifest["skill_tree_sha256"],
        "evaluator_sha256": sha256_file(Path(__file__)),
        "evaluator_surface": current_evaluator_surface,
        "oracle_sha256": sha256_file(selected_oracle),
        "runtime_isolation": runtime_manifest,
        "case_input_hashes": case_input_hashes,
        "oracle_copied_to_run": False,
        "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
        "source_bytes": len(source.encode("utf-8")),
        "source_words": len(source.split()),
        "cases": cases,
    }
    write_json(run_dir / "run-metadata.json", metadata)
    return metadata


def mark_start(run_dir: Path, case_id: str) -> dict[str, Any]:
    if case_id not in ROUTES:
        raise ValueError(f"unknown case: {case_id}")
    case_dir = run_dir / "cases" / case_id
    marker = case_dir / "dispatch-start.json"
    if marker.exists():
        raise ValueError(f"dispatch marker already exists for {case_id}")
    output = case_dir / "output"
    if output.exists() and any(output.rglob("*")):
        raise ValueError(f"cannot mark {case_id} after output artifacts exist")
    value = {
        "case_id": case_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "started_epoch": time.time(),
    }
    write_json(marker, value)
    metadata_path = run_dir / "run-metadata.json"
    metadata = load_json(metadata_path)
    dispatch_hashes = metadata.get("dispatch_start_sha256")
    if not isinstance(dispatch_hashes, dict):
        dispatch_hashes = {}
    dispatch_hashes[case_id] = hashlib.sha256(marker.read_bytes()).hexdigest()
    metadata["dispatch_start_sha256"] = dispatch_hashes
    write_json(metadata_path, metadata)
    return value


def load_auditor(audit_script: Path = AUDITOR_PATH):
    spec = importlib.util.spec_from_file_location("route_comparison_auditor", audit_script)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bundle auditor")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def term_groups_present(text: str, groups: list[list[str]]) -> bool:
    normalized = text.casefold()
    compact = normalized.replace(",", "").replace("$", "")
    return all(
        any(
            term.casefold() in normalized
            or term.casefold().replace(",", "").replace("$", "") in compact
            for term in group
        )
        for group in groups
    )


def exact_route_line(locator: str, expected_line: int) -> bool:
    if exact_line_set(locator, [expected_line]):
        return True
    if parse_line_ranges(locator):
        return False
    path_lines = {
        int(match.group(1))
        for match in SOURCE_PATH_LINE_RE.finditer(locator)
    }
    return path_lines == {expected_line}


def output_measurements(output: Path, started_epoch: float) -> dict[str, Any]:
    files = [
        path
        for path in output.rglob("*")
        if path.is_file() and "inputs" not in path.relative_to(output).parts
    ]
    artifact_bytes = sum(path.stat().st_size for path in files)
    completed_epoch = max(
        (path.stat().st_mtime for path in files),
        default=started_epoch,
    )
    oldest_epoch = min(
        (path.stat().st_mtime for path in files),
        default=started_epoch,
    )
    return {
        "artifact_bytes": artifact_bytes,
        "output_token_proxy": math.ceil(artifact_bytes / 4),
        "artifact_file_count": len(files),
        "elapsed_seconds": round(completed_epoch - started_epoch, 3),
        "output_predates_start": bool(files) and oldest_epoch < started_epoch,
    }


def score_route(
    run_dir: Path,
    route: str,
    oracle: dict[str, Any],
    auditor: Any,
) -> dict[str, Any]:
    case = run_dir / "cases" / route
    output = case / "output"
    errors: list[str] = []
    try:
        result = load_json(output / "result.json")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result = {}
        errors.append(f"result.json cannot load: {exc}")
    answers = result.get("answers")
    if not isinstance(answers, dict):
        answers = {}
        errors.append("answers must be an object")

    fact_results: dict[str, dict[str, Any]] = {}
    for fact_id, expectation in oracle["facts"].items():
        answer = answers.get(fact_id)
        if not isinstance(answer, dict):
            answer = {}
        text = answer.get("answer")
        locator = answer.get("locator")
        recovered = isinstance(text, str) and term_groups_present(
            text,
            expectation["term_groups"],
        )
        locator_pass = isinstance(locator, str) and exact_route_line(
            locator,
            expectation["line"],
        )
        fact_results[fact_id] = {
            "recovered": recovered,
            "locator_pass": locator_pass,
        }
        if not recovered:
            errors.append(f"{fact_id}: fact not recovered")
        if not locator_pass:
            errors.append(f"{fact_id}: line locator is not exact")

    unsupported = result.get("unsupported_material_claims")
    if unsupported != []:
        errors.append("unsupported_material_claims must be an empty list")
    if result.get("source_status") != "source-only":
        errors.append("source_status must remain source-only")

    recovery = result.get("recovery")
    if not isinstance(recovery, dict):
        recovery = {}
    recovery_features = {
        "source_ref": recovery.get("source_ref") == "inputs/source.txt",
        "notes": (output / "notes.md").is_file(),
        "coverage": (output / "coverage.json").is_file(),
        "handoff": (output / "handoff.md").is_file(),
        "machine_manifest": (output / "run-manifest.json").is_file(),
    }
    reload_paths = recovery.get("reload_paths")
    normalized_reload_paths = (
        [
            path.removeprefix("output/")
            for path in reload_paths
            if isinstance(path, str)
        ]
        if isinstance(reload_paths, list)
        else []
    )
    recovery_features["reload_paths_present"] = bool(normalized_reload_paths)
    recovery_features["reload_paths_resolve"] = (
        bool(normalized_reload_paths)
        and all(
            (output / path).exists()
            for path in normalized_reload_paths
        )
    )

    audit = None
    if route == "direct":
        extra = [
            path
            for path in output.iterdir()
            if path.name != "result.json"
        ] if output.is_dir() else []
        if extra:
            errors.append("direct route created artifacts beyond result.json")
    elif route == "light":
        if not recovery_features["notes"] or not recovery_features["coverage"]:
            errors.append("light route requires notes.md and coverage.json")
    else:
        audit = auditor.audit_bundle(output)
        if audit.get("structure_status") != "pass":
            errors.append("serious bundle structure_status is not pass")
        if audit.get("readiness_status") != "pass":
            errors.append("serious bundle readiness_status is not pass")

    start = load_json(case / "dispatch-start.json")
    measurements = output_measurements(output, float(start["started_epoch"]))
    if measurements["output_predates_start"]:
        errors.append("one or more output artifacts predate the dispatch marker")
    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "fact_results": fact_results,
        "critical_fact_recall": sum(
            item["recovered"] for item in fact_results.values()
        ) / len(fact_results),
        "locator_accuracy": sum(
            item["locator_pass"] for item in fact_results.values()
        ) / len(fact_results),
        "recovery_features": recovery_features,
        "measurements": measurements,
        "audit": audit,
        "output_tree_sha256": tree_digest(output),
    }


def score(run_dir: Path, receipt_path: Path) -> dict[str, Any]:
    metadata = load_json(run_dir / "run-metadata.json")
    duration_minutes = metadata.get("duration_proxy_minutes")
    if not isinstance(duration_minutes, int) or isinstance(duration_minutes, bool):
        raise ValueError("run metadata duration_proxy_minutes must be an integer")
    selected_oracle = oracle_path(duration_minutes)
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
    observed_oracle_hash = sha256_file(selected_oracle)
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
        route: tree_digest(
            run_dir / "cases" / route,
            excluded_parts={"output", "dispatch-start.json"},
        )
        for route in ROUTES
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
    expected_dispatch_hashes = metadata.get("dispatch_start_sha256")
    if not isinstance(expected_dispatch_hashes, dict):
        expected_dispatch_hashes = {}
    observed_dispatch_hashes = {}
    for route in ROUTES:
        marker = run_dir / "cases" / route / "dispatch-start.json"
        observed_dispatch_hashes[route] = (
            hashlib.sha256(marker.read_bytes()).hexdigest()
            if marker.is_file()
            else None
        )
    dispatch_binding = {
        "status": (
            "pass"
            if set(expected_dispatch_hashes) == set(ROUTES)
            and observed_dispatch_hashes == expected_dispatch_hashes
            else "fail"
        ),
        "expected_dispatch_start_sha256": expected_dispatch_hashes,
        "observed_dispatch_start_sha256": observed_dispatch_hashes,
    }
    if (
        evaluator_binding["status"] != "pass"
        or oracle_binding["status"] != "pass"
        or runtime_binding["status"] != "pass"
        or case_input_binding["status"] != "pass"
        or dispatch_binding["status"] != "pass"
    ):
        receipt = {
            "schema_version": 1,
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "status": "fail",
            "fixture": {
                "duration_proxy_minutes": duration_minutes,
                "source_words": metadata["source_words"],
                "risk": "low",
                "source_count": 1,
                "revision_count": 1,
            },
            "routes": {},
            "recommended_route_for_fixture": "unresolved",
            "proof_boundary": (
                "Scoring stopped before oracle evaluation because the evaluator, "
                "oracle, staged runtime, case inputs, or dispatch markers changed "
                "after preparation."
            ),
            "run_metadata": metadata,
            "evaluator_binding": evaluator_binding,
            "oracle_binding": oracle_binding,
            "runtime_binding": runtime_binding,
            "case_input_binding": case_input_binding,
            "dispatch_binding": dispatch_binding,
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        write_json(receipt_path, receipt)
        return receipt

    oracle = load_json(selected_oracle)
    auditor = load_auditor(skill_root / "scripts" / "audit_bundle.py")
    routes = {
        route: score_route(run_dir, route, oracle, auditor)
        for route in ROUTES
    }
    recommendation = "unresolved"
    if runtime_binding["status"] == "pass":
        for route in ROUTES:
            if routes[route]["status"] == "pass":
                recommendation = route
                break
    receipt = {
        "schema_version": 1,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "pass"
            if runtime_binding["status"] == "pass"
            and all(result["status"] == "pass" for result in routes.values())
            else "fail"
        ),
        "fixture": {
            "duration_proxy_minutes": duration_minutes,
            "source_words": metadata["source_words"],
            "risk": "low",
            "source_count": 1,
            "revision_count": 1,
        },
        "routes": routes,
        "recommended_route_for_fixture": recommendation,
        "token_measurement": (
            "output_token_proxy is ceil(serialized artifact bytes / 4), excluding "
            "copied source bytes; actual model billing tokens are unavailable."
        ),
        "proof_boundary": (
            "One synthetic low-risk transcript and one model family; recovery is "
            "artifact-based rather than a second cold-reader run; the staged runtime "
            "has artifact-level quarantine without host filesystem attestation."
        ),
        "run_metadata": metadata,
        "evaluator_binding": evaluator_binding,
        "oracle_binding": oracle_binding,
        "runtime_binding": runtime_binding,
        "case_input_binding": case_input_binding,
        "dispatch_binding": dispatch_binding,
    }
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(receipt_path, receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("--run-dir", type=Path, required=True)
    prepare_parser.add_argument("--skill-root", type=Path, required=True)
    prepare_parser.add_argument(
        "--duration-minutes",
        type=int,
        choices=(15, 60),
        default=15,
    )
    start_parser = subparsers.add_parser("mark-start")
    start_parser.add_argument("--run-dir", type=Path, required=True)
    start_parser.add_argument("--case-id", choices=ROUTES, required=True)
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("--run-dir", type=Path, required=True)
    score_parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.command == "prepare":
            result = prepare(
                args.run_dir,
                args.skill_root,
                duration_minutes=args.duration_minutes,
            )
        elif args.command == "mark-start":
            result = mark_start(args.run_dir, args.case_id)
        else:
            result = score(args.run_dir, args.receipt)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        result = {"status": "fail", "error": str(exc)}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status", "pass") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
