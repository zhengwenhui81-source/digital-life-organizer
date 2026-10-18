"""Read-only filename candidate relationships; never material approval."""

from __future__ import annotations

import re
from typing import Any

from fileforge.task_intelligence._documents import prepare_documents

_VERSION_SUFFIX = re.compile(r"_v[0-9]+(?:\.[0-9]+){0,2}\Z")
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _failure(error: str) -> dict[str, Any]:
    return {
        "success": False,
        "tool": "match_requirements",
        "data": None,
        "message": "Requirement candidate matching failed",
        "error": error,
    }


def _filename_parts(filename: str) -> tuple[str, str]:
    prefix, dot, suffix = filename.rpartition(".")
    return (prefix, dot + suffix) if prefix and suffix else (filename, "")


def _validate_candidates(documents: list[dict[str, Any]]) -> str | None:
    """Check matching-specific fields using original input positions."""
    for index, document in enumerate(documents):
        filename = document["filename"]
        if (
            not filename.strip()
            or "/" in filename
            or "\\" in filename
            or not filename.strip(".")
            or filename.endswith(".")
        ):
            return f"candidate_documents[{index}].filename is invalid"
        stem, extension = _filename_parts(filename)
        if not stem.strip("."):
            return f"candidate_documents[{index}].filename has all-dot stem"
        if document["extension"].translate(_ASCII_LOWER) != extension.translate(
            _ASCII_LOWER
        ):
            return f"candidate_documents[{index}].extension does not match filename"
    return None


def match_requirements(
    required_documents: list[str], candidate_documents: list[dict[str, Any]]
) -> dict[str, Any]:
    """Associate every requirement independently with all filename candidates.

    Caller owns Workspace authorization, successful reads and notice exclusion.
    Missing means no filename candidate in this input, not material absence.
    No content review, version choice, filesystem access or resource quota is
    implied. Validate all original inputs, including for empty requirements.
    """
    if type(required_documents) is not list:
        return _failure("required_documents must be a list of nonempty strings")
    for index, name in enumerate(required_documents):
        if type(name) is not str or not name.strip():
            return _failure(f"required_documents[{index}] must be a nonempty string")
    documents, error = prepare_documents(
        candidate_documents, validate_raw=_validate_candidates
    )
    if error:
        return _failure(f"candidate_documents: {error}")
    candidates = []
    for document in documents:
        stem, _ = _filename_parts(document["filename"])
        candidates.append((stem, _VERSION_SUFFIX.sub("", stem), document))
    names = list(dict.fromkeys(required_documents))
    matched, missing = [], []
    for name in names:
        references = [
            {key: doc[key] for key in ("file_id", "path", "filename")}
            for stem, base, doc in candidates
            if name == stem or (base and name == base)
        ]
        if references:
            matched.append({"requirement": name, "documents": references})
        else:
            missing.append(name)
    return {
        "success": True,
        "tool": "match_requirements",
        "data": {
            "required_documents": names,
            "matched": matched,
            "missing": missing,
        },
        "message": "Requirement candidate matching completed",
        "error": None,
    }
