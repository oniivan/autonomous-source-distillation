"""Define and stage the behavior-bearing runtime surface for sealed evaluations."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


RUNTIME_PATHS = (
    "SKILL.md",
    "agents",
    "references",
    "assets/starter-bundle",
    "scripts/audit_bundle.py",
    "scripts/bundle_contract.py",
    "scripts/chunk_text.py",
    "scripts/locator_utils.py",
    "scripts/runtime_contract.py",
)
EXCLUDED_PARTS = {".git", "__pycache__"}


def runtime_files(root: Path) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for relative_name in RUNTIME_PATHS:
        candidate = root / relative_name
        if candidate.is_file():
            files.append(candidate)
        elif candidate.is_dir():
            files.extend(
                path
                for path in candidate.rglob("*")
                if path.is_file()
                and not any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts)
                and path.suffix != ".pyc"
            )
        else:
            raise ValueError(f"skill runtime is missing required path: {relative_name}")
    return sorted(set(files), key=lambda path: path.relative_to(root).as_posix())


def validate_runtime_root(root: Path) -> None:
    if not root.is_dir():
        raise ValueError("skill root must be an existing directory")
    runtime_files(root)


def file_manifest(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in runtime_files(root)
    ]


def runtime_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for item in file_manifest(root):
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def stage_runtime(source_root: Path, target_root: Path) -> dict[str, Any]:
    validate_runtime_root(source_root)
    if target_root.exists():
        raise ValueError("staged runtime target must not already exist")
    target_root.mkdir(parents=True)
    source_root = source_root.resolve()
    for source in runtime_files(source_root):
        relative = source.relative_to(source_root)
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    manifest = file_manifest(target_root)
    return {
        "mode": "allowlist-copy",
        "skill_tree_sha256": runtime_digest(target_root),
        "allowed_files": manifest,
        "file_count": len(manifest),
        "forbidden_paths_present": any(
            part in {"evals", "tests", "methodology", "oracles"}
            for path in target_root.rglob("*")
            for part in path.relative_to(target_root).parts
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Print the behavior-bearing runtime manifest for this skill."
    )
    parser.add_argument(
        "--skill-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args()
    try:
        manifest = {
            "schema_version": 1,
            "skill_runtime_sha256": runtime_digest(args.skill_root),
            "allowed_files": file_manifest(args.skill_root),
        }
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "fail", "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
