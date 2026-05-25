from . import db
from .frequency import FREQUENCY_LIST


def missing_words(top: int = 20) -> list[tuple[int, str]]:
    """
    Return the top N most common English words that are missing from the library.

    Returns:
        List of (frequency_rank, word) tuples, sorted by frequency (most common first).
    """
    existing = set(db.get_all_words())
    result = []
    for rank, word in enumerate(FREQUENCY_LIST, start=1):
        if word not in existing:
            result.append((rank, word))
        if len(result) >= top:
            break
    return result


def coverage_stats() -> dict:
    """
    Return coverage statistics for the frequency list.
    """
    existing = set(db.get_all_words())
    total_freq = len(FREQUENCY_LIST)
    covered = sum(1 for w in FREQUENCY_LIST if w in existing)
    return {
        "total_in_frequency_list": total_freq,
        "covered": covered,
        "missing": total_freq - covered,
        "coverage_pct": round(100 * covered / total_freq, 1) if total_freq else 0,
    }


def suggest_targets(top: int = 20) -> str:
    """Pretty-print suggestions for which words to target next."""
    missing = missing_words(top)
    stats = coverage_stats()
    lines = [
        f"Word library coverage: {stats['coverage_pct']}% "
        f"({stats['covered']}/{stats['total_in_frequency_list']} common words)",
        f"Total unique words in library: {len(db.get_all_words())}",
        f"Total clips: {db.get_stats()['total_clips']}",
        "",
        f"--- Top {top} missing words (by frequency) ---",
    ]
    for rank, word in missing:
        lines.append(f"  #{rank:4d}  {word}")
    return "\n".join(lines)
