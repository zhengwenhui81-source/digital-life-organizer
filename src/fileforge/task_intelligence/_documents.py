"""Shared validation for contract-shaped task-intelligence input."""

from typing import Any

_STRING_FIELDS = ("file_id", "path", "filename", "extension", "text", "modified_time")


def validate_documents(documents: object) -> str | None:
    if not isinstance(documents, list):
        return "documents must be a list of Documents"
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            return f"documents[{index}] must be a Document object"
        if any(not isinstance(document.get(key), str) for key in _STRING_FIELDS):
            return f"documents[{index}] has missing or invalid string fields"
        if any(not document[key].strip() for key in ("file_id", "path", "filename")):
            return f"documents[{index}] has empty identity/source fields"
        if (
            type(document.get("size")) is not int
            or document["size"] < 0
            or not isinstance(document.get("metadata"), dict)
        ):
            return f"documents[{index}] has invalid size or metadata"
    return None


def _same_snapshot(left: Any, right: Any) -> bool:
    """Compare every supplied field, preserving types and array order."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _same_snapshot(value, right[key]) for key, value in left.items()
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _same_snapshot(a, b) for a, b in zip(left, right, strict=True)
        )
    return left == right


def prepare_documents(documents: object) -> tuple[list[dict[str, Any]], str | None]:
    """Validate the whole original collection, then preserve first equal snapshots.

    These tools currently have no formal quantity/text/serialized-size limits.
    Any future tool-specific resource checks belong before deduplication here;
    compare_versions limits do not apply. References and nested data stay intact.
    No parser receives any Documents until this entire preparation succeeds.
    """
    error = validate_documents(documents)
    if error:
        return [], error
    unique = {}
    try:
        for index, document in enumerate(documents):
            identity = document["file_id"]
            if identity in unique:
                if not _same_snapshot(unique[identity], document):
                    return [], (
                        f"Contradictory Document snapshot for file_id {identity} "
                        f"at documents[{index}]: supplied fields differ"
                    )
            else:
                unique[identity] = document
    except (RecursionError, TypeError, ValueError) as exc:
        return [], f"Invalid Document snapshot comparison: {type(exc).__name__}"
    return list(unique.values()), None
