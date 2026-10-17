"""Internal sentence boundaries that retain qualifiers before comma splitting."""

from __future__ import annotations

import re
from collections.abc import Iterator

_CONDITION = re.compile(
    r"如果|如|若|只有|仅当|仅在|只要|除非|一旦|假设|视情况|根据"
    r"|(?:当|在)[^，,。；;\n]{0,80}(?:时|情况下|条件下)"
)


def _join_continuations(text: str) -> str:
    """A newline immediately after a comma does not end its qualifier's scope."""
    return re.sub(r"([，,])[ \t]*\r?\n[ \t]*", r"\1", text)


def _unconditional_sentences(text: str) -> Iterator[str]:
    """Reject a qualified sentence BEFORE exposing any comma-delimited claim.

    Strong punctuation/newlines delimit independent assertions, not commas.
    No complete natural-language condition or cross-paragraph scope is inferred.
    """
    for sentence in re.split(r"[。；;！？!?\r\n]", _join_continuations(text)):
        sentence = sentence.strip()
        if sentence and not _CONDITION.search(sentence):
            yield sentence
