"""Private filename-matching prototype; not a public tool or frozen schema.

A/B must not depend on this module or its adjustable return structure. Caller
supplies candidate Documents, excluding notices and enforcing workspace scope.
No file roles, aliases, document contents or final versions are inferred.
"""

from __future__ import annotations

import re
from pathlib import PurePath
from typing import Any

from fileforge.task_intelligence._documents import validate_documents

# Unlike upstream extract_version's search, only a terminal suffix is allowed.
_VERSION_SUFFIX = re.compile(r"_v[0-9]+(?:\.[0-9]+){0,2}$")


def _match_materials(
    required_documents: list[str], documents: list[dict[str, Any]]
) -> dict[str, Any]:
    """Return private required/matched/missing data, never a ToolResult.

    Matching is case/whitespace sensitive. Strip only the last filename suffix,
    then compare exactly or remove one explicit terminal _vN[.N[.N]] suffix.
    Requirements are deduplicated exactly. Candidates are deduplicated by the
    original (file_id, path) pair, preserving the first occurrence and order.
    Inconsistent ID/path mappings or filenames for one identity raise ValueError;
    identities are never rewritten or silently reconciled. References are fresh
    dictionaries containing unmodified identity values.
    Missing means unmatched within this input only, not absent from the machine.
    Invalid inputs raise ValueError; no public error contract is introduced.
    """
    if not isinstance(required_documents, list) or any(
        not isinstance(name, str) or not name.strip() for name in required_documents
    ):
        raise ValueError("required_documents must be a list of nonempty strings")
    error = validate_documents(documents)
    if error:
        raise ValueError(error)
    names = list(dict.fromkeys(required_documents))
    candidates = []
    seen = set()
    paths_by_id = {}
    ids_by_path = {}
    filenames_by_identity = {}
    for document in documents:
        filename = document["filename"]
        if "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise ValueError("Document.filename must be a filename, not a path")
        file_id, path = document["file_id"], document["path"]
        identity = (file_id, path)
        if file_id in paths_by_id and paths_by_id[file_id] != path:
            raise ValueError(
                "Inconsistent Document identity: one file_id has multiple paths"
            )
        if path in ids_by_path and ids_by_path[path] != file_id:
            raise ValueError(
                "Inconsistent Document identity: one path has multiple file_ids"
            )
        if (
            identity in filenames_by_identity
            and filenames_by_identity[identity] != filename
        ):
            raise ValueError("Inconsistent Document identity: conflicting filenames")
        paths_by_id[file_id] = path
        ids_by_path[path] = file_id
        filenames_by_identity[identity] = filename
        if identity in seen:
            continue
        seen.add(identity)
        stem = PurePath(filename).stem
        base = _VERSION_SUFFIX.sub("", stem)
        candidates.append((stem, base, document))
    matched, missing = [], []
    for name in names:
        references = [
            {key: document[key] for key in ("file_id", "path", "filename")}
            for stem, base, document in candidates
            if name == stem or name == base
        ]
        if references:
            matched.append({"requirement": name, "documents": references})
        else:
            missing.append(name)
    return {"required_documents": names, "matched": matched, "missing": missing}
