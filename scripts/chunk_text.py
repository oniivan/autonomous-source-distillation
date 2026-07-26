#!/usr/bin/env python3
"""Chunk long text while preserving line ranges and best-effort locators."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


TIMESTAMP_RE = re.compile(
    r"(?P<locator>(?:\[\s*)?(?:\d{1,2}:)?\d{1,2}:\d{2}(?:\.\d+)?(?:\s*\])?)"
)
ISO_TIME_RE = re.compile(r"(?P<locator>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(?::\d{2})?)")


@dataclass
class Line:
    number: int
    text: str
    words: list[str]
    locator: str | None


@dataclass
class Unit:
    lines: list[Line]


@dataclass
class Chunk:
    units: list[Unit]
    overlap_unit_count: int


def line_word_count(lines: Iterable[Line]) -> int:
    return sum(len(line.words) for line in lines)


def unit_word_count(units: Iterable[Unit]) -> int:
    return sum(line_word_count(unit.lines) for unit in units)


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


def parse_lines(text: str) -> list[Line]:
    parsed: list[Line] = []
    for idx, raw in enumerate(text.splitlines(), start=1):
        words = re.findall(r"\S+", raw)
        parsed.append(Line(idx, raw.rstrip(), words, find_locator(raw)))
    return parsed


def build_units(lines: list[Line], boundary_mode: str) -> list[Unit]:
    if boundary_mode == "line":
        return [Unit([line]) for line in lines]

    units: list[Unit] = []
    current: list[Line] = []
    for line in lines:
        current.append(line)
        if not line.text.strip():
            units.append(Unit(current))
            current = []
    if current:
        units.append(Unit(current))
    return units


def split_chunks(units: list[Unit], max_words: int, overlap_words: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    current: list[Unit] = []
    overlap_unit_count = 0

    for unit in units:
        has_unique_content = len(current) > overlap_unit_count
        exceeds_limit = unit_word_count(current) + unit_word_count([unit]) > max_words
        if current and has_unique_content and exceeds_limit:
            chunks.append(Chunk(list(current), overlap_unit_count))
            current = overlap_tail(current, overlap_words)
            overlap_unit_count = len(current)
        current.append(unit)

    if current:
        chunks.append(Chunk(list(current), overlap_unit_count))

    return chunks


def overlap_tail(units: list[Unit], overlap_words: int) -> list[Unit]:
    if overlap_words <= 0:
        return []
    kept: list[Unit] = []
    total = 0
    for unit in reversed(units):
        kept.append(unit)
        total += unit_word_count([unit])
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
) -> dict[str, object]:
    lines = flatten_units(chunk.units)
    unique_lines = flatten_units(chunk.units[chunk.overlap_unit_count :])
    overlap_lines = flatten_units(chunk.units[: chunk.overlap_unit_count])
    locator_start, locator_end = locator_range(lines)
    content_locator_start, content_locator_end = locator_range(unique_lines)
    text = "\n".join(line.text for line in lines)
    content_text = "\n".join(line.text for line in unique_lines)

    return {
        "schema_version": 2,
        "chunk_id": f"{source_id}-C{index:03d}",
        "source_id": source_id,
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


def write_markdown(chunks: list[dict[str, object]], output: Path | None) -> None:
    rendered: list[str] = []
    for chunk in chunks:
        locator = ""
        if chunk["locator_start"] or chunk["locator_end"]:
            locator = f" locators {chunk['locator_start'] or '?'}-{chunk['locator_end'] or '?'}"
        overlap = ""
        if chunk["overlap_line_count"]:
            overlap = (
                f" overlap {chunk['overlap_line_start']}-{chunk['overlap_line_end']}"
            )
        rendered.append(
            f"## {chunk['chunk_id']} lines {chunk['line_start']}-{chunk['line_end']} "
            f"content {chunk['content_line_start']}-{chunk['content_line_end']}"
            f"{overlap}{locator}\n\n"
            f"{chunk['text']}\n"
        )
    text = "\n".join(rendered)
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text)


def write_jsonl(chunks: list[dict[str, object]], output: Path | None) -> None:
    lines = [json.dumps(chunk, ensure_ascii=False) for chunk in chunks]
    text = "\n".join(lines) + ("\n" if lines else "")
    if output:
        output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Chunk a long text file for staged distillation.")
    parser.add_argument("input", type=Path, help="Input text file.")
    parser.add_argument("--source-id", default="S1", help="Source ID prefix for chunk IDs.")
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

    text = args.input.read_text(encoding="utf-8")
    parsed = parse_lines(text)
    units = build_units(parsed, args.boundary_mode)
    raw_chunks = split_chunks(units, args.max_words, args.overlap_words)
    source_sha256 = sha256_text(text)
    chunks = [
        chunk_meta(
            chunk,
            args.source_id,
            idx,
            source_sha256,
            len(parsed),
            args.boundary_mode,
        )
        for idx, chunk in enumerate(raw_chunks, start=1)
    ]

    if args.format == "jsonl":
        write_jsonl(chunks, args.output)
    else:
        write_markdown(chunks, args.output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
