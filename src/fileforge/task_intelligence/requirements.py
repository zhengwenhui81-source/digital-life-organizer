"""Read-only requirement extraction from contract-shaped Documents."""

from __future__ import annotations

from typing import Any

from fileforge.task_intelligence._documents import prepare_documents
from fileforge.task_intelligence._encoding import source_path
from fileforge.task_intelligence._materials import parse_material_evidence


def extract_requirements(documents: list[dict[str, Any]]) -> dict[str, Any]:
    """Return first-seen mandatory names; negatives never erase positive evidence.

    Contradictions are reported separately by detect_conflicts. The caller owns
    task/workspace scoping. This tool only consumes the supplied Document text.
    """
    documents, error = prepare_documents(documents)
    if error:
        return {
            "success": False,
            "tool": "extract_requirements",
            "data": None,
            "message": "Requirement extraction failed",
            "error": error,
        }
    required_documents = []
    seen = set()
    for document in documents:
        for evidence in parse_material_evidence(
            document["text"], source_path(document)
        ):
            if evidence.required and evidence.material not in seen:
                seen.add(evidence.material)
                required_documents.append(evidence.material)
    return {
        "success": True,
        "tool": "extract_requirements",
        "data": {"required_documents": required_documents},
        "message": "Requirement extraction completed",
        "error": None,
    }
