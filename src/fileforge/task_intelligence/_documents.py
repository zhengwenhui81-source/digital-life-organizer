"""Shared validation for contract-shaped task-intelligence input."""

from math import isfinite
from typing import Any

_STRING_FIELDS = ("file_id", "path", "filename", "extension", "text", "modified_time")


def validate_documents(documents: object) -> str | None:
    if type(documents) is not list:
        return "documents must be a list of Documents"
    for index, document in enumerate(documents):
        if type(document) is not dict:
            return f"documents[{index}] must be a Document object"
        if any(type(document.get(key)) is not str for key in _STRING_FIELDS):
            return f"documents[{index}] has missing or invalid string fields"
        if any(not document[key].strip() for key in ("file_id", "path", "filename")):
            return f"documents[{index}] has empty identity/source fields"
        if (
            type(document.get("size")) is not int
            or document["size"] < 0
            or type(document.get("metadata")) is not dict
        ):
            return f"documents[{index}] has invalid size or metadata"
    return None


def _json_children(value, path):
    if type(value) is dict:
        for key, item in value.items():
            yield item, f"{path}.{key}"
    else:
        for index, item in enumerate(value):
            yield item, f"{path}[{index}]"


def _json_error(documents: object) -> str | None:
    """Walk exact JSON types iteratively; track ancestors, not all visited nodes."""
    active = set()
    stack = [(iter(((documents, "documents"),)), None)]
    while stack:
        children, identity = stack[-1]
        try:
            value, path = next(children)
        except StopIteration:
            stack.pop()
            if identity is not None:
                active.remove(identity)
            continue
        kind = type(value)
        if value is None or (kind is bool or kind is str or kind is int):
            continue
        if kind is float:
            if not isfinite(value):
                return f"{path}: non-finite number is not valid JSON"
            continue
        if kind is not dict and kind is not list:
            return f"{path}: non-JSON value type {kind.__name__}"
        identity = id(value)
        if identity in active:
            return f"{path}: circular reference is not valid JSON"
        if kind is dict:
            if any(type(key) is not str for key in value):
                return f"{path}: JSON object keys must be strings"
        active.add(identity)
        stack.append((iter(_json_children(value, path)), identity))
    return None


def _same_snapshot(left: Any, right: Any) -> bool:
    """Compare validated JSON without recursion or custom equality dispatch."""
    pending = [(left, right)]
    while pending:
        left, right = pending.pop()
        if type(left) is not type(right):
            return False
        if type(left) is dict:
            if left.keys() != right.keys():
                return False
            pending.extend((value, right[key]) for key, value in left.items())
        elif type(left) is list:
            if len(left) != len(right):
                return False
            pending.extend(zip(left, right, strict=True))
        elif left != right:
            return False
    return True


def prepare_documents(documents: object) -> tuple[list[dict[str, Any]], str | None]:
    """Validate the whole original collection, then preserve first equal snapshots.

    These tools currently have no formal quantity/text/serialized-size limits.
    Any future tool-specific resource checks belong before deduplication here;
    compare_versions limits do not apply. References and nested data stay intact.
    No parser receives any Documents until this entire preparation succeeds.
    """
    error = _json_error(documents)
    if not error:
        error = validate_documents(documents)
    if error:
        return [], error
    unique = {}
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
    return list(unique.values()), None
