"""Provisional encodings: see docs/task-intelligence-interface-proposal.md.

These details await A/B/C agreement; they are not a frozen shared contract.
"""


def deadline_field(scope: str) -> str:
    return "deadline" if not scope else f"deadline:{scope}"


def material_field(material: str) -> str:
    return f"required_documents:{material}"


def material_value(required: bool) -> str:
    return "required" if required else "not_required"


def source_path(document: dict) -> str:
    return document["path"]
