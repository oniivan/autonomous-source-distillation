"""Parse and compare the line component of native evidence locators."""

from __future__ import annotations

import re
from collections.abc import Iterable


LINE_RANGE_RE = re.compile(
    r"\blines?\s+(\d+)(?:\s*(?:-|\u2013|\u2014|to)\s*(\d+))?\b",
    re.IGNORECASE,
)


def parse_line_ranges(locator: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in LINE_RANGE_RE.finditer(locator):
        start = int(match.group(1))
        end = int(match.group(2) or start)
        ranges.append((start, end))
    return ranges


def exact_line_set(locator: str, expected_lines: Iterable[int]) -> bool:
    expected = set(expected_lines)
    observed: set[int] = set()
    for start, end in parse_line_ranges(locator):
        if start < 1 or end < start or end - start > 10_000:
            return False
        observed.update(range(start, end + 1))
    return observed == expected
