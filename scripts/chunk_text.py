#!/usr/bin/env python3
"""Chunk long text while preserving line ranges and best-effort locators."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, TextIO

SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from bundle_contract import BUNDLE_SCHEMA_VERSION, ID_RE  # noqa: E402


TIMESTAMP_RE = re.compile(
    r"(?P<locator>(?:\[\s*)?(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d+)?(?:\s*\])?)"
)
ISO_TIME_RE = re.compile(r"(?P<locator>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)")


@dataclass(slots=True)
class Line:
    number: int
    text: str
    word_count: int
    locator: str | None


@dataclass(slots=True)
class Unit:
    lines: list[Line]
    word_count: int


@dataclass(slots=True)
class Chunk:
    units: list[Unit]
    overlap_unit_count: int


def line_word_count(lines: Iterable[Line]) -> int:
    return sum(line.word_count for line in lines)


def unit_word_count(units: Iterable[Unit]) -> int:
    return sum(unit.word_count for unit in units)


def flatten_units(units: Iterable[Unit]) -> list[Line]:
    return [line for unit in units for line in unit.lines]


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_locator(text: str) -> str | None:
    for pattern in (ISO_TIME_RE, TIMESTAMP_RE):
        match = pattern.search(text)
        if match:
            return match.group("locator").strip("[] ")
    return None


def iter_lines(text: str) -> Iterator[Line]:
    stream = io.StringIO(text, newline=None)
    for idx, raw in enumerate(stream, start=1):
        normalized = raw.rstrip("\r\n")
        yield Line(
            idx,
            normalized,
            sum(1 for _ in re.finditer(r"\S+", normalized)),
            find_locator(normalized),
        )


def parse_lines(text: str) -> list[Line]:
    return list(iter_lines(text))


def iter_units(lines: Iterable[Line], boundary_mode: str) -> Iterator[Unit]:
    if boundary_mode == "line":
        for line in lines:
            yield Unit([line], line.word_count)
        return

    current: list[Line] = []
    current_word_count = 0
    for line in lines:
        current.append(line)
        current_word_count += line.word_count
        if not line.text.strip():
            yield Unit(current, current_word_count)
            current = []
            current_word_count = 0
    if current:
        yield Unit(current, current_word_count)


def build_units(lines: Iterable[Line], boundary_mode: str) -> list[Unit]:
    return list(iter_units(lines, boundary_mode))


def iter_chunks(
    units: Iterable[Unit],
    max_words: int,
    overlap_words: int,
) -> Iterator[Chunk]:
    current: list[Unit] = []
    current_word_count = 0
    overlap_unit_count = 0

    for unit in units:
        has_unique_content = len(current) > overlap_unit_count
        exceeds_limit = current_word_count + unit.word_count > max_words
        if current and has_unique_content and exceeds_limit:
            yield Chunk(list(current), overlap_unit_count)
            current = overlap_tail(current, overlap_words)
            overlap_unit_count = len(current)
            current_word_count = unit_word_count(current)
        current.append(unit)
        current_word_count += unit.word_count

    if current:
        yield Chunk(list(current), overlap_unit_count)


def split_chunks(
    units: Iterable[Unit],
    max_words: int,
    overlap_words: int,
) -> list[Chunk]:
    return list(iter_chunks(units, max_words, overlap_words))


def overlap_tail(units: list[Unit], overlap_words: int) -> list[Unit]:
    if overlap_words <= 0:
        return []
    kept: list[Unit] = []
    total = 0
    for unit in reversed(units):
        kept.append(unit)
        total += unit.word_count
        if total >= overlap_words:
            break
    return list(reversed(kept))


def locator_range(lines: list[Line]) -> tuple[str | None, str | None]:
    locators = [line.locator for line in lines if line.locator]
    return (
        locators[0] if locators else None,
        locators[-1] if locators else None,
    )


def chunk_meta(
    chunk: Chunk,
    source_id: str,
    index: int,
    source_sha256: str,
    source_line_count: int,
    boundary_mode: str,
    source_revision_id: str | None = None,
) -> dict[str, object]:
    source_revision_id = source_revision_id or f"{source_id}-R1"
    lines = flatten_units(chunk.units)
    unique_lines = flatten_units(chunk.units[chunk.overlap_unit_count :])
    overlap_lines = flatten_units(chunk.units[: chunk.overlap_unit_count])
    locator_start, locator_end = locator_range(lines)
    content_locator_start, content_locator_end = locator_range(unique_lines)
    text = "\n".join(line.text for line in lines)
    content_text = "\n".join(line.text for line in unique_lines)

    return {
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "chunk_id": f"{source_revision_id}-C{index:03d}",
        "source_id": source_id,
        "source_revision_id": source_revision_id,
        "ordinal": index,
        "boundary_mode": boundary_mode,
        "source_sha256": source_sha256,
        "source_line_count": source_line_count,
        "line_start": lines[0].number,
        "line_end": lines[-1].number,
        "content_line_start": unique_lines[0].number,
        "content_line_end": unique_lines[-1].number,
        "overlap_line_start": overlap_lines[0].number if overlap_lines else None,
        "overlap_line_end": overlap_lines[-1].number if overlap_lines else None,
        "overlap_line_count": len(overlap_lines),
        "locator_start": locator_start,
        "locator_end": locator_end,
        "content_locator_start": content_locator_start,
        "content_locator_end": content_locator_end,
        "word_count": line_word_count(lines),
        "content_word_count": line_word_count(unique_lines),
        "chunk_sha256": sha256_text(text),
        "content_sha256": sha256_text(content_text),
        "text": text,
    }


def write_markdown(
    chunks: Iterable[dict[str, object]],
    stream: TextIO,
) -> None:
    first = True
    for chunk in chunks:
        locator = ""
        if chunk["locator_start"] or chunk["locator_end"]:
            locator = f" locators {chunk['locator_start'] or '?'}-{chunk['locator_end'] or '?'}"
        overlap = ""
        if chunk["overlap_line_count"]:
            overlap = (
                f" overlap {chunk['overlap_line_start']}-{chunk['overlap_line_end']}"
            )
        rendered = (
            f"## {chunk['chunk_id']} lines {chunk['line_start']}-{chunk['line_end']} "
            f"content {chunk['content_line_start']}-{chunk['content_line_end']}"
            f"{overlap}{locator}\n\n"
            f"{chunk['text']}\n"
        )
        if not first:
            stream.write("\n")
        stream.write(rendered)
        first = False


def write_jsonl(
    chunks: Iterable[dict[str, object]],
    stream: TextIO,
) -> None:
    for chunk in chunks:
        stream.write(json.dumps(chunk, ensure_ascii=False))
        stream.write("\n")


def iter_chunk_metadata(
    text: str,
    source_id: str,
    source_revision_id: str,
    source_sha256: str,
    source_line_count: int,
    boundary_mode: str,
    max_words: int,
    overlap_words: int,
) -> Iterator[dict[str, object]]:
    lines = iter_lines(text)
    units = iter_units(lines, boundary_mode)
    chunks = iter_chunks(units, max_words, overlap_words)
    for index, chunk in enumerate(chunks, start=1):
        yield chunk_meta(
            chunk,
            source_id,
            index,
            source_sha256,
            source_line_count,
            boundary_mode,
            source_revision_id,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk a long text file for staged distillation.")
    parser.add_argument("input", type=Path, help="Input text file.")
    parser.add_argument("--source-id", default="S1", help="Source ID prefix for chunk IDs.")
    parser.add_argument(
        "--source-revision-id",
        help="Immutable source revision ID. Defaults to <source-id>-R1.",
    )
    parser.add_argument("--max-words", type=int, default=900, help="Approximate max words per chunk.")
    parser.add_argument("--overlap-words", type=int, default=80, help="Words to carry into the next chunk.")
    parser.add_argument(
        "--boundary-mode",
        choices=("line", "paragraph"),
        default="line",
        help="Atomic boundary units for mechanical chunking.",
    )
    parser.add_argument("--format", choices=("markdown", "jsonl"), default="markdown")
    parser.add_argument("--output", type=Path, help="Output file. Defaults to stdout.")
    args = parser.parse_args()

    if args.max_words <= 0:
        parser.error("--max-words must be positive")
    if args.overlap_words < 0:
        parser.error("--overlap-words must be zero or positive")
    if args.overlap_words >= args.max_words:
        parser.error("--overlap-words must be smaller than --max-words")
    if not ID_RE.fullmatch(args.source_id):
        parser.error("--source-id must be a non-empty portable identifier")
    source_revision_id = args.source_revision_id or f"{args.source_id}-R1"
    if not ID_RE.fullmatch(source_revision_id):
        parser.error("--source-revision-id must be a non-empty portable identifier")

    try:
        source_bytes = args.input.read_bytes()
    except OSError as exc:
        parser.error(
            f"cannot read input: {exc.strerror or type(exc).__name__}"
        )
    try:
        text = source_bytes.decode("utf-8")
    except UnicodeError:
        parser.error("input must be valid UTF-8")
    if not text.strip():
        parser.error("input must contain non-whitespace text")

    source_line_count = sum(1 for _ in iter_lines(text))
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    chunks = iter_chunk_metadata(
        text,
        args.source_id,
        source_revision_id,
        source_sha256,
        source_line_count,
        args.boundary_mode,
        args.max_words,
        args.overlap_words,
    )

    try:
        if args.output:
            with args.output.open("w", encoding="utf-8", newline="\n") as stream:
                if args.format == "jsonl":
                    write_jsonl(chunks, stream)
                else:
                    write_markdown(chunks, stream)
        elif args.format == "jsonl":
            write_jsonl(chunks, sys.stdout)
        else:
            write_markdown(chunks, sys.stdout)
    except OSError as exc:
        parser.error(
            f"cannot write output: {exc.strerror or type(exc).__name__}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
