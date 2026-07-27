#!/usr/bin/env python3
"""Benchmark chunker latency and peak RSS on representative source sizes."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import resource
except ImportError:  # Windows has no standard-library RSS API.
    resource = None


ROOT = Path(__file__).resolve().parents[1]
CHUNKER = ROOT / "scripts" / "chunk_text.py"
WORDS_PER_MINUTE = 150


DEFAULT_CASES = (
    {
        "case_id": "transcript-15m",
        "target_words": 15 * WORDS_PER_MINUTE,
        "target_bytes": None,
        "max_rss_mb": 128.0,
        "max_elapsed_seconds": 10.0,
    },
    {
        "case_id": "transcript-60m",
        "target_words": 60 * WORDS_PER_MINUTE,
        "target_bytes": None,
        "max_rss_mb": 192.0,
        "max_elapsed_seconds": 15.0,
    },
    {
        "case_id": "large-corpus-24mb",
        "target_words": None,
        "target_bytes": 24 * 1024 * 1024,
        "max_rss_mb": 300.0,
        "max_elapsed_seconds": 90.0,
    },
)


def synthetic_line(index: int) -> str:
    minutes, seconds = divmod(index, 60)
    return (
        f"{minutes:04d}:{seconds:02d} record {index} preserves source context "
        "boundary evidence caveat decision and locator\n"
    )


def write_fixture(
    path: Path,
    *,
    target_words: int | None,
    target_bytes: int | None,
) -> dict[str, int]:
    line_count = 0
    word_count = 0
    byte_count = 0
    with path.open("wb") as stream:
        while True:
            if target_words is not None and word_count >= target_words:
                break
            if target_bytes is not None and byte_count >= target_bytes:
                break
            line = synthetic_line(line_count + 1).encode("utf-8")
            stream.write(line)
            line_count += 1
            word_count += len(line.split())
            byte_count += len(line)
    return {
        "input_bytes": byte_count,
        "line_count": line_count,
        "word_count": word_count,
    }


def peak_rss_mb() -> float | None:
    if resource is None:
        return None
    observed = float(resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
    if sys.platform == "darwin":
        return observed / (1024 * 1024)
    return observed / 1024


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="asd-resource-") as temp:
        root = Path(temp)
        source = root / "source.txt"
        output = root / "chunks.jsonl"
        fixture = write_fixture(
            source,
            target_words=case.get("target_words"),
            target_bytes=case.get("target_bytes"),
        )
        command = [
            sys.executable,
            str(CHUNKER),
            str(source),
            "--source-id",
            "BENCH",
            "--source-revision-id",
            "BENCH-R1",
            "--max-words",
            "900",
            "--overlap-words",
            "80",
            "--format",
            "jsonl",
            "--output",
            str(output),
        ]
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        elapsed = time.perf_counter() - started
        output_chunks = 0
        output_bytes = 0
        if output.is_file():
            output_bytes = output.stat().st_size
            with output.open("r", encoding="utf-8") as stream:
                output_chunks = sum(1 for line in stream if line.strip())
        rss_mb = peak_rss_mb()
        errors: list[str] = []
        warnings: list[str] = []
        if completed.returncode != 0:
            errors.append(
                f"chunker exited {completed.returncode}: {completed.stderr.strip()}"
            )
        if rss_mb is None:
            warnings.append(
                "peak RSS not measured: this platform lacks Python's resource module"
            )
            errors.append(
                "peak RSS gate cannot pass because the required metric was not measured"
            )
        elif rss_mb > case["max_rss_mb"]:
            errors.append(
                f"peak RSS {rss_mb:.2f} MB exceeds {case['max_rss_mb']:.2f} MB"
            )
        if elapsed > case["max_elapsed_seconds"]:
            errors.append(
                f"elapsed {elapsed:.3f}s exceeds "
                f"{case['max_elapsed_seconds']:.3f}s"
            )
        return {
            "case_id": case["case_id"],
            **fixture,
            "output_bytes": output_bytes,
            "output_chunks": output_chunks,
            "peak_rss_mb": round(rss_mb, 3) if rss_mb is not None else None,
            "peak_rss_status": "measured" if rss_mb is not None else "not-measured",
            "elapsed_seconds": round(elapsed, 3),
            "max_rss_mb": case["max_rss_mb"],
            "max_elapsed_seconds": case["max_elapsed_seconds"],
            "status": "pass" if not errors else "fail",
            "errors": errors,
            "warnings": warnings,
        }


def run_case_subprocess(case: dict[str, Any]) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "_case",
        "--case-json",
        json.dumps(case),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {
            "case_id": case["case_id"],
            "status": "fail",
            "errors": [
                f"benchmark worker emitted invalid JSON: {exc}",
                completed.stderr.strip(),
            ],
        }
    if completed.returncode not in {0, 1}:
        result.setdefault("errors", []).append(
            f"benchmark worker exited {completed.returncode}"
        )
        result["status"] = "fail"
    return result


def run_suite(receipt: Path) -> dict[str, Any]:
    results = [run_case_subprocess(case) for case in DEFAULT_CASES]
    value = {
        "schema_version": 1,
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "status": (
            "pass"
            if all(result.get("status") == "pass" for result in results)
            else "fail"
        ),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "words_per_minute_assumption": WORDS_PER_MINUTE,
        "historical_pre_refactor_peak_rss_mb": {
            "input_range_mb": "20-26",
            "observed_range_mb": "553-666",
            "source": "2026-07-26 authoritative review reproduction",
        },
        "cases": results,
        "proof_boundary": (
            "Local synthetic chunker resource measurements; not a guarantee for every "
            "filesystem, Python build, or source structure."
        ),
    }
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    suite_parser = subparsers.add_parser("run")
    suite_parser.add_argument("--receipt", type=Path, required=True)
    case_parser = subparsers.add_parser("_case")
    case_parser.add_argument("--case-json", required=True)
    args = parser.parse_args()

    if args.command == "_case":
        case = json.loads(args.case_json)
        result = run_case(case)
    else:
        result = run_suite(args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
