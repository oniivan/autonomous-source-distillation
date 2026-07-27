from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "chunk_text.py"
SPEC = importlib.util.spec_from_file_location("chunk_text", SCRIPT)
assert SPEC and SPEC.loader
chunk_text = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = chunk_text
SPEC.loader.exec_module(chunk_text)


class ChunkTextTests(unittest.TestCase):
    def build(self, text: str, max_words: int, overlap_words: int, mode: str = "line"):
        lines = chunk_text.parse_lines(text)
        units = chunk_text.build_units(lines, mode)
        chunks = chunk_text.split_chunks(units, max_words, overlap_words)
        digest = chunk_text.sha256_text(text)
        return [
            chunk_text.chunk_meta(chunk, "S1", index, digest, len(lines), mode)
            for index, chunk in enumerate(chunks, start=1)
        ]

    def test_unique_content_ranges_cover_each_line_once_with_overlap(self):
        text = "\n".join(f"{index:02d}:00 word{index} extra" for index in range(1, 7))
        chunks = self.build(text, max_words=7, overlap_words=2)

        covered = []
        for chunk in chunks:
            covered.extend(
                range(chunk["content_line_start"], chunk["content_line_end"] + 1)
            )
        self.assertEqual(covered, list(range(1, 7)))
        self.assertEqual(chunks[0]["overlap_line_count"], 0)
        self.assertGreater(chunks[1]["overlap_line_count"], 0)
        self.assertLess(chunks[1]["line_start"], chunks[1]["content_line_start"])

    def test_content_hash_excludes_loaded_overlap(self):
        text = "a one\nb two\nc three\nd four"
        chunks = self.build(text, max_words=4, overlap_words=2)

        self.assertEqual(chunks[1]["content_line_start"], 3)
        self.assertEqual(
            chunks[1]["content_sha256"], chunk_text.sha256_text("c three")
        )
        self.assertNotEqual(chunks[1]["chunk_sha256"], chunks[1]["content_sha256"])

    def test_paragraph_mode_keeps_paragraph_units(self):
        text = "alpha beta\ngamma\n\ndelta epsilon\nzeta"
        chunks = self.build(text, max_words=4, overlap_words=0, mode="paragraph")

        self.assertEqual(len(chunks), 2)
        self.assertEqual((chunks[0]["content_line_start"], chunks[0]["content_line_end"]), (1, 3))
        self.assertEqual((chunks[1]["content_line_start"], chunks[1]["content_line_end"]), (4, 5))
        self.assertEqual(chunks[0]["boundary_mode"], "paragraph")

    def test_locators_distinguish_loaded_and_unique_content(self):
        text = "00:01 alpha beta\n00:02 gamma delta\n00:03 epsilon zeta"
        chunks = self.build(text, max_words=4, overlap_words=2)

        self.assertEqual(chunks[1]["locator_start"], "00:01")
        self.assertEqual(chunks[1]["content_locator_start"], "00:02")
        self.assertEqual(chunks[1]["content_locator_end"], "00:02")

    def test_iso_datetime_wins_over_generic_clock_locator(self):
        locator = chunk_text.find_locator("2026-07-18 12:34 build completed")
        self.assertEqual(locator, "2026-07-18 12:34")

    def test_line_parsing_preserves_trailing_spaces_and_tabs(self):
        lines = chunk_text.parse_lines("alpha  \nbeta\t\n")

        self.assertEqual([line.text for line in lines], ["alpha  ", "beta\t"])

    def test_large_unit_does_not_create_overlap_only_chunk(self):
        text = "one two three\n" + " ".join(f"word{index}" for index in range(20))
        chunks = self.build(text, max_words=8, overlap_words=3)

        self.assertEqual(len(chunks), 2)
        self.assertGreater(chunks[1]["content_word_count"], 0)

    def test_jsonl_cli_emits_auditable_unique_content_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.txt"
            output = Path(temp) / "chunks.jsonl"
            source.write_text("00:01 alpha beta\n00:02 gamma delta\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(source),
                    "--source-id",
                    "TX",
                    "--max-words",
                    "4",
                    "--overlap-words",
                    "2",
                    "--format",
                    "jsonl",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
                cwd=source.parent,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = [
                json.loads(line)
                for line in output.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(rows[0]["source_id"], "TX")
            self.assertEqual(rows[0]["source_revision_id"], "TX-R1")
            self.assertEqual(rows[0]["chunk_id"], "TX-R1-C001")
            self.assertEqual(
                rows[0]["schema_version"],
                chunk_text.BUNDLE_SCHEMA_VERSION,
            )
            self.assertEqual(rows[0]["content_line_start"], 1)
            self.assertIn("source_sha256", rows[0])
            self.assertIn("content_sha256", rows[0])

    def test_cli_binds_raw_source_bytes_and_explicit_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "source.txt"
            output = Path(temp) / "chunks.jsonl"
            source_bytes = b"00:01 alpha\r\n00:02 beta\r\n"
            source.write_bytes(source_bytes)

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    str(source),
                    "--source-id",
                    "TX",
                    "--source-revision-id",
                    "TX-REV-2026-07-26",
                    "--format",
                    "jsonl",
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            row = json.loads(output.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(row["source_revision_id"], "TX-REV-2026-07-26")
            self.assertEqual(row["source_line_count"], 2)
            self.assertEqual(
                row["source_sha256"],
                hashlib.sha256(source_bytes).hexdigest(),
            )

    def test_cli_rejects_bad_public_inputs_without_traceback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            valid = root / "valid.txt"
            empty = root / "empty.txt"
            invalid_utf8 = root / "invalid.txt"
            valid.write_text("alpha\n", encoding="utf-8")
            empty.write_text(" \n", encoding="utf-8")
            invalid_utf8.write_bytes(b"\xff")
            cases = [
                ([str(root / "missing.txt")], "cannot read input"),
                ([str(empty)], "must contain non-whitespace text"),
                ([str(invalid_utf8)], "must be valid UTF-8"),
                ([str(valid), "--source-id", ""], "portable identifier"),
                (
                    [str(valid), "--source-revision-id", "bad id"],
                    "portable identifier",
                ),
                (
                    [
                        str(valid),
                        "--output",
                        str(root / "missing-parent" / "chunks.jsonl"),
                    ],
                    "cannot write output",
                ),
            ]

            for arguments, expected in cases:
                with self.subTest(arguments=arguments):
                    result = subprocess.run(
                        [sys.executable, str(SCRIPT), *arguments],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn(expected, result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
