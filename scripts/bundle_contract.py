"""Shared constants for autonomous source distillation bundle producers and auditors."""

from __future__ import annotations

import re


BUNDLE_SCHEMA_VERSION = 3
LEGACY_SCHEMA_VERSION = 2
MANIFEST_FILE = "run-manifest.json"

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_ROUTES = {"direct", "light", "serious"}
ALLOWED_COVERAGE_MODES = {"contiguous-lines"}
ALLOWED_CLAIM_KINDS = {"factual", "inference"}
ALLOWED_VERIFICATION_STATUSES = {
    "source-only",
    "externally-verified",
    "uncertain",
    "disputed",
}
ALLOWED_LIFECYCLE_STATUSES = {"active", "superseded"}
ALLOWED_LEGACY_CLAIM_STATUSES = {
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
ALLOWED_NOTE_STATUSES = {"distilled", "skipped"}

REQUIRED_TEXT_FILES = ("run-manifest.md", "synthesis.md", "handoff.md")
REQUIRED_MACHINE_FILES = (
    MANIFEST_FILE,
    "sources.jsonl",
    "chunks.jsonl",
    "chunk-notes.jsonl",
    "evidence.jsonl",
    "claims.jsonl",
    "coverage.json",
)
