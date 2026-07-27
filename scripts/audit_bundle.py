#!/usr/bin/env python3
"""Audit a structured autonomous source distillation bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bundle_contract import (  # noqa: E402
    ALLOWED_CLAIM_KINDS,
    ALLOWED_COVERAGE_MODES,
    ALLOWED_EVIDENCE_POLARITIES,
    ALLOWED_FACET_STATUSES,
    ALLOWED_LEGACY_CLAIM_STATUSES,
    ALLOWED_LIFECYCLE_STATUSES,
    ALLOWED_NOTE_STATUSES,
    ALLOWED_RISK_STATUSES,
    ALLOWED_ROUTES,
    ALLOWED_VERIFICATION_STATUSES,
    BUNDLE_SCHEMA_VERSION,
    ID_RE,
    MANIFEST_FILE,
    REQUIRED_MACHINE_FILES,
    REQUIRED_TEXT_FILES,
    SHA256_RE,
)
from locator_utils import parse_line_ranges  # noqa: E402


class AuditState:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.readiness_errors: list[str] = []
        self.warnings: list[str] = []


class StrictJsonError(ValueError):
    """Raised when input uses a JSON shape that Python otherwise accepts loosely."""


def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise StrictJsonError(f"duplicate key {key!r}")
        value[key] = item
    return value


def reject_nonfinite_number(value: str) -> None:
    raise StrictJsonError(f"non-finite number {value}")


def strict_json_loads(text: str) -> Any:
    return json.loads(
        text,
        object_pairs_hook=reject_duplicate_keys,
        parse_constant=reject_nonfinite_number,
    )


def read_text(path: Path, errors: list[str], *, required: bool = True) -> str | None:
    if not path.is_file():
        if required:
            errors.append(f"missing file: {path.name}")
        return None
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError:
        errors.append(f"{path.name}: invalid UTF-8")
    except OSError as exc:
        errors.append(f"{path.name}: cannot read file: {exc.strerror or type(exc).__name__}")
    return None


def load_jsonl(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    text = read_text(path, errors)
    if text is None:
        return []
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            value = strict_json_loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc.msg}")
            continue
        except StrictJsonError as exc:
            errors.append(f"{path.name}:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.name}:{line_number}: row must be an object")
            continue
        rows.append(value)
    return rows


def load_json(
    path: Path,
    errors: list[str],
    *,
    required: bool = True,
) -> dict[str, Any]:
    text = read_text(path, errors, required=required)
    if text is None:
        return {}
    try:
        value = strict_json_loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON: {exc.msg}")
        return {}
    except StrictJsonError as exc:
        errors.append(f"{path.name}: invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name}: root must be an object")
        return {}
    return value


def require_string(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
) -> str:
    value = row.get(field_name)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {field_name} must be a non-empty string")
        return ""
    return value


def optional_string(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
) -> str | None:
    value = row.get(field_name)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}: {field_name} must be null or a non-empty string")
        return None
    return value


def require_identifier(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
) -> str:
    value = require_string(row, field_name, label, errors)
    if value and not ID_RE.fullmatch(value):
        errors.append(f"{label}: {field_name} has an invalid identifier format")
        return ""
    return value


def require_string_list(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
    *,
    unique: bool = False,
) -> list[str]:
    value = row.get(field_name)
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{label}: {field_name} must be a list of non-empty strings")
        return []
    result = list(value)
    if unique and len(result) != len(set(result)):
        errors.append(f"{label}: {field_name} must be unique")
    return result


def optional_string_list(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
    *,
    unique: bool = False,
) -> list[str]:
    if field_name not in row:
        return []
    return require_string_list(
        row,
        field_name,
        label,
        errors,
        unique=unique,
    )


def require_integer(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
    *,
    minimum: int | None = None,
) -> int | None:
    value = row.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        errors.append(f"{label}: {field_name} must be an integer")
        return None
    if minimum is not None and value < minimum:
        errors.append(f"{label}: {field_name} must be at least {minimum}")
        return None
    return value


def optional_boolean(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
    *,
    default: bool = False,
) -> bool:
    if field_name not in row:
        return default
    value = row.get(field_name)
    if not isinstance(value, bool):
        errors.append(f"{label}: {field_name} must be a boolean")
        return default
    return value


def require_enum(
    row: dict[str, Any],
    field_name: str,
    allowed: set[str],
    label: str,
    errors: list[str],
) -> str:
    value = require_string(row, field_name, label, errors)
    if value and value not in allowed:
        errors.append(
            f"{label}: {field_name} must be one of {', '.join(sorted(allowed))}"
        )
        return ""
    return value


def require_schema_version(
    row: dict[str, Any],
    label: str,
    errors: list[str],
) -> None:
    value = require_integer(row, "schema_version", label, errors, minimum=1)
    if value is not None and value != BUNDLE_SCHEMA_VERSION:
        errors.append(
            f"{label}: unsupported schema_version {value}; "
            f"expected {BUNDLE_SCHEMA_VERSION}"
        )


def require_sha256(
    row: dict[str, Any],
    field_name: str,
    label: str,
    errors: list[str],
) -> str:
    value = require_string(row, field_name, label, errors)
    if value and not SHA256_RE.fullmatch(value):
        errors.append(f"{label}: {field_name} must be 64 lowercase hex characters")
        return ""
    return value


def index_rows(
    rows: list[dict[str, Any]],
    field_name: str,
    file_name: str,
    errors: list[str],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        label = f"{file_name}:{position}"
        row_id = require_identifier(row, field_name, label, errors)
        if not row_id:
            continue
        if row_id in result:
            errors.append(f"{label}: duplicate {field_name} {row_id}")
            continue
        result[row_id] = row
    return result


def has_substantive_markdown(text: str) -> bool:
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped in {"---", "```"}:
            continue
        return True
    return False


def safe_bundle_path(
    workdir: Path,
    relative_path: str,
    label: str,
    errors: list[str],
) -> Path | None:
    path = Path(relative_path)
    if path.is_absolute():
        errors.append(f"{label}: path must be relative to the bundle")
        return None
    try:
        root = workdir.resolve()
        resolved = (root / path).resolve()
        resolved.relative_to(root)
    except (OSError, ValueError):
        errors.append(f"{label}: path escapes the bundle")
        return None
    return resolved


def canonical_bundle_digest(
    workdir: Path,
    source_catalog: dict[str, dict[str, Any]],
    errors: list[str],
) -> str:
    paths = {
        workdir / file_name
        for file_name in (*REQUIRED_MACHINE_FILES, *REQUIRED_TEXT_FILES)
    }
    for source in source_catalog["revisions"].values():
        source_ref = source.get("source_ref")
        if not isinstance(source_ref, str):
            continue
        parsed = urlsplit(source_ref)
        if parsed.scheme:
            continue
        try:
            candidate = (workdir / source_ref).resolve()
            candidate.relative_to(workdir.resolve())
        except (OSError, ValueError):
            continue
        paths.add(candidate)

    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda candidate: str(candidate)):
        if not path.is_file():
            continue
        try:
            relative = path.relative_to(workdir).as_posix()
            payload = path.read_bytes()
        except (OSError, ValueError) as exc:
            errors.append(
                f"bundle digest cannot read {path.name}: "
                f"{getattr(exc, 'strerror', None) or type(exc).__name__}"
            )
            continue
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def audit_manifest(
    manifest: dict[str, Any],
    state: AuditState,
) -> dict[str, Any]:
    label = MANIFEST_FILE
    require_schema_version(manifest, label, state.errors)
    route = require_enum(manifest, "route", ALLOWED_ROUTES, label, state.errors)
    require_string(manifest, "objective", label, state.errors)
    require_string(manifest, "output_mode", label, state.errors)
    require_enum(
        manifest,
        "acceptable_loss",
        {"low", "medium", "high"},
        label,
        state.errors,
    )
    require_string(manifest, "completion_oracle", label, state.errors)
    required_facets = require_string_list(
        manifest,
        "required_facets",
        label,
        state.errors,
        unique=True,
    )
    required_risks = require_string_list(
        manifest,
        "required_risks",
        label,
        state.errors,
        unique=True,
    )
    allow_empty_result = optional_boolean(
        manifest,
        "allow_empty_result",
        label,
        state.errors,
    )
    if allow_empty_result:
        require_string(manifest, "empty_result_reason", label, state.errors)
    semantic_required = optional_boolean(
        manifest,
        "semantic_evaluation_required",
        label,
        state.errors,
    )
    semantic_receipt = optional_string(
        manifest,
        "semantic_evaluation_receipt",
        label,
        state.errors,
    )
    if semantic_required and not semantic_receipt:
        state.readiness_errors.append(
            f"{label}: semantic evaluation is required but no receipt path is declared"
        )
    if semantic_required:
        state.readiness_errors.append(
            f"{label}: semantic evaluation requires trusted external adjudication; "
            "a local receipt cannot satisfy deterministic readiness"
        )

    handoff = manifest.get("handoff")
    if not isinstance(handoff, dict):
        state.errors.append(f"{label}: handoff must be an object")
        handoff = {}
    source_revision_ids = require_string_list(
        handoff,
        "source_revision_ids",
        f"{label} handoff",
        state.errors,
        unique=True,
    )
    key_claim_ids = require_string_list(
        handoff,
        "key_claim_ids",
        f"{label} handoff",
        state.errors,
        unique=True,
    )
    reload_paths = require_string_list(
        handoff,
        "reload_paths",
        f"{label} handoff",
        state.errors,
        unique=True,
    )
    unresolved_gaps = require_string_list(
        handoff,
        "unresolved_gaps",
        f"{label} handoff",
        state.errors,
    )
    safe_to_drop = require_string_list(
        handoff,
        "safe_to_drop",
        f"{label} handoff",
        state.errors,
        unique=True,
    )
    if route == "serious" and not reload_paths:
        state.readiness_errors.append(f"{label}: serious route needs handoff reload_paths")

    return {
        "route": route,
        "required_facets": required_facets,
        "required_risks": required_risks,
        "allow_empty_result": allow_empty_result,
        "semantic_required": semantic_required,
        "semantic_receipt": semantic_receipt,
        "handoff_source_revision_ids": source_revision_ids,
        "handoff_key_claim_ids": key_claim_ids,
        "reload_paths": reload_paths,
        "unresolved_gaps": unresolved_gaps,
        "safe_to_drop": safe_to_drop,
    }


def audit_sources(
    rows: list[dict[str, Any]],
    workdir: Path,
    strict_v3: bool,
    state: AuditState,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    index_field = "source_revision_id" if strict_v3 else "source_id"
    indexed_rows = index_rows(rows, index_field, "sources.jsonl", state.errors)
    revisions: dict[str, dict[str, Any]] = {}
    logical_sources: dict[str, dict[str, Any]] = {}

    for row_key, row in indexed_rows.items():
        source_id = (
            require_identifier(row, "source_id", f"source revision {row_key}", state.errors)
            if strict_v3
            else row_key
        )
        label = (
            f"source revision {row_key}"
            if strict_v3
            else f"source {source_id}"
        )
        if strict_v3:
            require_schema_version(row, label, state.errors)
        source_ref = require_string(row, "source_ref", label, state.errors)
        revision = require_string(row, "revision", label, state.errors)
        material_type = require_string(row, "material_type", label, state.errors)
        locator_scheme = require_string(row, "locator_scheme", label, state.errors)
        instruction_trust = require_string(
            row,
            "instruction_trust",
            label,
            state.errors,
        )
        if instruction_trust and instruction_trust != "data-only":
            state.errors.append(f"{label}: instruction_trust must be data-only")
        limits = row.get("representation_limits")
        if not isinstance(limits, list) or any(
            not isinstance(item, str) for item in limits
        ):
            state.errors.append(
                f"{label}: representation_limits must be a list of strings"
            )

        coverage_mode = (
            require_enum(
                row,
                "coverage_mode",
                ALLOWED_COVERAGE_MODES,
                label,
                state.errors,
            )
            if strict_v3
            else optional_string(
                row,
                "coverage_mode",
                label,
                state.errors,
            )
        )
        line_count: int | None = None
        if coverage_mode == "contiguous-lines":
            line_count = require_integer(
                row,
                "line_count",
                label,
                state.errors,
                minimum=0,
            )

        source_revision_id = ""
        source_sha256 = ""
        source_family_id = source_id
        derived_from_source_ids: list[str] = []
        source_lines: list[str] | None = None
        if strict_v3:
            source_revision_id = row_key
            source_sha256 = require_sha256(
                row,
                "source_sha256",
                label,
                state.errors,
            )
            source_family_id = require_identifier(
                row,
                "source_family_id",
                label,
                state.errors,
            )
            derived_from_source_ids = require_string_list(
                row,
                "derived_from_source_ids",
                label,
                state.errors,
                unique=True,
            )
            require_string(row, "accessed_at", label, state.errors)
            require_string(row, "sensitivity", label, state.errors)
            if source_id in derived_from_source_ids:
                state.errors.append(
                    f"{label}: derived_from_source_ids cannot contain itself"
                )
            if source_sha256 and revision != f"sha256:{source_sha256}":
                state.errors.append(
                    f"{label}: revision must equal sha256:<source_sha256>"
                )

            if source_ref:
                parsed_ref = urlsplit(source_ref)
                is_external_url = (
                    parsed_ref.scheme in {"http", "https"}
                    and bool(parsed_ref.netloc)
                )
                if parsed_ref.scheme and not is_external_url:
                    state.errors.append(
                        f"{label}: source_ref uses an unsupported or nonportable scheme"
                    )
                    local_source = None
                elif is_external_url:
                    state.warnings.append(
                        f"{label}: external source_ref bytes were not locally verified"
                    )
                    local_source = None
                else:
                    local_source = safe_bundle_path(
                        workdir,
                        source_ref,
                        f"{label} source_ref",
                        state.errors,
                    )
                if local_source is not None and not local_source.exists():
                    state.readiness_errors.append(
                        f"{label}: local source_ref does not exist"
                    )
                elif local_source is not None and not local_source.is_file():
                    state.errors.append(f"{label}: local source_ref must be a file")
                elif local_source is not None:
                    try:
                        source_bytes = local_source.read_bytes()
                        source_text = source_bytes.decode("utf-8")
                    except UnicodeError:
                        state.errors.append(f"{label}: source_ref is not valid UTF-8")
                    except OSError as exc:
                        state.errors.append(
                            f"{label}: cannot read source_ref: "
                            f"{exc.strerror or type(exc).__name__}"
                        )
                    else:
                        source_lines = source_text.splitlines()
                        observed_sha256 = hashlib.sha256(source_bytes).hexdigest()
                        if source_sha256 and observed_sha256 != source_sha256:
                            state.errors.append(
                                f"{label}: source_sha256 does not match source_ref bytes"
                            )
                        if (
                            coverage_mode == "contiguous-lines"
                            and line_count is not None
                            and len(source_lines) != line_count
                        ):
                            state.errors.append(
                                f"{label}: line_count does not match source_ref"
                            )

        normalized_revision = {
            "source_id": source_id,
            "source_ref": source_ref,
            "revision": revision,
            "material_type": material_type,
            "locator_scheme": locator_scheme,
            "coverage_mode": coverage_mode,
            "line_count": line_count,
            "source_revision_id": source_revision_id,
            "source_sha256": source_sha256,
            "source_family_id": source_family_id,
            "derived_from_source_ids": derived_from_source_ids,
            "source_lines": source_lines,
        }
        revision_key = source_revision_id if strict_v3 else source_id
        revisions[revision_key] = normalized_revision

        existing = logical_sources.get(source_id)
        if existing is None:
            if strict_v3:
                logical_sources[source_id] = {
                    "source_id": source_id,
                    "source_family_id": source_family_id,
                    "derived_from_source_ids": derived_from_source_ids,
                    "revision_ids": [revision_key],
                }
            else:
                logical_sources[source_id] = normalized_revision
        else:
            existing["revision_ids"].append(revision_key)
            if strict_v3 and (
                existing["source_family_id"] != source_family_id
                or existing["derived_from_source_ids"] != derived_from_source_ids
            ):
                state.errors.append(
                    f"{label}: source family and derivation must remain stable "
                    "across revisions"
                )

    if strict_v3:
        for source_id, source in logical_sources.items():
            for parent_id in source["derived_from_source_ids"]:
                if parent_id not in logical_sources:
                    state.errors.append(
                        f"source {source_id}: unknown derived source {parent_id}"
                    )
        detect_graph_cycles(
            {
                source_id: source["derived_from_source_ids"]
                for source_id, source in logical_sources.items()
            },
            "source derivation",
            state.errors,
        )

    return indexed_rows, {
        "revisions": revisions,
        "logical": logical_sources,
    }


def audit_chunks(
    rows: list[dict[str, Any]],
    source_catalog: dict[str, dict[str, Any]],
    strict_v3: bool,
    state: AuditState,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    chunks = index_rows(rows, "chunk_id", "chunks.jsonl", state.errors)
    normalized: dict[str, dict[str, Any]] = {}
    by_source: dict[str, list[dict[str, Any]]] = {}
    revisions = source_catalog["revisions"]
    logical_sources = source_catalog["logical"]

    for chunk_id, row in chunks.items():
        label = f"chunk {chunk_id}"
        if strict_v3:
            require_schema_version(row, label, state.errors)
        source_id = require_identifier(row, "source_id", label, state.errors)
        source_revision_id = ""
        if strict_v3:
            source_revision_id = require_identifier(
                row,
                "source_revision_id",
                label,
                state.errors,
            )
            source = revisions.get(source_revision_id)
            if source_revision_id and source is None:
                state.errors.append(
                    f"{label}: unknown source_revision_id {source_revision_id}"
                )
            elif source and source["source_id"] != source_id:
                state.errors.append(
                    f"{label}: source_id does not match source revision"
                )
        else:
            source = logical_sources.get(source_id)
            if source_id and source is None:
                state.errors.append(f"{label}: unknown source_id {source_id}")
        ordinal = require_integer(
            row,
            "ordinal",
            label,
            state.errors,
            minimum=1,
        )

        content_start = require_integer(
            row,
            "content_line_start",
            label,
            state.errors,
            minimum=1,
        )
        content_end = require_integer(
            row,
            "content_line_end",
            label,
            state.errors,
            minimum=1,
        )
        loaded_start = require_integer(
            row,
            "line_start",
            label,
            state.errors,
            minimum=1,
        )
        loaded_end = require_integer(
            row,
            "line_end",
            label,
            state.errors,
            minimum=1,
        )
        overlap_count = require_integer(
            row,
            "overlap_line_count",
            label,
            state.errors,
            minimum=0,
        )
        if (
            content_start is not None
            and content_end is not None
            and content_end < content_start
        ):
            state.errors.append(f"{label}: invalid unique-content line range")
        if (
            loaded_start is not None
            and loaded_end is not None
            and loaded_end < loaded_start
        ):
            state.errors.append(f"{label}: invalid loaded line range")
        if (
            loaded_start is not None
            and content_start is not None
            and content_start < loaded_start
        ):
            state.errors.append(f"{label}: invalid loaded line range")
        if (
            loaded_end is not None
            and content_end is not None
            and content_end > loaded_end
        ):
            state.errors.append(f"{label}: invalid loaded line range")
        if (
            overlap_count
            and loaded_start is not None
            and content_start is not None
            and loaded_start >= content_start
        ):
            state.errors.append(
                f"{label}: overlap must precede content_line_start in loaded range"
            )

        source_sha256 = ""
        source_line_count: int | None = None
        if strict_v3:
            source_sha256 = require_sha256(
                row,
                "source_sha256",
                label,
                state.errors,
            )
            source_line_count = require_integer(
                row,
                "source_line_count",
                label,
                state.errors,
                minimum=0,
            )
            chunk_sha256 = require_sha256(
                row,
                "chunk_sha256",
                label,
                state.errors,
            )
            content_sha256 = require_sha256(
                row,
                "content_sha256",
                label,
                state.errors,
            )
            if source:
                if source_sha256 != source["source_sha256"]:
                    state.errors.append(
                        f"{label}: source_sha256 does not match source registry"
                    )
                if (
                    source_line_count is not None
                    and source["line_count"] is not None
                    and source_line_count != source["line_count"]
                ):
                    state.errors.append(
                        f"{label}: source_line_count does not match source registry"
                    )
            text = row.get("text")
            if not isinstance(text, str) or not text:
                state.errors.append(f"{label}: text must be a non-empty string")
            else:
                observed_chunk_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if chunk_sha256 and chunk_sha256 != observed_chunk_hash:
                    state.errors.append(f"{label}: chunk_sha256 does not match text")
                text_lines = text.splitlines()
                valid_ranges = all(
                    isinstance(value, int) and not isinstance(value, bool)
                    for value in (
                        loaded_start,
                        loaded_end,
                        content_start,
                        content_end,
                        overlap_count,
                    )
                )
                if valid_ranges:
                    loaded_line_count = loaded_end - loaded_start + 1
                    unique_line_count = content_end - content_start + 1
                    if len(text_lines) != loaded_line_count:
                        state.errors.append(
                            f"{label}: text line count does not match loaded line range"
                        )
                    if overlap_count != content_start - loaded_start:
                        state.errors.append(
                            f"{label}: overlap_line_count does not match line ranges"
                        )
                    if content_end != loaded_end:
                        state.errors.append(
                            f"{label}: unique content must end at line_end"
                        )
                    if len(text_lines) - overlap_count != unique_line_count:
                        state.errors.append(
                            f"{label}: unique-content line count does not match range"
                        )
                if overlap_count is not None and overlap_count <= len(text_lines):
                    content_text = "\n".join(text_lines[overlap_count:])
                    observed_content_hash = hashlib.sha256(
                        content_text.encode("utf-8")
                    ).hexdigest()
                    if content_sha256 and content_sha256 != observed_content_hash:
                        state.errors.append(
                            f"{label}: content_sha256 does not match unique content"
                        )
                elif overlap_count is not None:
                    state.errors.append(
                        f"{label}: overlap_line_count exceeds loaded text lines"
                    )
                source_lines = source.get("source_lines") if source else None
                if valid_ranges and source_lines is not None:
                    if loaded_end > len(source_lines):
                        state.errors.append(
                            f"{label}: loaded line range exceeds local source"
                        )
                    else:
                        expected_text = "\n".join(
                            source_lines[loaded_start - 1 : loaded_end]
                        )
                        if text != expected_text:
                            state.errors.append(
                                f"{label}: text does not match registered source lines"
                            )
                    if content_end > len(source_lines):
                        state.errors.append(
                            f"{label}: unique-content range exceeds local source"
                        )
                    else:
                        expected_content = "\n".join(
                            source_lines[content_start - 1 : content_end]
                        )
                        expected_content_hash = hashlib.sha256(
                            expected_content.encode("utf-8")
                        ).hexdigest()
                        if content_sha256 != expected_content_hash:
                            state.errors.append(
                                f"{label}: content_sha256 does not match "
                                "registered source lines"
                            )

        normalized[chunk_id] = {
            "chunk_id": chunk_id,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
            "ordinal": ordinal,
            "content_line_start": content_start,
            "content_line_end": content_end,
            "line_start": loaded_start,
            "line_end": loaded_end,
            "overlap_line_count": overlap_count,
            "source_sha256": source_sha256,
            "source_line_count": source_line_count,
        }
        source_key = source_revision_id if strict_v3 else source_id
        if source_key:
            by_source.setdefault(source_key, []).append(normalized[chunk_id])

    for source_key, source_chunks in by_source.items():
        source = (
            revisions.get(source_key, {})
            if strict_v3
            else logical_sources.get(source_key, {})
        )
        source_label = (
            f"source revision {source_key}"
            if strict_v3
            else f"source {source_key}"
        )
        ordinals = sorted(
            row["ordinal"]
            for row in source_chunks
            if isinstance(row.get("ordinal"), int)
        )
        if ordinals and ordinals != list(range(1, len(ordinals) + 1)):
            state.errors.append(
                f"{source_label}: chunk ordinals must be contiguous from 1"
            )

        if source.get("coverage_mode") != "contiguous-lines":
            continue
        ranged = [
            row
            for row in source_chunks
            if isinstance(row.get("content_line_start"), int)
            and not isinstance(row.get("content_line_start"), bool)
            and isinstance(row.get("content_line_end"), int)
            and not isinstance(row.get("content_line_end"), bool)
        ]
        ranged.sort(key=lambda row: row["content_line_start"])
        if len(ranged) != len(source_chunks):
            state.errors.append(
                f"{source_label}: contiguous-lines coverage requires ranges "
                "on every chunk"
            )
            continue
        expected = 1
        for row in ranged:
            start = row["content_line_start"]
            end = row["content_line_end"]
            if start != expected:
                kind = "overlap" if start < expected else "gap"
                state.errors.append(
                    f"{source_label}: unique-content {kind} before line {start}; "
                    f"expected {expected}"
                )
            expected = max(expected, end + 1)
        line_count = source.get("line_count")
        if (
            isinstance(line_count, int)
            and not isinstance(line_count, bool)
            and expected - 1 != line_count
        ):
            state.errors.append(
                f"{source_label}: unique-content ends at {expected - 1}, "
                f"expected line_count {line_count}"
            )

    return chunks, normalized


def audit_notes(
    rows: list[dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    strict_v3: bool,
    state: AuditState,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    notes = index_rows(rows, "chunk_id", "chunk-notes.jsonl", state.errors)
    normalized: dict[str, dict[str, Any]] = {}
    missing = sorted(set(chunks) - set(notes))
    extra = sorted(set(notes) - set(chunks))
    if missing:
        state.errors.append(f"chunk-notes.jsonl: missing notes for {', '.join(missing)}")
    if extra:
        state.errors.append(
            f"chunk-notes.jsonl: unknown chunk IDs {', '.join(extra)}"
        )

    for chunk_id, row in notes.items():
        label = f"chunk note {chunk_id}"
        if strict_v3:
            require_schema_version(row, label, state.errors)
        status = require_enum(
            row,
            "status",
            ALLOWED_NOTE_STATUSES,
            label,
            state.errors,
        )
        evidence_ids = require_string_list(
            row,
            "evidence_ids",
            label,
            state.errors,
            unique=True,
        )
        propositions = optional_string_list(
            row,
            "propositions",
            label,
            state.errors,
        )
        if status == "distilled":
            require_string(row, "gist", label, state.errors)
        elif status == "skipped":
            require_string(row, "skip_reason", label, state.errors)
            if evidence_ids:
                state.errors.append(
                    f"{label}: skipped notes cannot own evidence_ids"
                )
            if propositions:
                state.errors.append(
                    f"{label}: skipped notes cannot contain propositions"
                )
        normalized[chunk_id] = {
            "chunk_id": chunk_id,
            "status": status,
            "evidence_ids": evidence_ids,
            "skip_reason": (
                row.get("skip_reason")
                if isinstance(row.get("skip_reason"), str)
                else ""
            ),
        }
    return notes, normalized


def audit_evidence(
    rows: list[dict[str, Any]],
    source_catalog: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    strict_v3: bool,
    state: AuditState,
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, str],
]:
    evidence = index_rows(rows, "evidence_id", "evidence.jsonl", state.errors)
    normalized: dict[str, dict[str, Any]] = {}
    revisions = source_catalog["revisions"]
    logical_sources = source_catalog["logical"]

    for evidence_id, row in evidence.items():
        label = f"evidence {evidence_id}"
        if strict_v3:
            require_schema_version(row, label, state.errors)
        source_id = require_identifier(row, "source_id", label, state.errors)
        chunk_id = require_identifier(row, "chunk_id", label, state.errors)
        locator = require_string(row, "locator", label, state.errors)
        require_string(row, "statement", label, state.errors)
        polarity = require_enum(
            row,
            "polarity",
            ALLOWED_EVIDENCE_POLARITIES,
            label,
            state.errors,
        )
        source_revision_id = ""
        if strict_v3:
            source_revision_id = require_identifier(
                row,
                "source_revision_id",
                label,
                state.errors,
            )
        source = logical_sources.get(source_id)
        source_revision = (
            revisions.get(source_revision_id)
            if strict_v3 and source_revision_id
            else None
        )
        chunk = chunks.get(chunk_id)
        if source_id and source is None:
            state.errors.append(f"{label}: unknown source_id {source_id}")
        if strict_v3 and source_revision_id and source_revision is None:
            state.errors.append(
                f"{label}: unknown source_revision_id {source_revision_id}"
            )
        elif strict_v3 and source_revision and source_revision["source_id"] != source_id:
            state.errors.append(
                f"{label}: source_id does not match source revision"
            )
        if chunk_id and chunk is None:
            state.errors.append(f"{label}: unknown chunk_id {chunk_id}")
        elif chunk and chunk.get("source_id") != source_id:
            state.errors.append(f"{label}: source_id does not match its chunk")
        if strict_v3 and chunk and source_revision_id != chunk["source_revision_id"]:
            state.errors.append(
                f"{label}: source_revision_id does not match its chunk"
            )
        if (
            strict_v3
            and locator
            and source_revision
            and "line" in source_revision["locator_scheme"].casefold()
        ):
            line_ranges = parse_line_ranges(locator)
            if not line_ranges:
                state.errors.append(
                    f"{label}: locator must contain an explicit line or line range"
                )
            for start, end in line_ranges:
                if start < 1 or end < start:
                    state.errors.append(f"{label}: locator has an invalid line range")
                    continue
                line_count = source_revision.get("line_count")
                if isinstance(line_count, int) and end > line_count:
                    state.errors.append(
                        f"{label}: locator line range exceeds source line_count"
                    )
                chunk_start = chunk.get("line_start") if chunk else None
                chunk_end = chunk.get("line_end") if chunk else None
                if (
                    isinstance(chunk_start, int)
                    and not isinstance(chunk_start, bool)
                    and isinstance(chunk_end, int)
                    and not isinstance(chunk_end, bool)
                    and (start < chunk_start or end > chunk_end)
                ):
                    state.errors.append(
                        f"{label}: locator line range falls outside its chunk"
                    )
        duplicate_of = row.get("duplicate_of")
        normalized_duplicate: str | None = None
        if duplicate_of is not None:
            if not isinstance(duplicate_of, str) or not duplicate_of.strip():
                state.errors.append(
                    f"{label}: duplicate_of must be null or a non-empty string"
                )
            elif not ID_RE.fullmatch(duplicate_of):
                state.errors.append(f"{label}: duplicate_of has invalid identifier format")
            else:
                normalized_duplicate = duplicate_of

        normalized[evidence_id] = {
            "evidence_id": evidence_id,
            "source_id": source_id,
            "source_revision_id": source_revision_id,
            "chunk_id": chunk_id,
            "polarity": polarity,
            "duplicate_of": normalized_duplicate,
        }

    for evidence_id, row in normalized.items():
        duplicate_of = row["duplicate_of"]
        if duplicate_of is None:
            continue
        target = normalized.get(duplicate_of)
        if duplicate_of == evidence_id:
            state.errors.append(
                f"evidence {evidence_id}: duplicate_of cannot reference itself"
            )
        elif target is None:
            state.errors.append(
                f"evidence {evidence_id}: unknown duplicate_of {duplicate_of}"
            )
        else:
            if target["source_id"] != row["source_id"]:
                state.errors.append(
                    f"evidence {evidence_id}: duplicate_of must remain within one source"
                )
            if strict_v3 and target["source_revision_id"] != row["source_revision_id"]:
                state.errors.append(
                    f"evidence {evidence_id}: duplicate_of must remain within one revision"
                )
            if target["polarity"] != row["polarity"]:
                state.errors.append(
                    f"evidence {evidence_id}: duplicate_of must preserve polarity"
                )

    roots = canonical_roots(normalized, state.errors)
    return evidence, normalized, roots


def canonical_roots(
    evidence: dict[str, dict[str, Any]],
    errors: list[str],
) -> dict[str, str]:
    roots: dict[str, str] = {}
    for evidence_id in evidence:
        if evidence_id in roots:
            continue
        path: list[str] = []
        positions: dict[str, int] = {}
        current = evidence_id
        terminal = evidence_id
        while current in evidence:
            if current in roots:
                terminal = roots[current]
                break
            if current in positions:
                cycle = path[positions[current] :]
                errors.append(
                    f"evidence {evidence_id}: duplicate_of cycle detected: "
                    f"{' -> '.join(cycle + [current])}"
                )
                terminal = current
                break
            positions[current] = len(path)
            path.append(current)
            next_id = evidence[current].get("duplicate_of")
            if not isinstance(next_id, str) or next_id not in evidence:
                terminal = current
                break
            current = next_id
        for path_id in path:
            roots[path_id] = terminal
    return roots


def audit_note_evidence(
    notes: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    state: AuditState,
) -> None:
    for chunk_id, note in notes.items():
        evidence_ids = note["evidence_ids"]
        for evidence_id in evidence_ids:
            evidence_row = evidence.get(evidence_id)
            if evidence_row is None:
                state.errors.append(
                    f"chunk note {chunk_id}: unknown evidence_id {evidence_id}"
                )
            elif evidence_row["chunk_id"] != chunk_id:
                state.errors.append(
                    f"chunk note {chunk_id}: evidence {evidence_id} belongs to "
                    f"{evidence_row['chunk_id']}"
                )
        if note["status"] == "skipped" and evidence_ids:
            state.errors.append(f"chunk note {chunk_id}: skipped note owns evidence")

    for evidence_id, row in evidence.items():
        chunk_id = row["chunk_id"]
        note = notes.get(chunk_id)
        if note is None or evidence_id not in note["evidence_ids"]:
            state.errors.append(
                f"evidence {evidence_id}: not listed by chunk note {chunk_id}"
            )
        elif note["status"] != "distilled":
            state.errors.append(
                f"evidence {evidence_id}: owning chunk note must be distilled"
            )


def source_derives_from(
    child_id: str,
    ancestor_id: str,
    sources: dict[str, dict[str, Any]],
) -> bool:
    pending = list(sources.get(child_id, {}).get("derived_from_source_ids", []))
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        if current == ancestor_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        pending.extend(
            sources.get(current, {}).get("derived_from_source_ids", [])
        )
    return False


def audit_claims(
    rows: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    evidence_roots: dict[str, str],
    strict_v3: bool,
    state: AuditState,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    claims = index_rows(rows, "claim_id", "claims.jsonl", state.errors)
    normalized: dict[str, dict[str, Any]] = {}

    for claim_id, row in claims.items():
        label = f"claim {claim_id}"
        if strict_v3:
            require_schema_version(row, label, state.errors)
        require_string(row, "claim", label, state.errors)
        evidence_ids = require_string_list(
            row,
            "evidence_ids",
            label,
            state.errors,
            unique=True,
        )
        valid_evidence_ids: list[str] = []
        for evidence_id in evidence_ids:
            if evidence_id not in evidence:
                state.errors.append(f"{label}: unknown evidence_id {evidence_id}")
            else:
                valid_evidence_ids.append(evidence_id)
        canonical_ids = [
            evidence_roots.get(evidence_id, evidence_id)
            for evidence_id in valid_evidence_ids
        ]
        if len(canonical_ids) != len(set(canonical_ids)):
            state.errors.append(
                f"{label}: evidence_ids repeat one canonical observation"
            )

        root_rows = [
            evidence[root_id]
            for root_id in dict.fromkeys(canonical_ids)
            if root_id in evidence
        ]
        support_sources = {
            evidence_row["source_id"]
            for evidence_row in root_rows
            if evidence_row["polarity"] == "supports"
        }
        opposing_sources = {
            evidence_row["source_id"]
            for evidence_row in root_rows
            if evidence_row["polarity"] == "opposes"
        }
        qualifying_sources = {
            evidence_row["source_id"]
            for evidence_row in root_rows
            if evidence_row["polarity"] in {"qualifies", "context", "uncertainty"}
        }

        if strict_v3:
            claim_kind = require_enum(
                row,
                "claim_kind",
                ALLOWED_CLAIM_KINDS,
                label,
                state.errors,
            )
            verification_status = require_enum(
                row,
                "verification_status",
                ALLOWED_VERIFICATION_STATUSES,
                label,
                state.errors,
            )
            lifecycle_status = require_enum(
                row,
                "lifecycle_status",
                ALLOWED_LIFECYCLE_STATUSES,
                label,
                state.errors,
            )
            supporting_source_ids = require_string_list(
                row,
                "supporting_source_ids",
                label,
                state.errors,
                unique=True,
            )
            opposing_source_ids = require_string_list(
                row,
                "opposing_source_ids",
                label,
                state.errors,
                unique=True,
            )
            qualifying_source_ids = require_string_list(
                row,
                "qualifying_source_ids",
                label,
                state.errors,
                unique=True,
            )
            if set(supporting_source_ids) != support_sources:
                state.errors.append(
                    f"{label}: supporting_source_ids do not match supporting evidence"
                )
            if set(opposing_source_ids) != opposing_sources:
                state.errors.append(
                    f"{label}: opposing_source_ids do not match opposing evidence"
                )
            if set(qualifying_source_ids) != qualifying_sources:
                state.errors.append(
                    f"{label}: qualifying_source_ids do not match qualifying evidence"
                )
            premise_claim_ids = require_string_list(
                row,
                "premise_claim_ids",
                label,
                state.errors,
                unique=True,
            )
            supersedes_claim_ids = require_string_list(
                row,
                "supersedes_claim_ids",
                label,
                state.errors,
                unique=True,
            )
            superseded_by_claim_ids = require_string_list(
                row,
                "superseded_by_claim_ids",
                label,
                state.errors,
                unique=True,
            )
            if claim_kind == "factual" and not valid_evidence_ids:
                state.errors.append(f"{label}: factual claim needs evidence")
            if claim_kind == "inference" and not premise_claim_ids:
                state.errors.append(f"{label}: inference needs premise_claim_ids")
            if verification_status in {"source-only", "externally-verified"}:
                if not support_sources:
                    state.errors.append(
                        f"{label}: {verification_status} needs supporting evidence"
                    )
            if verification_status == "disputed" and not (
                support_sources and opposing_sources
            ):
                state.errors.append(
                    f"{label}: disputed needs both supporting and opposing evidence"
                )
            if lifecycle_status == "superseded" and not superseded_by_claim_ids:
                state.errors.append(
                    f"{label}: superseded claim needs superseded_by_claim_ids"
                )
            if lifecycle_status == "active" and superseded_by_claim_ids:
                state.errors.append(
                    f"{label}: active claim cannot have superseded_by_claim_ids"
                )
        else:
            claim_kind = require_string(row, "type", label, state.errors)
            legacy_status = require_enum(
                row,
                "status",
                ALLOWED_LEGACY_CLAIM_STATUSES,
                label,
                state.errors,
            )
            verification_status = legacy_status
            lifecycle_status = (
                "superseded" if legacy_status == "superseded" else "active"
            )
            premise_claim_ids = optional_string_list(
                row,
                "premise_claim_ids",
                label,
                state.errors,
                unique=True,
            )
            supersedes_claim_ids = []
            superseded_by_claim_ids = []
            if legacy_status != "inference" and not valid_evidence_ids:
                state.errors.append(f"{label}: non-inference claim needs evidence")
            if legacy_status == "contradicted" and not (
                support_sources and opposing_sources
            ):
                state.errors.append(
                    f"{label}: contradicted needs supporting and opposing evidence"
                )

        independent_source_ids = require_string_list(
            row,
            "independent_source_ids",
            label,
            state.errors,
            unique=True,
        )
        unsupported_independent_sources: list[str] = []
        for source_id in independent_source_ids:
            if source_id not in sources:
                state.errors.append(f"{label}: unknown independent source {source_id}")
            elif source_id not in support_sources:
                unsupported_independent_sources.append(source_id)
        if unsupported_independent_sources:
            state.errors.append(
                f"{label}: independent sources lack claim evidence: "
                f"{', '.join(sorted(unsupported_independent_sources))}"
            )
        if strict_v3:
            independent_families: set[str] = set()
            for source_id in independent_source_ids:
                source = sources.get(source_id)
                if source is None:
                    continue
                family_id = source["source_family_id"]
                if family_id in independent_families:
                    state.errors.append(
                        f"{label}: independent sources share source_family_id {family_id}"
                    )
                independent_families.add(family_id)
            support_families = {
                sources[source_id]["source_family_id"]
                for source_id in support_sources
                if source_id in sources
            }
            if independent_families != support_families:
                state.errors.append(
                    f"{label}: independent_source_ids must represent every "
                    "supporting source family exactly once"
                )
            for left_position, left_id in enumerate(independent_source_ids):
                for right_id in independent_source_ids[left_position + 1 :]:
                    if source_derives_from(left_id, right_id, sources) or source_derives_from(
                        right_id,
                        left_id,
                        sources,
                    ):
                        state.errors.append(
                            f"{label}: independent sources cannot derive from each other"
                        )

        verification_refs = require_string_list(
            row,
            "verification_refs",
            label,
            state.errors,
        )
        if verification_status == "externally-verified" and not verification_refs:
            state.errors.append(
                f"{label}: externally-verified needs verification_refs"
            )

        normalized[claim_id] = {
            "claim_id": claim_id,
            "claim_kind": claim_kind,
            "verification_status": verification_status,
            "lifecycle_status": lifecycle_status,
            "evidence_ids": valid_evidence_ids,
            "canonical_evidence_ids": canonical_ids,
            "premise_claim_ids": premise_claim_ids,
            "supersedes_claim_ids": supersedes_claim_ids,
            "superseded_by_claim_ids": superseded_by_claim_ids,
        }

    if strict_v3:
        audit_claim_relations(normalized, evidence, state)
    return claims, normalized


def audit_claim_relations(
    claims: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    state: AuditState,
) -> None:
    for claim_id, claim in claims.items():
        label = f"claim {claim_id}"
        for premise_id in claim["premise_claim_ids"]:
            if premise_id == claim_id:
                state.errors.append(f"{label}: cannot use itself as a premise")
            elif premise_id not in claims:
                state.errors.append(f"{label}: unknown premise claim {premise_id}")
        for prior_id in claim["supersedes_claim_ids"]:
            prior = claims.get(prior_id)
            if prior_id == claim_id:
                state.errors.append(f"{label}: cannot supersede itself")
            elif prior is None:
                state.errors.append(f"{label}: unknown superseded claim {prior_id}")
            else:
                if prior["lifecycle_status"] != "superseded":
                    state.errors.append(
                        f"{label}: superseded claim {prior_id} must have "
                        "lifecycle_status superseded"
                    )
                if claim_id not in prior["superseded_by_claim_ids"]:
                    state.errors.append(
                        f"{label}: supersession link to {prior_id} is not reciprocal"
                    )
                old_revisions = {
                    evidence[evidence_id]["source_revision_id"]
                    for evidence_id in prior["canonical_evidence_ids"]
                    if evidence_id in evidence
                }
                new_revisions = {
                    evidence[evidence_id]["source_revision_id"]
                    for evidence_id in claim["canonical_evidence_ids"]
                    if evidence_id in evidence
                }
                if old_revisions and new_revisions and old_revisions == new_revisions:
                    state.errors.append(
                        f"{label}: supersession must be supported by a changed revision"
                    )
        for replacement_id in claim["superseded_by_claim_ids"]:
            replacement = claims.get(replacement_id)
            if replacement_id == claim_id:
                state.errors.append(f"{label}: cannot be superseded by itself")
            elif replacement is None:
                state.errors.append(
                    f"{label}: unknown replacement claim {replacement_id}"
                )
            elif claim_id not in replacement["supersedes_claim_ids"]:
                state.errors.append(
                    f"{label}: replacement link to {replacement_id} is not reciprocal"
                )

    detect_graph_cycles(
        {
            claim_id: claim["premise_claim_ids"]
            for claim_id, claim in claims.items()
        },
        "claim premise",
        state.errors,
    )
    detect_graph_cycles(
        {
            claim_id: claim["supersedes_claim_ids"]
            for claim_id, claim in claims.items()
        },
        "claim supersession",
        state.errors,
    )


def detect_graph_cycles(
    graph: dict[str, list[str]],
    label: str,
    errors: list[str],
) -> None:
    colors: dict[str, int] = {}

    def visit(node: str, path: list[str]) -> None:
        color = colors.get(node, 0)
        if color == 1:
            errors.append(f"{label}: cycle detected: {' -> '.join(path + [node])}")
            return
        if color == 2:
            return
        colors[node] = 1
        for child in graph.get(node, []):
            if child in graph:
                visit(child, path + [node])
        colors[node] = 2

    for node in graph:
        if colors.get(node, 0) == 0:
            visit(node, [])


def audit_coverage(
    coverage: dict[str, Any],
    source_catalog: dict[str, dict[str, Any]],
    chunks: dict[str, dict[str, Any]],
    notes: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
    evidence_roots: dict[str, str],
    manifest: dict[str, Any],
    strict_v3: bool,
    state: AuditState,
) -> dict[str, Any]:
    revisions = source_catalog["revisions"]
    logical_sources = source_catalog["logical"]
    if strict_v3:
        require_schema_version(coverage, "coverage.json", state.errors)
    source_entries = coverage.get("sources")
    if not isinstance(source_entries, list):
        state.errors.append("coverage.json: sources must be a list")
        source_entries = []

    indexed: dict[str, dict[str, Any]] = {}
    distilled_count = 0
    for position, entry in enumerate(source_entries, start=1):
        if not isinstance(entry, dict):
            state.errors.append(f"coverage.json source {position}: must be an object")
            continue
        source_id = require_identifier(
            entry,
            "source_id",
            f"coverage source {position}",
            state.errors,
        )
        source_revision_id = ""
        if strict_v3:
            source_revision_id = require_identifier(
                entry,
                "source_revision_id",
                f"coverage source {position}",
                state.errors,
            )
            source = revisions.get(source_revision_id)
            if source_revision_id and source is None:
                state.errors.append(
                    f"coverage source {position}: unknown source_revision_id "
                    f"{source_revision_id}"
                )
            elif source and source["source_id"] != source_id:
                state.errors.append(
                    f"coverage source {position}: source_id does not match revision"
                )
        key = source_revision_id if strict_v3 else source_id
        if key in indexed:
            state.errors.append(f"coverage.json: duplicate source entry {key}")
        elif key:
            indexed[key] = entry
    expected_source_keys = set(revisions if strict_v3 else logical_sources)
    if set(indexed) != expected_source_keys:
        kind = "revision IDs" if strict_v3 else "source IDs"
        state.errors.append(
            f"coverage.json: source {kind} must exactly match sources.jsonl"
        )

    for source_key, entry in indexed.items():
        source_id = (
            revisions.get(source_key, {}).get("source_id", "")
            if strict_v3
            else source_key
        )
        label = (
            f"coverage source revision {source_key}"
            if strict_v3
            else f"coverage {source_id}"
        )
        planned_list = require_string_list(
            entry,
            "planned_chunks",
            label,
            state.errors,
            unique=True,
        )
        planned = set(planned_list)
        actual = {
            chunk_id
            for chunk_id, row in chunks.items()
            if (
                row.get("source_revision_id") == source_key
                if strict_v3
                else row.get("source_id") == source_id
            )
        }
        if not actual:
            require_string(entry, "source_skip_reason", label, state.errors)
        if planned != actual:
            state.errors.append(
                f"{label}: planned_chunks do not match chunks.jsonl"
            )

        distilled_list = require_string_list(
            entry,
            "distilled_chunks",
            label,
            state.errors,
            unique=True,
        )
        distilled = set(distilled_list)
        expected_distilled = {
            chunk_id
            for chunk_id in actual
            if notes.get(chunk_id, {}).get("status") == "distilled"
        }
        if distilled != expected_distilled:
            state.errors.append(
                f"{label}: distilled_chunks do not match chunk notes"
            )
        distilled_count += len(expected_distilled)

        skipped_raw = entry.get("skipped_chunks")
        if not isinstance(skipped_raw, list):
            state.errors.append(f"{label}: skipped_chunks must be a list")
            skipped_raw = []
        skipped: set[str] = set()
        skipped_reasons: dict[str, str] = {}
        for item in skipped_raw:
            if not isinstance(item, dict):
                state.errors.append(f"{label}: skipped entry must be an object")
                continue
            chunk_id = require_identifier(
                item,
                "chunk_id",
                f"{label} skipped",
                state.errors,
            )
            reason = require_string(
                item,
                "reason",
                f"{label} skipped",
                state.errors,
            )
            if chunk_id:
                if chunk_id in skipped:
                    state.errors.append(f"{label}: skipped_chunks must be unique")
                skipped.add(chunk_id)
                skipped_reasons[chunk_id] = reason
        expected_skipped = {
            chunk_id
            for chunk_id in actual
            if notes.get(chunk_id, {}).get("status") == "skipped"
        }
        if skipped != expected_skipped:
            state.errors.append(
                f"{label}: skipped_chunks do not match chunk notes"
            )
        for chunk_id in skipped & expected_skipped:
            note_reason = notes[chunk_id].get("skip_reason")
            if skipped_reasons.get(chunk_id) != note_reason:
                state.errors.append(
                    f"{label}: skip reason for {chunk_id} does not match chunk note"
                )

    facets = coverage.get("facets")
    if not isinstance(facets, list):
        state.errors.append("coverage.json: facets must be a list")
        facets = []
    facet_names: set[str] = set()
    for position, facet in enumerate(facets, start=1):
        if not isinstance(facet, dict):
            state.errors.append(f"coverage facet {position}: must be an object")
            continue
        label = f"coverage facet {position}"
        facet_name = require_string(facet, "facet", label, state.errors)
        if facet_name in facet_names:
            state.errors.append(f"{label}: duplicate facet {facet_name}")
        elif facet_name:
            facet_names.add(facet_name)
        status = require_enum(
            facet,
            "status",
            ALLOWED_FACET_STATUSES,
            label,
            state.errors,
        )
        evidence_ids = require_string_list(
            facet,
            "evidence_ids",
            label,
            state.errors,
            unique=True,
        )
        canonical_ids: list[str] = []
        for evidence_id in evidence_ids:
            if evidence_id not in evidence:
                state.errors.append(f"{label}: unknown evidence_id {evidence_id}")
            else:
                canonical_ids.append(evidence_roots.get(evidence_id, evidence_id))
        if len(canonical_ids) != len(set(canonical_ids)):
            state.errors.append(
                f"{label}: evidence_ids repeat one canonical observation"
            )
        if status == "covered" and not evidence_ids:
            state.errors.append(f"{label}: covered facet needs evidence_ids")
        if status == "absent":
            require_string(facet, "search_note", label, state.errors)
        if status in {"not-applicable", "unresolved"}:
            require_string(facet, "reason", label, state.errors)
        if status == "unresolved":
            state.readiness_errors.append(
                f"{label}: unresolved facet blocks readiness"
            )

    missing_facets = set(manifest.get("required_facets", [])) - facet_names
    if strict_v3 and missing_facets:
        state.readiness_errors.append(
            "coverage.json: required facets missing: "
            f"{', '.join(sorted(missing_facets))}"
        )

    risk_checks = coverage.get("risk_checks")
    if not isinstance(risk_checks, list):
        state.errors.append("coverage.json: risk_checks must be a list")
        risk_checks = []
    risk_names: set[str] = set()
    for position, risk_check in enumerate(risk_checks, start=1):
        if not isinstance(risk_check, dict):
            state.errors.append(f"coverage risk {position}: must be an object")
            continue
        label = f"coverage risk {position}"
        risk_name = require_string(risk_check, "risk", label, state.errors)
        if risk_name in risk_names:
            state.errors.append(f"{label}: duplicate risk {risk_name}")
        elif risk_name:
            risk_names.add(risk_name)
        status = require_enum(
            risk_check,
            "status",
            ALLOWED_RISK_STATUSES,
            label,
            state.errors,
        )
        reviewed_chunks = require_string_list(
            risk_check,
            "reviewed_chunks",
            label,
            state.errors,
            unique=True,
        )
        for chunk_id in reviewed_chunks:
            if chunk_id not in chunks:
                state.errors.append(f"{label}: unknown reviewed chunk {chunk_id}")
        if status in {"pass", "fail"} and not reviewed_chunks:
            state.errors.append(f"{label}: {status} needs reviewed_chunks")
        if status in {"not-applicable", "unresolved"}:
            require_string(risk_check, "reason", label, state.errors)
        if status in {"fail", "unresolved"}:
            state.readiness_errors.append(
                f"{label}: {status} risk blocks readiness"
            )

    missing_risks = set(manifest.get("required_risks", [])) - risk_names
    if strict_v3 and missing_risks:
        state.readiness_errors.append(
            "coverage.json: required risks missing: "
            f"{', '.join(sorted(missing_risks))}"
        )
    if strict_v3 and distilled_count == 0 and not manifest.get(
        "allow_empty_result",
        False,
    ):
        state.readiness_errors.append(
            "coverage.json: no distilled chunks; all-skipped work is not ready"
        )
    return {
        "facet_names": facet_names,
        "risk_names": risk_names,
        "distilled_count": distilled_count,
    }


def audit_manifest_handoff(
    workdir: Path,
    manifest: dict[str, Any],
    source_catalog: dict[str, dict[str, Any]],
    claims: dict[str, dict[str, Any]],
    state: AuditState,
) -> None:
    declared_revisions = set(manifest["handoff_source_revision_ids"])
    observed_revisions = set(source_catalog["revisions"])
    if declared_revisions != observed_revisions:
        state.readiness_errors.append(
            f"{MANIFEST_FILE}: handoff source_revision_ids must exactly match sources"
        )
    for claim_id in manifest["handoff_key_claim_ids"]:
        if claim_id not in claims:
            state.errors.append(
                f"{MANIFEST_FILE}: handoff references unknown key claim {claim_id}"
            )
    if claims and not manifest["handoff_key_claim_ids"]:
        state.readiness_errors.append(
            f"{MANIFEST_FILE}: handoff needs at least one key_claim_id"
        )
    for relative_path in manifest["reload_paths"]:
        resolved = safe_bundle_path(
            workdir,
            relative_path,
            f"{MANIFEST_FILE} reload path {relative_path}",
            state.errors,
        )
        if resolved is not None and not resolved.exists():
            state.readiness_errors.append(
                f"{MANIFEST_FILE}: reload path does not exist: {relative_path}"
            )
    semantic_receipt = manifest.get("semantic_receipt")
    if semantic_receipt:
        resolved = safe_bundle_path(
            workdir,
            semantic_receipt,
            f"{MANIFEST_FILE} semantic_evaluation_receipt",
            state.errors,
        )
        if resolved is not None:
            if not resolved.is_file():
                state.readiness_errors.append(
                    f"{MANIFEST_FILE}: semantic evaluation receipt does not exist"
                )
            else:
                audit_semantic_receipt(
                    resolved,
                    state,
                )


def audit_semantic_receipt(
    path: Path,
    state: AuditState,
) -> None:
    label = f"{MANIFEST_FILE}: semantic evaluation receipt"
    try:
        value = strict_json_loads(path.read_text(encoding="utf-8"))
    except UnicodeError:
        state.readiness_errors.append(f"{label} is not valid UTF-8")
        return
    except OSError as exc:
        state.readiness_errors.append(
            f"{label} cannot be read: {exc.strerror or type(exc).__name__}"
        )
        return
    except (json.JSONDecodeError, StrictJsonError) as exc:
        detail = exc.msg if isinstance(exc, json.JSONDecodeError) else str(exc)
        state.readiness_errors.append(f"{label} is not valid JSON: {detail}")
        return
    if not isinstance(value, dict):
        state.readiness_errors.append(f"{label} must be a JSON object")
        return
    state.warnings.append(
        f"{label} is self-attested metadata, not trusted semantic proof"
    )


def _audit_bundle(workdir: Path) -> dict[str, Any]:
    state = AuditState()
    try:
        resolved_workdir = workdir.resolve()
    except OSError:
        resolved_workdir = workdir
    if not resolved_workdir.is_dir():
        return {
            "schema_version": "unknown",
            "status": "fail",
            "structure_status": "fail",
            "readiness_status": "fail",
            "bundle_sha256": None,
            "counts": {
                "sources": 0,
                "chunks": 0,
                "chunk_notes": 0,
                "evidence": 0,
                "claims": 0,
            },
            "errors": ["bundle path must be an existing directory"],
            "readiness_errors": [],
            "warnings": [],
        }

    text_files: dict[str, str] = {}
    for file_name in REQUIRED_TEXT_FILES:
        text = read_text(resolved_workdir / file_name, state.errors)
        if text is None:
            continue
        if not text.strip():
            state.errors.append(f"empty file: {file_name}")
        text_files[file_name] = text

    manifest_path = resolved_workdir / MANIFEST_FILE
    strict_v3 = manifest_path.is_file()
    load_errors: list[str] = []
    if strict_v3:
        manifest_raw = load_json(manifest_path, load_errors)
        manifest = (
            audit_manifest(manifest_raw, state)
            if not load_errors
            else {}
        )
    else:
        manifest_raw = {}
        manifest = {
            "route": "",
            "required_facets": [],
            "required_risks": [],
            "allow_empty_result": False,
            "semantic_required": False,
            "semantic_receipt": None,
            "handoff_source_revision_ids": [],
            "handoff_key_claim_ids": [],
            "reload_paths": [],
            "unresolved_gaps": [],
            "safe_to_drop": [],
        }
        state.warnings.append(
            "legacy bundle: add run-manifest.json schema_version 3 to evaluate readiness"
        )

    source_rows = load_jsonl(resolved_workdir / "sources.jsonl", load_errors)
    chunk_rows = load_jsonl(resolved_workdir / "chunks.jsonl", load_errors)
    note_rows = load_jsonl(resolved_workdir / "chunk-notes.jsonl", load_errors)
    evidence_rows = load_jsonl(resolved_workdir / "evidence.jsonl", load_errors)
    claim_rows = load_jsonl(resolved_workdir / "claims.jsonl", load_errors)
    coverage = load_json(resolved_workdir / "coverage.json", load_errors)
    if load_errors:
        state.errors.extend(load_errors)
        bundle_sha256 = canonical_bundle_digest(
            resolved_workdir,
            {"revisions": {}, "logical": {}},
            state.errors,
        )
        return {
            "schema_version": BUNDLE_SCHEMA_VERSION if strict_v3 else "legacy-2",
            "status": "fail",
            "structure_status": "fail",
            "readiness_status": "fail" if strict_v3 else "not-evaluated",
            "bundle_sha256": bundle_sha256,
            "counts": {
                "sources": len(source_rows),
                "chunks": len(chunk_rows),
                "chunk_notes": len(note_rows),
                "evidence": len(evidence_rows),
                "claims": len(claim_rows),
            },
            "errors": state.errors,
            "readiness_errors": state.readiness_errors,
            "warnings": state.warnings,
        }

    source_rows_index, source_catalog = audit_sources(
        source_rows,
        resolved_workdir,
        strict_v3,
        state,
    )
    bundle_sha256 = canonical_bundle_digest(
        resolved_workdir,
        source_catalog,
        state.errors,
    )
    if not source_rows_index:
        state.errors.append("sources.jsonl: at least one source is required")
    chunk_rows_index, chunks = audit_chunks(
        chunk_rows,
        source_catalog,
        strict_v3,
        state,
    )
    note_rows_index, notes = audit_notes(
        note_rows,
        chunks,
        strict_v3,
        state,
    )
    evidence_rows_index, evidence, evidence_roots = audit_evidence(
        evidence_rows,
        source_catalog,
        chunks,
        strict_v3,
        state,
    )
    audit_note_evidence(notes, evidence, state)
    claim_rows_index, claims = audit_claims(
        claim_rows,
        source_catalog["logical"],
        evidence,
        evidence_roots,
        strict_v3,
        state,
    )
    audit_coverage(
        coverage,
        source_catalog,
        chunks,
        notes,
        evidence,
        evidence_roots,
        manifest,
        strict_v3,
        state,
    )

    if strict_v3:
        for file_name, text in text_files.items():
            if not has_substantive_markdown(text):
                state.readiness_errors.append(
                    f"{file_name}: needs substantive content beyond headings"
                )
        if not claims and not manifest["allow_empty_result"]:
            state.readiness_errors.append(
                "claims.jsonl: at least one claim is required for readiness"
            )
        audit_manifest_handoff(
            resolved_workdir,
            manifest,
            source_catalog,
            claims,
            state,
        )

    structure_status = "pass" if not state.errors else "fail"
    if not strict_v3:
        readiness_status = "not-evaluated"
    elif state.errors or state.readiness_errors:
        readiness_status = "fail"
    else:
        readiness_status = "pass"

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION if strict_v3 else "legacy-2",
        "status": structure_status,
        "structure_status": structure_status,
        "readiness_status": readiness_status,
        "bundle_sha256": bundle_sha256,
        "counts": {
            "sources": len(source_rows_index),
            "chunks": len(chunk_rows_index),
            "chunk_notes": len(note_rows_index),
            "evidence": len(evidence_rows_index),
            "claims": len(claim_rows_index),
        },
        "errors": state.errors,
        "readiness_errors": state.readiness_errors,
        "warnings": state.warnings,
    }


def audit_bundle(workdir: Path) -> dict[str, Any]:
    """Return a receipt for every input shape instead of raising."""
    try:
        return _audit_bundle(workdir)
    except Exception as exc:  # Defensive boundary for untrusted bundle input.
        return {
            "schema_version": "unknown",
            "status": "fail",
            "structure_status": "fail",
            "readiness_status": "fail",
            "bundle_sha256": None,
            "counts": {
                "sources": 0,
                "chunks": 0,
                "chunk_notes": 0,
                "evidence": 0,
                "claims": 0,
            },
            "errors": [f"internal audit failure: {type(exc).__name__}: {exc}"],
            "readiness_errors": [],
            "warnings": [],
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a structured long-material distillation bundle."
    )
    parser.add_argument("workdir", type=Path, help="Bundle directory to audit.")
    parser.add_argument(
        "--require-ready",
        action="store_true",
        help="Return nonzero unless both structure and delivery readiness pass.",
    )
    args = parser.parse_args()

    receipt = audit_bundle(args.workdir)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    if receipt["structure_status"] != "pass":
        return 1
    if args.require_ready and receipt["readiness_status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
