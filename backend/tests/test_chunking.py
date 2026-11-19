import pytest

from app.services.chunking import chunk_markdown
from scripts.seed import DOCUMENTS_DIR, load_documents

DOC = """# Policy

Intro line.

## Booking
Book early.

### Flights
Economy only.

## Approval
Managers approve.
"""


def assert_offsets_match(text, chunks):
    for chunk in chunks:
        assert text[chunk.start_char : chunk.end_char] == chunk.content


def test_each_heading_starts_a_chunk_with_its_heading_path():
    chunks = chunk_markdown(DOC)

    assert [(c.content.splitlines()[0], c.headings) for c in chunks] == [
        ("# Policy", ("Policy",)),
        ("## Booking", ("Policy", "Booking")),
        ("### Flights", ("Policy", "Booking", "Flights")),
        ("## Approval", ("Policy", "Approval")),
    ]
    assert [c.section for c in chunks] == ["Policy", "Booking", "Flights", "Approval"]
    assert [c.index for c in chunks] == [0, 1, 2, 3]
    assert_offsets_match(DOC, chunks)


def test_text_before_the_first_heading_has_no_section():
    text = "Preamble.\n\n# Title\nBody."

    first = chunk_markdown(text)[0]

    assert (first.content, first.section) == ("Preamble.", None)


def test_hash_lines_inside_code_fences_are_not_headings():
    text = "# Title\n```\n# not a heading\n```\nAfter."

    assert len(chunk_markdown(text)) == 1


def test_empty_and_blank_text_give_no_chunks():
    assert chunk_markdown("") == []
    assert chunk_markdown("  \n\n ") == []


def test_long_sections_are_split_with_overlap_and_no_lost_text():
    paragraphs = [f"Paragraph {i} " + "word " * 40 for i in range(20)]
    text = "## Long\n" + "\n\n".join(paragraphs)

    chunks = chunk_markdown(text, max_chars=600, overlap_chars=100)

    assert len(chunks) > 1
    assert all(len(c.content) <= 600 for c in chunks)
    assert all(c.section == "Long" for c in chunks)
    assert_offsets_match(text, chunks)
    for previous, current in zip(chunks, chunks[1:], strict=False):
        assert current.start_char < previous.end_char  # overlaps
        assert current.start_char > previous.start_char  # always moves forward
    # Every non-blank character is in some chunk.
    covered = set()
    for c in chunks:
        covered.update(range(c.start_char, c.end_char))
    assert all(i in covered for i, ch in enumerate(text) if not ch.isspace())


def test_text_without_any_break_is_cut_at_max_chars():
    text = "x" * 2500

    chunks = chunk_markdown(text, max_chars=1000, overlap_chars=100)

    assert [len(c.content) for c in chunks][:2] == [1000, 1000]
    assert_offsets_match(text, chunks)


def test_overlap_must_be_less_than_half_of_max_chars():
    with pytest.raises(ValueError):
        chunk_markdown("text", max_chars=100, overlap_chars=50)


def test_sample_document_chunks_point_at_the_exact_file_text():
    for document in load_documents():
        file_text = (DOCUMENTS_DIR / document.source).read_text(encoding="utf-8")
        chunks = chunk_markdown(document.body)

        assert chunks, document.source
        for chunk in chunks:
            start = document.body_start + chunk.start_char
            end = document.body_start + chunk.end_char
            assert file_text[start:end] == chunk.content
