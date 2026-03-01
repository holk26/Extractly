"""Boilerplate deduplication for multi-page crawl results.

When a domain is crawled, structural elements such as navigation bars,
footers, and cookie banners often survive as text blocks that are identical
across every page.  This module detects those repeated blocks and removes
them from all pages before the content is returned to the caller, reducing
token usage and improving LLM signal-to-noise ratio.
"""

from collections import Counter
from typing import List


# Minimum characters a block must have to be considered for deduplication.
# Very short lines (e.g. a single word) are too common to be reliable signals.
_MIN_BLOCK_LEN = 30


def _split_blocks(text: str) -> List[str]:
    """Split *text* into non-empty paragraph-level blocks."""
    blocks: List[str] = []
    for block in text.split("\n\n"):
        stripped = block.strip()
        if stripped and len(stripped) >= _MIN_BLOCK_LEN:
            blocks.append(stripped)
    return blocks


def remove_boilerplate(
    pages: List[str],
    threshold: float = 0.6,
) -> tuple[List[str], bool]:
    """Detect and remove boilerplate blocks from *pages*.

    A block is considered boilerplate when it appears verbatim in at least
    *threshold* fraction of the pages (minimum 2 pages).

    Args:
        pages:      List of per-page Markdown strings.
        threshold:  Fraction of pages a block must appear in to be pruned
                    (default: 0.6 = 60 %).

    Returns:
        A tuple of:
        - the cleaned page list (same length and order as *pages*)
        - a boolean indicating whether any boilerplate was detected and removed.
    """
    if len(pages) < 2:
        return pages, False

    page_blocks: List[List[str]] = [_split_blocks(p) for p in pages]

    # Count how many *distinct* pages each block appears in
    block_page_counts: Counter = Counter()
    for blocks in page_blocks:
        for block in set(blocks):  # deduplicate within a single page
            block_page_counts[block] += 1

    min_count = max(2, int(len(pages) * threshold))
    boilerplate: set[str] = {
        block for block, count in block_page_counts.items() if count >= min_count
    }

    if not boilerplate:
        return pages, False

    cleaned: List[str] = []
    for page_text, blocks in zip(pages, page_blocks):
        surviving = [b for b in blocks if b not in boilerplate]
        # Re-join surviving blocks; fall back to original text if nothing survives
        cleaned.append("\n\n".join(surviving).strip() if surviving else page_text)

    return cleaned, True
