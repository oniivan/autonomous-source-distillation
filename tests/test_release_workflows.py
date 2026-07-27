from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, file_name: str):
    path = ROOT / "scripts" / file_name
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


benchmark_resources = load_script("release_benchmark_resources", "benchmark_resources.py")
evaluation_contract = load_script(
    "release_evaluation_contract",
    "evaluation_contract.py",
)
locator_utils = load_script("release_locator_utils", "locator_utils.py")
semantic_eval = load_script("release_semantic_eval", "semantic_eval.py")
mutation_suite = load_script("release_mutation_suite", "run_mutation_suite.py")
release_replay = load_script("release_replay_bundles", "replay_release_bundles.py")
route_comparison = load_script("release_route_comparison", "route_comparison.py")
runtime_contract = load_script("release_runtime_contract", "runtime_contract.py")


class ReleaseWorkflowTests(unittest.TestCase):
    def test_runtime_manifest_cli_works_from_external_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "runtime_contract.py"),
                    "--skill-root",
                    str(ROOT),
                ],
                cwd=temp,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(result.stdout)
        self.assertEqual(
            manifest["skill_runtime_sha256"],
            runtime_contract.runtime_digest(ROOT),
        )

    def test_line_locator_matching_is_exact(self):
        self.assertTrue(locator_utils.exact_line_set("00:48; line 12", [12]))
        self.assertTrue(locator_utils.exact_line_set("lines 2-3", [2, 3]))
        self.assertFalse(locator_utils.exact_line_set("line 112", [12]))
        self.assertFalse(locator_utils.exact_line_set("lines 20-30", [2, 3]))
        self.assertTrue(
            route_comparison.exact_route_line(
                "inputs/source.txt:12 (00:48)",
                12,
            )
        )
        self.assertFalse(
            route_comparison.exact_route_line("inputs/source.txt:112", 12)
        )
        self.assertFalse(
            route_comparison.exact_route_line(
                "inputs/source.txt:12; line 112",
                12,
            )
        )
        self.assertFalse(route_comparison.exact_route_line("other.txt:12", 12))

    def test_semantic_prepare_does_not_copy_oracle(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "random-eval-root"
            metadata = semantic_eval.prepare(run_dir)

            self.assertFalse(metadata["oracle_copied_to_run"])
            self.assertEqual(len(metadata["cases"]), 5)
            self.assertFalse(any(run_dir.rglob("expected.json")))
            self.assertFalse(metadata["runtime_isolation"]["forbidden_paths_present"])
            self.assertFalse((run_dir / "runtime" / "evals").exists())
            self.assertEqual(
                metadata["evaluator_sha256"],
                semantic_eval.sha256_file(ROOT / "scripts" / "semantic_eval.py"),
            )
            self.assertEqual(
                metadata["evaluator_surface"],
                semantic_eval.evaluator_surface(),
            )
            self.assertEqual(
                metadata["oracle_sha256"],
                semantic_eval.sha256_file(semantic_eval.ORACLE),
            )
            for case in metadata["cases"]:
                self.assertTrue(Path(case["task"]).is_file())

    def test_prepare_rejects_missing_runtime_before_creating_run(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            missing = temp_root / "missing-skill"
            semantic_run = temp_root / "semantic-run"
            route_run = temp_root / "route-run"

            with self.assertRaises(ValueError):
                semantic_eval.prepare(semantic_run, missing)
            with self.assertRaises(ValueError):
                route_comparison.prepare(route_run, missing)

            self.assertFalse(semantic_run.exists())
            self.assertFalse(route_run.exists())

    def test_resource_fixture_meets_requested_word_floor(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "source.txt"
            fixture = benchmark_resources.write_fixture(
                target,
                target_words=2250,
                target_bytes=None,
            )

            self.assertGreaterEqual(fixture["word_count"], 2250)
            self.assertEqual(fixture["input_bytes"], target.stat().st_size)
            self.assertGreater(fixture["line_count"], 0)

    def test_resource_gate_fails_when_rss_is_not_measured(self):
        original_resource = benchmark_resources.resource
        benchmark_resources.resource = None
        try:
            result = benchmark_resources.run_case(
                {
                    "case_id": "no-rss",
                    "target_words": 10,
                    "target_bytes": None,
                    "max_rss_mb": 0.001,
                    "max_elapsed_seconds": 10.0,
                }
            )
        finally:
            benchmark_resources.resource = original_resource

        self.assertEqual(result["status"], "fail", result)
        self.assertEqual(result["peak_rss_status"], "not-measured")

    def test_preserved_mutation_suite_passes(self):
        receipt = mutation_suite.run_suite()

        self.assertEqual(receipt["status"], "pass", receipt)
        self.assertGreaterEqual(len(receipt["cases"]), 18)
        self.assertFalse(any(case["exception"] for case in receipt["cases"]))

    def test_route_comparison_stages_a_real_15_minute_proxy(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "route-run"
            metadata = route_comparison.prepare(run_dir, ROOT)

            self.assertFalse(metadata["oracle_copied_to_run"])
            self.assertEqual(len(metadata["cases"]), 3)
            self.assertGreaterEqual(metadata["source_words"], 2250)
            self.assertLess(metadata["source_words"], 2300)
            self.assertFalse(any(run_dir.rglob("oracle.json")))
            self.assertFalse((run_dir / "runtime" / "evals").exists())
            self.assertEqual(
                metadata["evaluator_sha256"],
                route_comparison.sha256_file(
                    ROOT / "scripts" / "route_comparison.py"
                ),
            )
            self.assertEqual(
                metadata["evaluator_surface"],
                route_comparison.evaluator_surface(),
            )
            self.assertEqual(
                metadata["oracle_sha256"],
                route_comparison.sha256_file(route_comparison.ORACLE),
            )

    def test_route_comparison_stages_a_real_60_minute_proxy(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "route-run"
            metadata = route_comparison.prepare(
                run_dir,
                ROOT,
                duration_minutes=60,
            )

            self.assertEqual(metadata["duration_proxy_minutes"], 60)
            self.assertGreaterEqual(metadata["source_words"], 9000)
            self.assertLess(metadata["source_words"], 9100)
            self.assertEqual(len(route_comparison.source_lines(60)), 900)
            self.assertFalse((run_dir / "runtime" / "evals").exists())
            self.assertEqual(
                metadata["oracle_sha256"],
                route_comparison.sha256_file(route_comparison.ORACLE_60M),
            )

    def test_committed_release_receipts_pass(self):
        receipts = (
            ROOT
            / "evals"
            / "semantic"
            / "releases"
            / "2026-07-27"
            / "semantic-evaluation-receipt.json",
            ROOT
            / "evals"
            / "routing"
            / "releases"
            / "2026-07-27-15m"
            / "route-comparison-receipt.json",
            ROOT
            / "evals"
            / "routing"
            / "releases"
            / "2026-07-27-60m"
            / "route-comparison-receipt.json",
            ROOT
            / "evals"
            / "resources"
            / "releases"
            / "2026-07-27"
            / "resource-receipt.json",
            ROOT
            / "evals"
            / "mutations"
            / "releases"
            / "2026-07-27"
            / "mutation-receipt.json",
            ROOT
            / "evals"
            / "replay"
            / "releases"
            / "2026-07-27"
            / "replay-receipt.json",
        )
        for receipt in receipts:
            with self.subTest(receipt=receipt):
                value = json.loads(receipt.read_text(encoding="utf-8"))
                self.assertEqual(value["status"], "pass", value)

    def test_semantic_score_rejects_bound_runtime_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            skill_root = temp_root / "skill"
            shutil.copytree(
                ROOT,
                skill_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            run_dir = temp_root / "run"
            semantic_eval.prepare(run_dir, skill_root)
            release_cases = (
                ROOT
                / "evals"
                / "semantic"
                / "releases"
                / "2026-07-27"
                / "cases"
            )
            for case in semantic_eval.CASE_NAMES:
                shutil.copytree(
                    release_cases / case / "output",
                    run_dir / "cases" / case / "output",
                )

            runtime_skill = run_dir / "runtime" / "SKILL.md"
            runtime_skill.write_text(
                runtime_skill.read_text(encoding="utf-8")
                + "\nBehavior-bearing drift.\n",
                encoding="utf-8",
            )
            receipt = semantic_eval.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["runtime_binding"]["status"], "fail")

    def test_semantic_score_rejects_staged_input_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            semantic_eval.prepare(run_dir, ROOT)
            task = run_dir / "cases" / "C-boundary-overlap" / "task.md"
            task.write_text(
                task.read_text(encoding="utf-8") + "\ncontaminated\n",
                encoding="utf-8",
            )

            receipt = semantic_eval.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["case_input_binding"]["status"], "fail")
            self.assertEqual(receipt["cases"], {})

    def test_semantic_score_rejects_evaluator_binding_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            semantic_eval.prepare(run_dir, ROOT)
            metadata_path = run_dir / "run-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["evaluator_sha256"] = "0" * 64
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            receipt = semantic_eval.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["evaluator_binding"]["status"], "fail")
            self.assertEqual(receipt["oracle_binding"]["status"], "pass")
            self.assertEqual(receipt["cases"], {})

    def test_evaluators_reject_package_local_helper_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            skill_root = temp_root / "skill"
            shutil.copytree(
                ROOT,
                skill_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            semantic_run = temp_root / "semantic-run"
            route_run = temp_root / "route-run"
            subprocess.run(
                [
                    sys.executable,
                    str(skill_root / "scripts" / "semantic_eval.py"),
                    "prepare",
                    "--run-dir",
                    str(semantic_run),
                    "--skill-root",
                    str(skill_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(skill_root / "scripts" / "route_comparison.py"),
                    "prepare",
                    "--run-dir",
                    str(route_run),
                    "--skill-root",
                    str(skill_root),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            for route in route_comparison.ROUTES:
                subprocess.run(
                    [
                        sys.executable,
                        str(skill_root / "scripts" / "route_comparison.py"),
                        "mark-start",
                        "--run-dir",
                        str(route_run),
                        "--case-id",
                        route,
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            helper = skill_root / "scripts" / "locator_utils.py"
            helper.write_text(
                helper.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )

            semantic_receipt_path = temp_root / "semantic-receipt.json"
            route_receipt_path = temp_root / "route-receipt.json"
            subprocess.run(
                [
                    sys.executable,
                    str(skill_root / "scripts" / "semantic_eval.py"),
                    "score",
                    "--run-dir",
                    str(semantic_run),
                    "--receipt",
                    str(semantic_receipt_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(skill_root / "scripts" / "route_comparison.py"),
                    "score",
                    "--run-dir",
                    str(route_run),
                    "--receipt",
                    str(route_receipt_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            semantic_receipt = json.loads(
                semantic_receipt_path.read_text(encoding="utf-8")
            )
            route_receipt = json.loads(
                route_receipt_path.read_text(encoding="utf-8")
            )

            self.assertEqual(semantic_receipt["status"], "fail")
            self.assertEqual(
                semantic_receipt["evaluator_binding"]["status"],
                "fail",
            )
            self.assertEqual(semantic_receipt["runtime_binding"]["status"], "pass")
            self.assertEqual(route_receipt["status"], "fail")
            self.assertEqual(
                route_receipt["evaluator_binding"]["status"],
                "fail",
            )
            self.assertEqual(route_receipt["runtime_binding"]["status"], "pass")

    def test_route_score_rejects_staged_input_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            route_comparison.prepare(run_dir, ROOT)
            task = run_dir / "cases" / "direct" / "task.md"
            task.write_text(
                task.read_text(encoding="utf-8") + "\ncontaminated\n",
                encoding="utf-8",
            )

            receipt = route_comparison.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["case_input_binding"]["status"], "fail")
            self.assertEqual(receipt["routes"], {})

    def test_route_score_rejects_dispatch_marker_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            route_comparison.prepare(run_dir, ROOT)
            for route in route_comparison.ROUTES:
                route_comparison.mark_start(run_dir, route)
            marker = run_dir / "cases" / "direct" / "dispatch-start.json"
            marker.write_text(
                marker.read_text(encoding="utf-8") + " ",
                encoding="utf-8",
            )

            receipt = route_comparison.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["dispatch_binding"]["status"], "fail")
            self.assertEqual(receipt["routes"], {})

    def test_route_score_rejects_oracle_binding_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            route_comparison.prepare(run_dir, ROOT)
            for route in route_comparison.ROUTES:
                route_comparison.mark_start(run_dir, route)
            metadata_path = run_dir / "run-metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["oracle_sha256"] = "0" * 64
            metadata_path.write_text(
                json.dumps(metadata, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            receipt = route_comparison.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["evaluator_binding"]["status"], "pass")
            self.assertEqual(receipt["oracle_binding"]["status"], "fail")
            self.assertEqual(receipt["routes"], {})

    def test_route_mark_start_is_create_once_and_precedes_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            run_dir = Path(temp) / "run"
            route_comparison.prepare(run_dir, ROOT)
            route_comparison.mark_start(run_dir, "direct")
            with self.assertRaises(ValueError):
                route_comparison.mark_start(run_dir, "direct")

            output = run_dir / "cases" / "light" / "output"
            output.mkdir()
            (output / "result.json").write_text("{}\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                route_comparison.mark_start(run_dir, "light")

    def test_route_score_rejects_outputs_that_predate_dispatch(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            run_dir = temp_root / "run"
            route_comparison.prepare(run_dir, ROOT)
            for route in route_comparison.ROUTES:
                route_comparison.mark_start(run_dir, route)
                shutil.copytree(
                    ROOT
                    / "evals"
                    / "routing"
                    / "releases"
                    / "2026-07-27-15m"
                    / "cases"
                    / route
                    / "output",
                    run_dir / "cases" / route / "output",
                )
            direct_result = run_dir / "cases" / "direct" / "output" / "result.json"
            os.utime(direct_result, (1, 1))

            receipt = route_comparison.score(
                run_dir,
                temp_root / "receipt.json",
            )

            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertTrue(
                receipt["routes"]["direct"]["measurements"][
                    "output_predates_start"
                ]
            )
            self.assertTrue(
                any(
                    "predate the dispatch marker" in error
                    for error in receipt["routes"]["direct"]["errors"]
                )
            )

    def test_retained_serious_bundles_replay_on_current_runtime(self):
        receipt = release_replay.replay(ROOT)

        self.assertEqual(receipt["compatibility_status"], "pass", receipt)
        self.assertEqual(receipt["source_receipts_status"], "pass")
        self.assertEqual(receipt["behavioral_binding_status"], "pass", receipt)
        self.assertEqual(receipt["evaluation_binding_status"], "pass", receipt)
        self.assertEqual(receipt["provenance_status"], "pass", receipt)
        self.assertEqual(receipt["behavioral_case_count"], 11)
        self.assertEqual(receipt["total_replayed_case_count"], 12)
        self.assertEqual(len(receipt["cases"]), 12)
        for case in receipt["cases"].values():
            self.assertEqual(case["output_hash_status"], "pass", case)
            if case["audit_required"]:
                self.assertEqual(case["audit"]["structure_status"], "pass", case)
                self.assertEqual(case["audit"]["readiness_status"], "pass", case)
            else:
                self.assertIsNone(case["audit"])
        self.assertEqual(receipt["status"], "pass", receipt)

    def test_release_replay_fails_for_every_missing_behavioral_output(self):
        semantic_receipt = json.loads(
            (
                ROOT
                / "evals"
                / "semantic"
                / "releases"
                / "2026-07-27"
                / "semantic-evaluation-receipt.json"
            ).read_text(encoding="utf-8")
        )
        targets = [
            (
                f"semantic/{case_id}",
                Path("evals")
                / "semantic"
                / "releases"
                / "2026-07-27"
                / "cases"
                / case_id
                / "output",
            )
            for case_id in semantic_receipt["cases"]
        ]
        for release_name in ("2026-07-27-15m", "2026-07-27-60m"):
            route_receipt = json.loads(
                (
                    ROOT
                    / "evals"
                    / "routing"
                    / "releases"
                    / release_name
                    / "route-comparison-receipt.json"
                ).read_text(encoding="utf-8")
            )
            duration = route_receipt["fixture"]["duration_proxy_minutes"]
            targets.extend(
                (
                    f"routing/{duration}m/{route}",
                    Path("evals")
                    / "routing"
                    / "releases"
                    / release_name
                    / "cases"
                    / route
                    / "output",
                )
                for route in route_receipt["routes"]
            )

        with tempfile.TemporaryDirectory() as temp:
            skill_root = Path(temp) / "skill"
            shutil.copytree(
                ROOT,
                skill_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            for case_id, relative_output in targets:
                with self.subTest(case_id=case_id):
                    output = skill_root / relative_output
                    hidden = output.with_name("output.hidden")
                    output.rename(hidden)
                    try:
                        receipt = release_replay.replay(skill_root)
                    finally:
                        hidden.rename(output)
                    self.assertEqual(receipt["status"], "fail", receipt)
                    self.assertEqual(
                        receipt["cases"][case_id]["output_hash_status"],
                        "fail",
                    )

    def test_release_replay_rejects_content_free_provenance(self):
        with tempfile.TemporaryDirectory() as temp:
            skill_root = Path(temp) / "skill"
            shutil.copytree(
                ROOT,
                skill_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            provenance_path = (
                skill_root
                / "evals"
                / "semantic"
                / "releases"
                / "2026-07-27"
                / "generation-provenance.json"
            )
            original = provenance_path.read_text(encoding="utf-8")
            provenance_path.write_text(
                '{"status":"pass"}\n',
                encoding="utf-8",
            )
            receipt = release_replay.replay(skill_root)
            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["provenance_status"], "fail", receipt)
            provenance_path.write_text(original, encoding="utf-8")

            route_receipt_path = (
                skill_root
                / "evals"
                / "routing"
                / "releases"
                / "2026-07-27-15m"
                / "route-comparison-receipt.json"
            )
            route_receipt = json.loads(
                route_receipt_path.read_text(encoding="utf-8")
            )
            route_receipt["run_metadata"]["generation_provenance"] = {}
            route_receipt_path.write_text(
                json.dumps(route_receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            receipt = release_replay.replay(skill_root)
            self.assertEqual(receipt["status"], "fail", receipt)
            self.assertEqual(receipt["provenance_status"], "fail", receipt)

    def test_release_replay_rejects_precorrection_hash_drift(self):
        with tempfile.TemporaryDirectory() as temp:
            skill_root = Path(temp) / "skill"
            shutil.copytree(
                ROOT,
                skill_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__"),
            )
            receipt_path = (
                skill_root
                / "evals"
                / "routing"
                / "releases"
                / "2026-07-27-15m"
                / "precorrection-locator-receipt.json"
            )
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            receipt["routes"]["direct"]["output_tree_sha256"] = "0" * 64
            receipt_path.write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            replay = release_replay.replay(skill_root)

            self.assertEqual(replay["status"], "fail", replay)
            self.assertEqual(replay["provenance_status"], "fail", replay)


if __name__ == "__main__":
    unittest.main()
