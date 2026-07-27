from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "assets" / "starter-bundle"


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit_bundle = load_script("starter_audit_bundle", ROOT / "scripts" / "audit_bundle.py")
chunk_text = load_script("starter_chunk_text", ROOT / "scripts" / "chunk_text.py")


class StarterBundleTests(unittest.TestCase):
    def test_starter_bundle_passes_structure_and_readiness(self):
        receipt = audit_bundle.audit_bundle(STARTER)

        self.assertEqual(receipt["structure_status"], "pass", receipt)
        self.assertEqual(receipt["readiness_status"], "pass", receipt)
        self.assertEqual(receipt["schema_version"], 3)

    def test_committed_chunk_matches_current_chunker(self):
        source_path = STARTER / "inputs" / "source.txt"
        source_bytes = source_path.read_bytes()
        source_text = source_bytes.decode("utf-8")
        source_line_count = sum(1 for _ in chunk_text.iter_lines(source_text))
        generated = list(
            chunk_text.iter_chunk_metadata(
                source_text,
                "S1",
                "S1-R1",
                hashlib.sha256(source_bytes).hexdigest(),
                source_line_count,
                "line",
                900,
                80,
            )
        )
        committed = [
            json.loads(line)
            for line in (STARTER / "chunks.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

        self.assertEqual(generated, committed)


if __name__ == "__main__":
    unittest.main()
