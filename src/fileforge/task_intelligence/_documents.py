"""Shared validation for contract-shaped task-intelligence input."""

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
