from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_bundle.py"
SPEC = importlib.util.spec_from_file_location("audit_bundle", SCRIPT)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class AuditBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for name in ("run-manifest.md", "synthesis.md", "handoff.md"):
            (self.root / name).write_text(f"# {name}\n", encoding="utf-8")

        self.sources = [
            {
                "source_id": "S1",
                "source_ref": "input.txt",
                "revision": "sha256:abc",
                "material_type": "transcript",
                "locator_scheme": "line",
                "instruction_trust": "data-only",
                "representation_limits": [],
                "coverage_mode": "contiguous-lines",
                "line_count": 4,
            }
        ]
        self.chunks = [
            {
                "chunk_id": "S1-C001",
                "source_id": "S1",
                "ordinal": 1,
                "line_start": 1,
                "line_end": 2,
                "content_line_start": 1,
                "content_line_end": 2,
                "overlap_line_count": 0,
            },
            {
                "chunk_id": "S1-C002",
                "source_id": "S1",
                "ordinal": 2,
                "line_start": 2,
                "line_end": 4,
                "content_line_start": 3,
                "content_line_end": 4,
                "overlap_line_count": 1,
            },
        ]
        self.notes = [
            {
                "chunk_id": "S1-C001",
                "status": "distilled",
                "gist": "First half",
                "evidence_ids": ["E1"],
            },
            {
                "chunk_id": "S1-C002",
                "status": "distilled",
                "gist": "Second half",
                "evidence_ids": ["E2"],
            },
        ]
        self.evidence = [
            {
                "evidence_id": "E1",
                "source_id": "S1",
                "chunk_id": "S1-C001",
                "locator": "lines 1-2",
                "statement": "Alpha",
                "polarity": "supports",
                "duplicate_of": None,
            },
            {
                "evidence_id": "E2",
                "source_id": "S1",
                "chunk_id": "S1-C002",
                "locator": "lines 3-4",
                "statement": "Beta",
                "polarity": "supports",
                "duplicate_of": None,
            },
        ]
        self.claims = [
            {
                "claim_id": "C1",
                "claim": "Alpha and beta",
                "type": "factual",
                "status": "source-only",
                "evidence_ids": ["E1", "E2"],
                "independent_source_ids": ["S1"],
                "verification_refs": [],
            }
        ]
        self.coverage = {
            "sources": [
                {
                    "source_id": "S1",
                    "planned_chunks": ["S1-C001", "S1-C002"],
                    "distilled_chunks": ["S1-C001", "S1-C002"],
                    "skipped_chunks": [],
                }
            ],
            "facets": [
                {
                    "facet": "limitations",
                    "status": "covered",
                    "evidence_ids": ["E2"],
                }
            ],
            "risk_checks": [],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_bundle(self):
        write_jsonl(self.root / "sources.jsonl", self.sources)
        write_jsonl(self.root / "chunks.jsonl", self.chunks)
        write_jsonl(self.root / "chunk-notes.jsonl", self.notes)
        write_jsonl(self.root / "evidence.jsonl", self.evidence)
        write_jsonl(self.root / "claims.jsonl", self.claims)
        (self.root / "coverage.json").write_text(
            json.dumps(self.coverage), encoding="utf-8"
        )

    def audit(self):
        self.write_bundle()
        return audit_module.audit_bundle(self.root)

    def test_valid_bundle_passes_and_overlap_is_not_double_counted(self):
        receipt = self.audit()
        self.assertEqual(receipt["status"], "pass", receipt["errors"])
        self.assertEqual(receipt["counts"]["chunks"], 2)

    def test_missing_chunk_note_fails(self):
        self.notes.pop()
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("missing notes" in error for error in receipt["errors"]))

    def test_unique_content_gap_fails(self):
        self.chunks[1]["content_line_start"] = 4
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("unique-content gap" in error for error in receipt["errors"]))

    def test_externally_verified_claim_requires_reference(self):
        self.claims[0]["status"] = "externally-verified"
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any("externally-verified needs" in error for error in receipt["errors"])
        )

    def test_covered_facet_requires_evidence(self):
        self.coverage["facets"][0]["evidence_ids"] = []
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any("covered facet needs" in error for error in receipt["errors"])
        )

    def test_unknown_duplicate_target_fails(self):
        self.evidence[1]["duplicate_of"] = "E404"
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("unknown duplicate_of" in error for error in receipt["errors"]))

    def test_note_evidence_must_belong_to_the_same_chunk(self):
        self.notes[0]["evidence_ids"] = ["E2"]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("belongs to S1-C002" in error for error in receipt["errors"]))

    def test_orphan_evidence_must_be_listed_by_its_chunk_note(self):
        self.notes[1]["evidence_ids"] = []
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any("evidence E2: not listed by chunk note" in error for error in receipt["errors"])
        )

    def test_malformed_note_evidence_list_fails_without_crashing(self):
        self.notes[0]["evidence_ids"] = [{"bad": "shape"}]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any("list of non-empty strings" in error for error in receipt["errors"])
        )

    def test_duplicate_cycle_fails(self):
        self.evidence[0]["duplicate_of"] = "E2"
        self.evidence[1]["duplicate_of"] = "E1"
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("cycle detected" in error for error in receipt["errors"]))

    def test_independent_source_ids_must_be_unique(self):
        self.claims[0]["independent_source_ids"] = ["S1", "S1"]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any(
                "independent_source_ids must be unique" in error
                for error in receipt["errors"]
            )
        )

    def test_claim_evidence_ids_must_be_unique(self):
        self.claims[0]["evidence_ids"] = ["E1", "E1"]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any(
                "claim C1: evidence_ids must be unique" in error
                for error in receipt["errors"]
            )
        )

    def test_independent_source_needs_claim_linked_evidence(self):
        source = dict(self.sources[0])
        source.update(
            {
                "source_id": "S2",
                "source_ref": "second.txt",
                "revision": "sha256:def",
                "line_count": 0,
            }
        )
        self.sources.append(source)
        self.coverage["sources"].append(
            {
                "source_id": "S2",
                "planned_chunks": [],
                "distilled_chunks": [],
                "skipped_chunks": [],
                "source_skip_reason": "No relevant extract available",
            }
        )
        self.claims[0]["independent_source_ids"].append("S2")
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any(
                "independent sources lack claim evidence: S2" in error
                for error in receipt["errors"]
            )
        )

    def test_unprocessed_source_requires_skip_reason(self):
        source = dict(self.sources[0])
        source.update(
            {
                "source_id": "S2",
                "source_ref": "second.txt",
                "revision": "sha256:def",
                "line_count": 0,
            }
        )
        self.sources.append(source)
        self.coverage["sources"].append(
            {
                "source_id": "S2",
                "planned_chunks": [],
                "distilled_chunks": [],
                "skipped_chunks": [],
            }
        )
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("source_skip_reason" in error for error in receipt["errors"]))

    def test_absent_facet_requires_search_note(self):
        self.coverage["facets"][0] = {
            "facet": "minority-view",
            "status": "absent",
            "evidence_ids": [],
        }
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("search_note" in error for error in receipt["errors"]))

    def test_risk_check_must_resolve_reviewed_chunks(self):
        self.coverage["risk_checks"] = [
            {
                "risk": "boundary",
                "status": "pass",
                "reviewed_chunks": ["S1-C404"],
            }
        ]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any(
                "unknown reviewed chunk S1-C404" in error
                for error in receipt["errors"]
            )
        )

    def test_coverage_chunk_ids_must_be_unique(self):
        self.coverage["sources"][0]["planned_chunks"].append("S1-C002")
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(
            any(
                "planned_chunks must be unique" in error
                for error in receipt["errors"]
            )
        )

    def test_loaded_line_range_must_contain_unique_content(self):
        self.chunks[1]["line_end"] = 3
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("invalid loaded line range" in error for error in receipt["errors"]))

    def test_skipped_chunk_requires_reason_and_coverage_match(self):
        self.notes[1] = {
            "chunk_id": "S1-C002",
            "status": "skipped",
            "skip_reason": "",
            "evidence_ids": [],
        }
        self.coverage["sources"][0]["distilled_chunks"] = ["S1-C001"]
        self.coverage["sources"][0]["skipped_chunks"] = [
            {"chunk_id": "S1-C002", "reason": "duplicate"}
        ]
        receipt = self.audit()
        self.assertEqual(receipt["status"], "fail")
        self.assertTrue(any("skip_reason" in error for error in receipt["errors"]))

    def test_cli_returns_machine_readable_receipt(self):
        self.write_bundle()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.root)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["status"], "pass")
        self.assertEqual(receipt["counts"]["evidence"], 2)


if __name__ == "__main__":
    unittest.main()
