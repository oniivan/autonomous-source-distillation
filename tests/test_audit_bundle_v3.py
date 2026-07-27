from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "audit_bundle.py"
SPEC = importlib.util.spec_from_file_location("audit_bundle_v3", SCRIPT)
assert SPEC and SPEC.loader
audit_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_module)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class V3AuditBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "inputs").mkdir()
        self.source_text = "alpha\nbeta\n"
        (self.root / "inputs" / "source.txt").write_text(
            self.source_text,
            encoding="utf-8",
        )
        self.source_sha256 = sha256_text(self.source_text)
        self.chunk_text = "alpha\nbeta"
        self.chunk_sha256 = sha256_text(self.chunk_text)

        (self.root / "run-manifest.md").write_text(
            "# Run Manifest\n\nSerious source distillation fixture.\n",
            encoding="utf-8",
        )
        (self.root / "synthesis.md").write_text(
            "# Synthesis\n\nThe source contains alpha and beta.\n",
            encoding="utf-8",
        )
        (self.root / "handoff.md").write_text(
            "# Handoff\n\nReload claims.jsonl and sources.jsonl.\n",
            encoding="utf-8",
        )

        self.manifest = {
            "schema_version": 3,
            "route": "serious",
            "objective": "Recover the two source facts.",
            "output_mode": "methodology",
            "required_facets": ["limitations"],
            "required_risks": ["boundary"],
            "acceptable_loss": "low",
            "completion_oracle": "Both facts have exact line evidence.",
            "allow_empty_result": False,
            "semantic_evaluation_required": False,
            "semantic_evaluation_receipt": None,
            "handoff": {
                "source_revision_ids": ["S1-R1"],
                "key_claim_ids": ["C1"],
                "reload_paths": [
                    "sources.jsonl",
                    "claims.jsonl",
                    "handoff.md",
                ],
                "unresolved_gaps": [],
                "safe_to_drop": ["inputs/source.txt"],
            },
        }
        self.sources = [
            {
                "schema_version": 3,
                "source_id": "S1",
                "source_revision_id": "S1-R1",
                "source_ref": "inputs/source.txt",
                "revision": f"sha256:{self.source_sha256}",
                "source_sha256": self.source_sha256,
                "source_family_id": "F1",
                "derived_from_source_ids": [],
                "accessed_at": "2026-07-26",
                "material_type": "transcript",
                "locator_scheme": "line",
                "sensitivity": "private",
                "instruction_trust": "data-only",
                "representation_limits": [],
                "coverage_mode": "contiguous-lines",
                "line_count": 2,
            }
        ]
        self.chunks = [
            {
                "schema_version": 3,
                "chunk_id": "S1-R1-C001",
                "source_id": "S1",
                "source_revision_id": "S1-R1",
                "ordinal": 1,
                "boundary_mode": "line",
                "source_sha256": self.source_sha256,
                "source_line_count": 2,
                "line_start": 1,
                "line_end": 2,
                "content_line_start": 1,
                "content_line_end": 2,
                "overlap_line_count": 0,
                "chunk_sha256": self.chunk_sha256,
                "content_sha256": self.chunk_sha256,
                "text": self.chunk_text,
            }
        ]
        self.notes = [
            {
                "schema_version": 3,
                "chunk_id": "S1-R1-C001",
                "status": "distilled",
                "gist": "Alpha and beta.",
                "propositions": ["Alpha.", "Beta."],
                "evidence_ids": ["E1"],
            }
        ]
        self.evidence = [
            {
                "schema_version": 3,
                "evidence_id": "E1",
                "source_id": "S1",
                "source_revision_id": "S1-R1",
                "chunk_id": "S1-R1-C001",
                "locator": "lines 1-2",
                "statement": "Alpha and beta.",
                "polarity": "supports",
                "duplicate_of": None,
            }
        ]
        self.claims = [
            {
                "schema_version": 3,
                "claim_id": "C1",
                "claim": "The source contains alpha and beta.",
                "claim_kind": "factual",
                "verification_status": "source-only",
                "lifecycle_status": "active",
                "evidence_ids": ["E1"],
                "supporting_source_ids": ["S1"],
                "opposing_source_ids": [],
                "qualifying_source_ids": [],
                "independent_source_ids": ["S1"],
                "verification_refs": [],
                "premise_claim_ids": [],
                "supersedes_claim_ids": [],
                "superseded_by_claim_ids": [],
            }
        ]
        self.coverage = {
            "schema_version": 3,
            "sources": [
                {
                    "source_id": "S1",
                    "source_revision_id": "S1-R1",
                    "planned_chunks": ["S1-R1-C001"],
                    "distilled_chunks": ["S1-R1-C001"],
                    "skipped_chunks": [],
                }
            ],
            "facets": [
                {
                    "facet": "limitations",
                    "status": "covered",
                    "evidence_ids": ["E1"],
                }
            ],
            "risk_checks": [
                {
                    "risk": "boundary",
                    "status": "pass",
                    "reviewed_chunks": ["S1-R1-C001"],
                }
            ],
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_bundle(self):
        (self.root / "run-manifest.json").write_text(
            json.dumps(self.manifest, sort_keys=True),
            encoding="utf-8",
        )
        write_jsonl(self.root / "sources.jsonl", self.sources)
        write_jsonl(self.root / "chunks.jsonl", self.chunks)
        write_jsonl(self.root / "chunk-notes.jsonl", self.notes)
        write_jsonl(self.root / "evidence.jsonl", self.evidence)
        write_jsonl(self.root / "claims.jsonl", self.claims)
        (self.root / "coverage.json").write_text(
            json.dumps(self.coverage, sort_keys=True),
            encoding="utf-8",
        )

    def audit(self):
        self.write_bundle()
        return audit_module.audit_bundle(self.root)

    def assert_structure_failure(self, receipt, text: str | None = None):
        self.assertEqual(receipt["structure_status"], "fail", receipt)
        self.assertFalse(
            any("internal audit failure" in error for error in receipt["errors"]),
            receipt,
        )
        if text:
            self.assertTrue(
                any(text in error for error in receipt["errors"]),
                receipt,
            )

    def test_valid_v3_bundle_passes_structure_and_readiness(self):
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "pass", receipt)
        self.assertEqual(receipt["schema_version"], 3)

    def test_unsupported_schema_and_hash_count_skew_fail(self):
        self.chunks[0]["schema_version"] = 999
        self.chunks[0]["source_sha256"] = "0" * 64
        self.chunks[0]["source_line_count"] = 999
        receipt = self.audit()
        self.assert_structure_failure(receipt, "unsupported schema_version")
        self.assertTrue(
            any("source_sha256 does not match" in error for error in receipt["errors"])
        )
        self.assertTrue(
            any("source_line_count does not match" in error for error in receipt["errors"])
        )

    def test_source_ref_bytes_bind_source_hash(self):
        (self.root / "inputs" / "source.txt").write_text(
            "changed\nbeta\n",
            encoding="utf-8",
        )
        receipt = self.audit()
        self.assert_structure_failure(receipt, "source_sha256 does not match source_ref")

    def test_chunk_text_must_match_registered_source_slice(self):
        fabricated = "fabricated\ncontent"
        self.chunks[0]["text"] = fabricated
        self.chunks[0]["chunk_sha256"] = sha256_text(fabricated)
        self.chunks[0]["content_sha256"] = sha256_text(fabricated)
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "text does not match registered source lines",
        )

    def test_chunk_text_line_count_must_match_declared_range(self):
        self.chunks[0]["text"] = "alpha"
        self.chunks[0]["chunk_sha256"] = sha256_text("alpha")
        self.chunks[0]["content_sha256"] = sha256_text("alpha")
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "text line count does not match loaded line range",
        )

    def test_source_binding_preserves_trailing_spaces_and_tabs(self):
        source_text = "alpha  \nbeta\t\n"
        source_hash = sha256_text(source_text)
        chunk_text = "alpha  \nbeta\t"
        chunk_hash = sha256_text(chunk_text)
        (self.root / "inputs" / "source.txt").write_text(
            source_text,
            encoding="utf-8",
        )
        self.sources[0].update(
            revision=f"sha256:{source_hash}",
            source_sha256=source_hash,
        )
        self.chunks[0].update(
            source_sha256=source_hash,
            chunk_sha256=chunk_hash,
            content_sha256=chunk_hash,
            text=chunk_text,
        )

        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "pass", receipt)

    def test_unknown_coverage_mode_fails_closed(self):
        self.sources[0]["coverage_mode"] = "contigous-lines"
        self.sources[0]["line_count"] = 999
        receipt = self.audit()
        self.assert_structure_failure(receipt, "coverage_mode must be one of")

    def test_local_source_ref_must_remain_inside_bundle(self):
        self.sources[0]["source_ref"] = "../outside.txt"
        receipt = self.audit()
        self.assert_structure_failure(receipt, "path escapes the bundle")

    def test_missing_local_source_ref_blocks_readiness_only(self):
        self.sources[0]["source_ref"] = "inputs/missing.txt"
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(
            any(
                "local source_ref does not exist" in error
                for error in receipt["readiness_errors"]
            ),
            receipt,
        )

    def test_external_source_ref_is_explicitly_unverified(self):
        self.sources[0]["source_ref"] = "https://example.test/source.txt"
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "pass", receipt)
        self.assertTrue(
            any(
                "external source_ref bytes were not locally verified" in warning
                for warning in receipt["warnings"]
            ),
            receipt,
        )

    def test_line_locator_must_be_inside_source_and_chunk(self):
        self.evidence[0]["locator"] = "lines 12-13"
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "locator line range exceeds source line_count",
        )

    def test_boolean_line_ranges_fail(self):
        self.chunks[0].update(
            line_start=True,
            line_end=True,
            content_line_start=True,
            content_line_end=True,
            overlap_line_count=False,
        )
        receipt = self.audit()
        self.assert_structure_failure(receipt, "must be an integer")

    def test_skipped_note_cannot_own_claim_evidence(self):
        self.notes[0] = {
            "schema_version": 3,
            "chunk_id": "S1-R1-C001",
            "status": "skipped",
            "skip_reason": "duplicate appendix",
            "propositions": [],
            "evidence_ids": ["E1"],
        }
        self.coverage["sources"][0]["distilled_chunks"] = []
        self.coverage["sources"][0]["skipped_chunks"] = [
            {
                "chunk_id": "S1-R1-C001",
                "reason": "duplicate appendix",
            }
        ]
        receipt = self.audit()
        self.assert_structure_failure(receipt, "skipped notes cannot own evidence_ids")

    def test_canonical_duplicate_cannot_inflate_claim_or_facet(self):
        alias = copy.deepcopy(self.evidence[0])
        alias["evidence_id"] = "E2"
        alias["duplicate_of"] = "E1"
        self.evidence.append(alias)
        self.notes[0]["evidence_ids"] = ["E1", "E2"]
        self.claims[0]["evidence_ids"] = ["E1", "E2"]
        self.coverage["facets"][0]["evidence_ids"] = ["E1", "E2"]
        receipt = self.audit()
        self.assert_structure_failure(receipt, "repeat one canonical observation")

    def test_opposing_evidence_does_not_count_as_support(self):
        self.evidence[0]["polarity"] = "opposes"
        self.claims[0]["supporting_source_ids"] = ["S1"]
        self.claims[0]["opposing_source_ids"] = []
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "supporting_source_ids do not match supporting evidence",
        )

    def test_disputed_claim_requires_support_and_opposition(self):
        self.claims[0]["verification_status"] = "disputed"
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "disputed needs both supporting and opposing evidence",
        )

    def test_inference_requires_premise_claims(self):
        self.claims[0]["claim_kind"] = "inference"
        self.claims[0]["evidence_ids"] = []
        self.claims[0]["supporting_source_ids"] = []
        self.claims[0]["independent_source_ids"] = []
        receipt = self.audit()
        self.assert_structure_failure(receipt, "inference needs premise_claim_ids")

    def add_second_logical_source(self, *, family_id: str, derived_from: list[str]):
        source_text = "gamma\n"
        (self.root / "inputs" / "second.txt").write_text(
            source_text,
            encoding="utf-8",
        )
        source_sha = sha256_text(source_text)
        chunk_text = "gamma"
        chunk_sha = sha256_text(chunk_text)
        self.sources.append(
            {
                "schema_version": 3,
                "source_id": "S2",
                "source_revision_id": "S2-R1",
                "source_ref": "inputs/second.txt",
                "revision": f"sha256:{source_sha}",
                "source_sha256": source_sha,
                "source_family_id": family_id,
                "derived_from_source_ids": derived_from,
                "accessed_at": "2026-07-26",
                "material_type": "report",
                "locator_scheme": "line",
                "sensitivity": "public",
                "instruction_trust": "data-only",
                "representation_limits": [],
                "coverage_mode": "contiguous-lines",
                "line_count": 1,
            }
        )
        self.chunks.append(
            {
                "schema_version": 3,
                "chunk_id": "S2-R1-C001",
                "source_id": "S2",
                "source_revision_id": "S2-R1",
                "ordinal": 1,
                "boundary_mode": "line",
                "source_sha256": source_sha,
                "source_line_count": 1,
                "line_start": 1,
                "line_end": 1,
                "content_line_start": 1,
                "content_line_end": 1,
                "overlap_line_count": 0,
                "chunk_sha256": chunk_sha,
                "content_sha256": chunk_sha,
                "text": chunk_text,
            }
        )
        self.notes.append(
            {
                "schema_version": 3,
                "chunk_id": "S2-R1-C001",
                "status": "distilled",
                "gist": "Gamma.",
                "propositions": ["Gamma."],
                "evidence_ids": ["E2"],
            }
        )
        self.evidence.append(
            {
                "schema_version": 3,
                "evidence_id": "E2",
                "source_id": "S2",
                "source_revision_id": "S2-R1",
                "chunk_id": "S2-R1-C001",
                "locator": "line 1",
                "statement": "Gamma.",
                "polarity": "supports",
                "duplicate_of": None,
            }
        )
        self.claims[0]["evidence_ids"].append("E2")
        self.claims[0]["supporting_source_ids"].append("S2")
        self.claims[0]["independent_source_ids"].append("S2")
        self.coverage["sources"].append(
            {
                "source_id": "S2",
                "source_revision_id": "S2-R1",
                "planned_chunks": ["S2-R1-C001"],
                "distilled_chunks": ["S2-R1-C001"],
                "skipped_chunks": [],
            }
        )
        self.manifest["handoff"]["source_revision_ids"].append("S2-R1")

    def test_same_family_sources_are_not_independent(self):
        self.add_second_logical_source(family_id="F1", derived_from=[])
        receipt = self.audit()
        self.assert_structure_failure(receipt, "share source_family_id")

    def test_derived_sources_are_not_independent(self):
        self.add_second_logical_source(family_id="F2", derived_from=["S1"])
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "independent sources cannot derive from each other",
        )

    def test_multiple_revisions_and_reciprocal_supersession_pass(self):
        source_text = "alpha corrected\nbeta\n"
        (self.root / "inputs" / "source-v2.txt").write_text(
            source_text,
            encoding="utf-8",
        )
        source_sha = sha256_text(source_text)
        chunk_text = "alpha corrected\nbeta"
        chunk_sha = sha256_text(chunk_text)
        self.sources.append(
            {
                **copy.deepcopy(self.sources[0]),
                "source_revision_id": "S1-R2",
                "source_ref": "inputs/source-v2.txt",
                "revision": f"sha256:{source_sha}",
                "source_sha256": source_sha,
            }
        )
        self.chunks.append(
            {
                **copy.deepcopy(self.chunks[0]),
                "chunk_id": "S1-R2-C001",
                "source_revision_id": "S1-R2",
                "source_sha256": source_sha,
                "chunk_sha256": chunk_sha,
                "content_sha256": chunk_sha,
                "text": chunk_text,
            }
        )
        self.notes.append(
            {
                "schema_version": 3,
                "chunk_id": "S1-R2-C001",
                "status": "distilled",
                "gist": "Alpha was corrected; beta remains.",
                "propositions": ["Alpha was corrected.", "Beta remains."],
                "evidence_ids": ["E2"],
            }
        )
        self.evidence.append(
            {
                "schema_version": 3,
                "evidence_id": "E2",
                "source_id": "S1",
                "source_revision_id": "S1-R2",
                "chunk_id": "S1-R2-C001",
                "locator": "lines 1-2",
                "statement": "Alpha corrected and beta.",
                "polarity": "supports",
                "duplicate_of": None,
            }
        )
        self.claims[0]["lifecycle_status"] = "superseded"
        self.claims[0]["superseded_by_claim_ids"] = ["C2"]
        replacement = copy.deepcopy(self.claims[0])
        replacement.update(
            {
                "claim_id": "C2",
                "claim": "The corrected source contains corrected alpha and beta.",
                "lifecycle_status": "active",
                "evidence_ids": ["E2"],
                "supersedes_claim_ids": ["C1"],
                "superseded_by_claim_ids": [],
            }
        )
        self.claims.append(replacement)
        self.coverage["sources"].append(
            {
                "source_id": "S1",
                "source_revision_id": "S1-R2",
                "planned_chunks": ["S1-R2-C001"],
                "distilled_chunks": ["S1-R2-C001"],
                "skipped_chunks": [],
            }
        )
        self.manifest["handoff"]["source_revision_ids"].append("S1-R2")
        self.manifest["handoff"]["key_claim_ids"] = ["C2"]
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "pass", receipt)

    def test_supersession_without_changed_revision_fails(self):
        self.claims[0]["lifecycle_status"] = "superseded"
        self.claims[0]["superseded_by_claim_ids"] = ["C2"]
        replacement = copy.deepcopy(self.claims[0])
        replacement.update(
            {
                "claim_id": "C2",
                "lifecycle_status": "active",
                "supersedes_claim_ids": ["C1"],
                "superseded_by_claim_ids": [],
            }
        )
        self.claims.append(replacement)
        self.manifest["handoff"]["key_claim_ids"] = ["C2"]
        receipt = self.audit()
        self.assert_structure_failure(
            receipt,
            "supersession must be supported by a changed revision",
        )

    def test_readiness_failures_do_not_become_structure_failures(self):
        self.coverage["facets"][0] = {
            "facet": "limitations",
            "status": "unresolved",
            "evidence_ids": [],
            "reason": "not adjudicated",
        }
        self.coverage["risk_checks"][0]["status"] = "fail"
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(receipt["readiness_errors"])

    def test_heading_only_markdown_fails_readiness(self):
        for name in ("run-manifest.md", "synthesis.md", "handoff.md"):
            (self.root / name).write_text(f"# {name}\n", encoding="utf-8")
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(
            any("substantive content" in error for error in receipt["readiness_errors"])
        )

    def test_all_skipped_fails_readiness(self):
        self.notes[0] = {
            "schema_version": 3,
            "chunk_id": "S1-R1-C001",
            "status": "skipped",
            "skip_reason": "No relevant material.",
            "propositions": [],
            "evidence_ids": [],
        }
        self.evidence = []
        self.claims = []
        self.coverage["sources"][0]["distilled_chunks"] = []
        self.coverage["sources"][0]["skipped_chunks"] = [
            {
                "chunk_id": "S1-R1-C001",
                "reason": "No relevant material.",
            }
        ]
        self.coverage["facets"][0] = {
            "facet": "limitations",
            "status": "absent",
            "evidence_ids": [],
            "search_note": "No material claim found.",
        }
        self.coverage["risk_checks"][0]["status"] = "not-applicable"
        self.coverage["risk_checks"][0]["reviewed_chunks"] = []
        self.coverage["risk_checks"][0]["reason"] = "No material content."
        self.manifest["handoff"]["key_claim_ids"] = []
        receipt = self.audit()
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(
            any("all-skipped" in error for error in receipt["readiness_errors"])
        )

    def test_malformed_public_types_never_raise(self):
        mutations = [
            lambda: self.notes[0].update(status=["distilled"]),
            lambda: self.claims[0].update(verification_status=["source-only"]),
            lambda: self.coverage["risk_checks"][0].update(status=["pass"]),
            lambda: self.evidence[0].update(duplicate_of=["E0"]),
            lambda: self.evidence[0].update(source_id=["S1"]),
            lambda: self.evidence[0].update(chunk_id={"bad": "shape"}),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                mutate()
                receipt = self.audit()
                self.assert_structure_failure(receipt)
                self.tearDown()
                self.setUp()

    def test_invalid_utf8_returns_machine_readable_failure(self):
        self.write_bundle()
        (self.root / "sources.jsonl").write_bytes(b"\xff\n")
        receipt = audit_module.audit_bundle(self.root)
        self.assert_structure_failure(receipt, "invalid UTF-8")

    def test_duplicate_json_keys_fail_before_schema_validation(self):
        self.write_bundle()
        sources_path = self.root / "sources.jsonl"
        sources_path.write_text(
            sources_path.read_text(encoding="utf-8").replace(
                '"source_id": "S1"',
                '"source_id": "S1", "source_id": "S2"',
                1,
            ),
            encoding="utf-8",
        )
        receipt = audit_module.audit_bundle(self.root)
        self.assert_structure_failure(receipt, "duplicate key 'source_id'")
        self.assertEqual(len(receipt["errors"]), 1, receipt)

    def test_nonfinite_json_numbers_fail_before_schema_validation(self):
        self.write_bundle()
        coverage_path = self.root / "coverage.json"
        coverage_path.write_text(
            coverage_path.read_text(encoding="utf-8")[:-1]
            + ', "nonstandard": NaN}',
            encoding="utf-8",
        )
        receipt = audit_module.audit_bundle(self.root)
        self.assert_structure_failure(receipt, "non-finite number NaN")

    def test_required_semantic_receipt_remains_externally_pending(self):
        self.manifest["semantic_evaluation_required"] = True
        self.manifest["semantic_evaluation_receipt"] = "semantic-receipt.json"
        self.write_bundle()
        missing_receipt = audit_module.audit_bundle(self.root)
        self.assertEqual(missing_receipt["structure_status"], "pass", missing_receipt)
        self.assertEqual(missing_receipt["readiness_status"], "fail", missing_receipt)

        (self.root / "semantic-receipt.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "status": "pass",
                    "cases": {"task-specific-forward-test": {"status": "pass"}},
                    "proof_boundary": "Self-attested test metadata.",
                }
            ),
            encoding="utf-8",
        )
        receipt = audit_module.audit_bundle(self.root)
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(
            any(
                "trusted external adjudication" in error
                for error in receipt["readiness_errors"]
            ),
            receipt,
        )
        self.assertTrue(
            any(
                "self-attested metadata" in warning
                for warning in receipt["warnings"]
            ),
            receipt,
        )

    def test_fake_semantic_receipt_cannot_satisfy_readiness(self):
        self.manifest["semantic_evaluation_required"] = True
        self.manifest["semantic_evaluation_receipt"] = "semantic-receipt.json"
        self.write_bundle()
        (self.root / "semantic-receipt.json").write_text(
            "not a semantic receipt\n",
            encoding="utf-8",
        )
        receipt = audit_module.audit_bundle(self.root)
        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "fail", receipt)
        self.assertTrue(
            any(
                "semantic evaluation receipt is not valid JSON" in error
                for error in receipt["readiness_errors"]
            ),
            receipt,
        )

    def test_invalid_bundle_root_returns_one_actionable_error(self):
        receipt = audit_module.audit_bundle(self.root / "missing")
        self.assertEqual(receipt["structure_status"], "fail", receipt)
        self.assertEqual(
            receipt["errors"],
            ["bundle path must be an existing directory"],
        )
        self.assertEqual(receipt["warnings"], [])

    def test_require_ready_cli_distinguishes_readiness(self):
        self.coverage["risk_checks"][0]["status"] = "fail"
        self.write_bundle()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(self.root),
                "--require-ready",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=self.root.parent,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        receipt = json.loads(result.stdout)
        self.assertEqual(receipt["structure_status"], "pass")
        self.assertEqual(receipt["readiness_status"], "fail")


if __name__ == "__main__":
    unittest.main()
