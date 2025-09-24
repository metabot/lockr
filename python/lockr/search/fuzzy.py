"""
FZF-like fuzzy matching implementation for Lockr.

This module implements fuzzy string matching similar to fzf, with scoring
based on character position, consecutive matches, and other factors.
"""

from typing import List, Tuple, Optional, NamedTuple
import math


class MatchResult(NamedTuple):
    """Result of a fuzzy match."""
    text: str
    score: float
    positions: List[int]  # Character positions that matched


def fuzzy_match(pattern: str, text: str, case_sensitive: bool = False) -> Optional[MatchResult]:
    """
    Perform fuzzy matching between pattern and text.

    This implements FZF-like scoring with the following rules:
    - Consecutive character matches get higher scores
    - Matches at word boundaries get bonuses
    - Earlier matches get higher scores
    - Case-insensitive by default

    Args:
        pattern: The search pattern
        text: The text to match against
        case_sensitive: Whether matching should be case sensitive

    Returns:
        MatchResult if pattern matches text, None otherwise
    """
    if not pattern:
        return MatchResult(text, 0.0, [])

    if not case_sensitive:
        pattern = pattern.lower()
        search_text = text.lower()
    else:
        search_text = text

    # Find all character matches
    positions = []
    pattern_idx = 0

    for text_idx, char in enumerate(search_text):
        if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
            positions.append(text_idx)
            pattern_idx += 1

    # If we didn't match all pattern characters, no match
    if pattern_idx < len(pattern):
        return None

    # Calculate score based on match quality
    score = _calculate_score(pattern, text, positions, case_sensitive)

    return MatchResult(text, score, positions)


def _calculate_score(pattern: str, text: str, positions: List[int], case_sensitive: bool) -> float:
    """
    Calculate fuzzy match score based on FZF algorithm.

    Higher scores are better. The scoring considers:
    - Length bonus: shorter strings with matches score higher
    - Consecutive bonus: consecutive character matches
    - Word boundary bonus: matches at start of words
    - First character bonus: matches at beginning of string
    - Camel case bonus: matches at uppercase letters in camelCase
    """
    if not positions:
        return 0.0

    score = 0.0
    prev_pos = -1
    consecutive_count = 0

    # Base score - higher for shorter strings
    score += 1.0 / len(text)

    for i, pos in enumerate(positions):
        char = text[pos]

        # First character bonus
        if pos == 0:
            score += 0.8

        # Word boundary bonus (after space, underscore, or dash)
        elif pos > 0 and text[pos - 1] in ' _-':
            score += 0.7

        # Camel case bonus (uppercase after lowercase)
        elif pos > 0 and text[pos - 1].islower() and char.isupper():
            score += 0.6

        # Consecutive character bonus
        if prev_pos >= 0 and pos == prev_pos + 1:
            consecutive_count += 1
            score += 0.15 * consecutive_count  # Increasing bonus for longer sequences
        else:
            consecutive_count = 0

        # Earlier matches get higher scores
        position_penalty = pos / len(text)
        score -= position_penalty * 0.1

        prev_pos = pos

    # Bonus for matching a higher percentage of the pattern
    coverage = len(positions) / len(text)
    score += coverage * 0.5

    # Exact match bonus
    if not case_sensitive:
        if pattern.lower() == text.lower():
            score += 2.0
        elif text.lower().startswith(pattern.lower()):
            score += 1.0
    else:
        if pattern == text:
            score += 2.0
        elif text.startswith(pattern):
            score += 1.0

    return score


def fuzzy_search(pattern: str, candidates: List[str], limit: int = 100,
                case_sensitive: bool = False) -> List[MatchResult]:
    """
    Perform fuzzy search across multiple candidates.

    Args:
        pattern: The search pattern
        candidates: List of strings to search through
        limit: Maximum number of results to return
        case_sensitive: Whether matching should be case sensitive

    Returns:
        List of MatchResult objects sorted by score (best first)
    """
    if not pattern:
        # Return all candidates with zero scores if no pattern
        results = [MatchResult(text, 0.0, []) for text in candidates[:limit]]
        return results

    results = []

    for candidate in candidates:
        match_result = fuzzy_match(pattern, candidate, case_sensitive)
        if match_result:
            results.append(match_result)

    # Sort by score (highest first), then by length (shorter first), then alphabetically
    results.sort(key=lambda x: (-x.score, len(x.text), x.text.lower()))

    return results[:limit]


def highlight_matches(text: str, positions: List[int],
                     start_marker: str = "\033[1m\033[33m",  # Bold yellow
                     end_marker: str = "\033[0m") -> str:
    """
    Highlight matched characters in text using ANSI color codes.

    Args:
        text: The text to highlight
        positions: List of character positions to highlight
        start_marker: ANSI code to start highlighting
        end_marker: ANSI code to end highlighting

    Returns:
        Text with highlighted matches
    """
    if not positions:
        return text

    result = []
    last_pos = 0

    # Sort positions to handle them in order
    sorted_positions = sorted(set(positions))

    for pos in sorted_positions:
        if pos < len(text):
            # Add text before the match
            result.append(text[last_pos:pos])
            # Add highlighted character
            result.append(f"{start_marker}{text[pos]}{end_marker}")
            last_pos = pos + 1

    # Add remaining text
    result.append(text[last_pos:])

    return ''.join(result)