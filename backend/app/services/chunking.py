"""Split Markdown into chunks that remember exactly where they came from.

Each chunk is one section (a heading and the text under it). A section longer than
`max_chars` is cut at the best nearby break (paragraph, then line, then sentence,
then word), and each piece overlaps the previous one so a sentence near a cut is
not lost. For every chunk, `text[start_char:end_char] == content`, which is what lets
a citation point at the exact source passage.
"""

import re
from dataclasses import dataclass

# About 350 tokens: small enough for precise citations, large enough to keep context.
MAX_CHARS = 1500
OVERLAP_CHARS = 200

_HEADING = re.compile(r" {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*")
_FENCE = re.compile(r" {0,3}(```|~~~)")
_BREAKS = ("\n\n", "\n", ". ", " ")


@dataclass(frozen=True)
class Chunk:
    index: int
    content: str
    start_char: int
    end_char: int
    # Enclosing headings, outermost first.
    headings: tuple[str, ...]

    @property
    def section(self) -> str | None:
        return self.headings[-1] if self.headings else None


def chunk_markdown(
    text: str, max_chars: int = MAX_CHARS, overlap_chars: int = OVERLAP_CHARS
) -> list[Chunk]:
    if not 0 <= overlap_chars < max_chars // 2:
        raise ValueError("overlap_chars must be at least 0 and less than half of max_chars")

    chunks: list[Chunk] = []
    for start, end, headings in _sections(text):
        for piece_start, piece_end in _split(text, start, end, max_chars, overlap_chars):
            chunks.append(
                Chunk(
                    index=len(chunks),
                    content=text[piece_start:piece_end],
                    start_char=piece_start,
                    end_char=piece_end,
                    headings=headings,
                )
            )
    return chunks


def _sections(text: str) -> list[tuple[int, int, tuple[str, ...]]]:
    """(start, end, headings) for each heading's section, plus any text before the first."""
    sections: list[tuple[int, int, tuple[str, ...]]] = []
    stack: list[tuple[int, str]] = []  # (level, heading text)
    section_start = 0
    in_fence = False
    position = 0
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if _FENCE.match(bare):
            in_fence = not in_fence
        elif not in_fence and (match := _HEADING.fullmatch(bare)):
            sections.append((section_start, position, tuple(title for _, title in stack)))
            level = len(match.group(1))
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, match.group(2)))
            section_start = position
        position += len(line)
    sections.append((section_start, len(text), tuple(title for _, title in stack)))
    return sections


def _split(
    text: str, start: int, end: int, max_chars: int, overlap_chars: int
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start, end = _trim(text, start, end)
    while start < end:
        if end - start <= max_chars:
            spans.append((start, end))
            break

        limit = start + max_chars
        cut = limit
        for separator in _BREAKS:
            # Only accept breaks in the second half, so pieces do not get too small.
            found = text.rfind(separator, start + max_chars // 2, limit)
            if found != -1:
                cut = found + len(separator)
                break
        spans.append(_trim(text, start, cut))

        # Start the next piece a little before the cut, at the beginning of a word.
        next_start = cut - overlap_chars
        while next_start < cut and not text[next_start - 1].isspace():
            next_start += 1
        start, end = _trim(text, next_start, end)
    return spans


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end
