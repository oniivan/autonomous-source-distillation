"""Hash the complete package-local execution surface of an evaluator."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


def file_surface(
    root: Path,
    relative_paths: Iterable[str],
) -> dict[str, Any]:
    root = root.resolve()
    names = tuple(sorted(relative_paths))
    if not names or len(names) != len(set(names)):
        raise ValueError("evaluator surface paths must be nonempty and unique")

    files: list[dict[str, str]] = []
    for name in names:
        if not isinstance(name, str) or not name:
            raise ValueError("evaluator surface paths must be nonempty strings")
        candidate = (root / name).resolve()
        if not candidate.is_relative_to(root) or not candidate.is_file():
            raise ValueError(f"evaluator surface file is missing or unsafe: {name}")
        files.append(
            {
                "path": name,
                "sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            }
        )

    digest = hashlib.sha256()
    for item in files:
        digest.update(item["path"].encode("utf-8"))
        digest.update(b"\0")
        digest.update(item["sha256"].encode("ascii"))
        digest.update(b"\n")
    return {
        "schema_version": 1,
        "surface_sha256": digest.hexdigest(),
        "files": files,
    }
