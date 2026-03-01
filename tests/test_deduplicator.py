"""Tests for app.services.deduplicator.remove_boilerplate."""

from app.services.deduplicator import remove_boilerplate, _split_blocks


class TestSplitBlocks:
    def test_splits_on_double_newline(self):
        text = (
            "Block one has enough characters to pass the minimum length.\n\n"
            "Block two has enough characters to pass the minimum length.\n\n"
            "Block three has enough characters to pass the minimum length."
        )
        blocks = _split_blocks(text)
        assert len(blocks) == 3

    def test_ignores_short_blocks(self):
        text = "Hi\n\nThis is a longer block that meets the minimum length."
        blocks = _split_blocks(text)
        assert "Hi" not in blocks  # too short

    def test_strips_whitespace_around_blocks(self):
        text = "  Hello, this is a block with enough characters.  \n\n  Another block here.  "
        blocks = _split_blocks(text)
        assert all(b == b.strip() for b in blocks)

    def test_empty_string_returns_empty(self):
        assert _split_blocks("") == []


class TestRemoveBoilerplate:
    def test_single_page_unchanged(self):
        pages = ["Only one page, no deduplication possible here."]
        result, removed = remove_boilerplate(pages)
        assert result == pages
        assert removed is False

    def test_no_repeated_blocks_unchanged(self):
        pages = [
            "This is unique content for page one with enough text to qualify.",
            "This is unique content for page two with enough text to qualify.",
            "This is unique content for page three with enough text to qualify.",
        ]
        result, removed = remove_boilerplate(pages)
        assert removed is False

    def test_detects_and_removes_repeated_block(self):
        footer = "Copyright 2024 Example Company. All rights reserved worldwide."
        pages = [
            f"Page one content that is unique to this specific page.\n\n{footer}",
            f"Page two content that is unique to this specific page.\n\n{footer}",
            f"Page three content that is unique to this specific page.\n\n{footer}",
        ]
        result, removed = remove_boilerplate(pages, threshold=0.6)
        assert removed is True
        for page in result:
            assert footer not in page

    def test_preserves_unique_content(self):
        footer = "Copyright 2024 Example Company. All rights reserved worldwide."
        unique = [
            "Unique article about machine learning algorithms and applications.",
            "Unique article about web development frameworks and libraries.",
            "Unique article about data science and statistical modelling.",
        ]
        pages = [f"{u}\n\n{footer}" for u in unique]
        result, removed = remove_boilerplate(pages, threshold=0.6)
        assert removed is True
        for i, page in enumerate(result):
            assert unique[i] in page

    def test_repeated_block_below_threshold_kept(self):
        repeated = "This block repeats only on some pages but not most of them."
        pages = [
            f"First page unique content that is different from all other pages.\n\n{repeated}",
            f"Second page unique content that is different from all other pages.\n\n{repeated}",
            "Third page unique content that is different from all other pages.",
            "Fourth page unique content that is different from all other pages.",
            "Fifth page unique content that is different from all other pages.",
        ]
        # threshold=0.6 means block must appear in >= 3 pages; this one appears in 2/5
        result, removed = remove_boilerplate(pages, threshold=0.6)
        assert removed is False

    def test_empty_pages_list_unchanged(self):
        result, removed = remove_boilerplate([])
        assert result == []
        assert removed is False

    def test_returns_same_length(self):
        footer = "This is a boilerplate footer text that appears on every single page."
        pages = [
            f"Content for page {i}. Unique text that varies per page.\n\n{footer}"
            for i in range(5)
        ]
        result, removed = remove_boilerplate(pages)
        assert len(result) == len(pages)
