"""
log_normalizer.py

Compares two log lines while ignoring variable substitutions (player
names, ids, pointers, timestamps, counters) so that two occurrences of
the same loghash -- but with different player/card/league/member ids --
are still recognized as "the same context".

Approach:
  1. Mask known variable patterns (regex-based) to build a normalized
     "template" of each line.
  2. If both normalized templates match exactly, the contexts are
     considered the same (highest confidence).
  3. If not, fall back to a fuzzy similarity ratio (difflib) as a
     safety net for variable patterns the regexes didn't anticipate.

No LLM involved, per requirements.
"""

import difflib
import re

# Order matters: mask more specific patterns before generic digit runs.
_MASK_PATTERNS = [
    # Timestamps like 2026/09/15-10:22:57.332Z or 2026-09-15T10:22:57.332Z
    (re.compile(r"\d{4}[/-]\d{2}[/-]\d{2}[T-]\d{2}:\d{2}:\d{2}\.\d+Z?"), "<TS>"),
    # Memory addresses like 0x7f9705551f70
    (re.compile(r"0x[0-9a-fA-F]+"), "<PTR>"),
    # The trace-id triple block, e.g. [0000000000000000/0000000000000000/00000000000000000000]
    (re.compile(r"\[[0-9a-fA-F]{16}/[0-9a-fA-F]{16}/\d{20}\]"), "<TRACEID>"),
    # Loghash-style tokens anywhere in the line, e.g. [46c094de:00c2]
    (re.compile(r"\[[0-9a-fA-F]+:[0-9a-fA-F]+\]"), "<HASH>"),
    # Player-name patterns like "on WR K.Davis" / "on QB C.Miller"
    (re.compile(r"\bon [A-Z]{1,4} [A-Z]\.[A-Za-z'\-]+"), "on <PLAYER>"),
    # Any other bracketed numeric id, e.g. [2922315], [1102089651706]
    (re.compile(r"\[\d+\]"), "<ID>"),
    # Any remaining standalone digit run (durations, counts, dates, ids)
    (re.compile(r"\b\d+\b"), "<NUM>"),
]

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_line(line: str) -> str:
    normalized = line
    for pattern, replacement in _MASK_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def normalize_block(lines: list) -> str:
    return "\n".join(normalize_line(line) for line in lines)


def similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def classify_context_match(
    sample_1: str,
    before_1: list,
    after_1: list,
    sample_2: str,
    before_2: list,
    after_2: list,
    fuzzy_threshold: float = 0.9,
) -> dict:
    """
    Returns:
      {
        "same_context": bool,               # requires BOTH the triggering
                                              # line AND the 5-before lines
                                              # to match
        "verdict_reason": str,
        "matched_line_similarity": float,
        "before_context_similarity": float,
        "full_context_similarity": float,
      }
    """
    norm_sample_1 = normalize_line(sample_1)
    norm_sample_2 = normalize_line(sample_2)

    if norm_sample_1 == norm_sample_2:
        line_match = True
        matched_line_similarity = 1.0
    else:
        matched_line_similarity = similarity(norm_sample_1, norm_sample_2)
        line_match = matched_line_similarity >= fuzzy_threshold

    norm_before_1 = normalize_block(before_1)
    norm_before_2 = normalize_block(before_2)

    if norm_before_1 == norm_before_2:
        before_match = True
        before_context_similarity = 1.0
    else:
        before_context_similarity = similarity(norm_before_1, norm_before_2)
        before_match = before_context_similarity >= fuzzy_threshold

    same_context = line_match and before_match

    if line_match and before_match:
        verdict_reason = "triggering line and 5-before context both match (after masking)"
    elif line_match and not before_match:
        verdict_reason = (
            f"triggering line matches, but 5-before context differs "
            f"({before_context_similarity:.0%} similar)"
        )
    elif before_match and not line_match:
        verdict_reason = (
            f"5-before context matches, but triggering line differs "
            f"({matched_line_similarity:.0%} similar)"
        )
    else:
        verdict_reason = (
            f"different (line {matched_line_similarity:.0%}, "
            f"5-before context {before_context_similarity:.0%} similar)"
        )

    full_block_1 = normalize_block(before_1 + [sample_1] + after_1)
    full_block_2 = normalize_block(before_2 + [sample_2] + after_2)
    full_context_similarity = similarity(full_block_1, full_block_2)

    return {
        "same_context": same_context,
        "verdict_reason": verdict_reason,
        "matched_line_similarity": matched_line_similarity,
        "before_context_similarity": before_context_similarity,
        "full_context_similarity": full_context_similarity,
    }
