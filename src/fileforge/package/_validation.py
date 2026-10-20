"""Structure/reference consistency using reviewed D JSON and identity rules.

Equality of supplied references/Documents is not evidence freshness. No input
binds those analysis results to raw file bytes; current planning hashes cannot
retroactively supply historical binding. A owns the confirmed v1 current
consistency handoff; this module does not perform it or read files.
"""

from fileforge.task_intelligence._documents import (
    _json_error,
    _same_snapshot,
    prepare_documents,
)

TOOLS = (
    "extract_requirements",
    "match_requirements",
    "detect_conflicts",
    "compare_versions",
)
REF = ("file_id", "path", "filename")


def exact(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f"{label} must have exactly {keys}")


def text(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def names(value, label):
    if type(value) is not list:
        raise ValueError(f"{label} must be a string array")
    for item in value:
        text(item, label)
    return list(dict.fromkeys(value))


def reference(value):
    exact(value, REF, "source reference")
    for key in REF:
        text(value[key], key)
    return value


def validate(task, selected, analysis, destination):
    error = _json_error(
        dict(
            task=task,
            selected_files=selected,
            analysis=analysis,
            destination=destination,
        )
    )
    if error:
        raise ValueError(error)
    exact(task, ("task_id", "user_goal", "workspace"), "task")
    for key, value in task.items():
        text(value, key)
    exact(analysis, TOOLS, "analysis")
    references = {}
    full = []

    def register(ref):
        reference(ref)
        identity = ref["file_id"]
        if identity in references and not _same_snapshot(references[identity], ref):
            raise ValueError(f"Contradictory source reference: {identity}")
        references[identity] = ref

    indices = set()
    for tool, slot in analysis.items():
        if slot is None:
            continue
        exact(slot, ("result_index", "result"), tool)
        index = slot["result_index"]
        if type(index) is not int or index < 0 or index in indices:
            raise ValueError(
                "Analysis result_index must be distinct nonnegative integers"
            )
        indices.add(index)
        r = slot["result"]
        exact(r, ("success", "tool", "data", "message", "error"), "ToolResult")
        if (
            type(r["success"]) is not bool
            or r["tool"] != tool
            or type(r["message"]) is not str
        ):
            raise ValueError("Invalid analysis ToolResult")
        if not r["success"]:
            raise ValueError(
                f"Upstream tool failed: {tool}; no executable Package plan"
            )
        if r["error"] is not None:
            raise ValueError("Successful analysis must have error=null")
        data = r["data"]
        if tool == "extract_requirements":
            exact(data, ("required_documents",), tool)
            names(data["required_documents"], tool)
        elif tool == "match_requirements":
            exact(data, ("required_documents", "matched", "missing"), tool)
            req = names(data["required_documents"], tool)
            missing = names(data["missing"], tool)
            if (
                req != data["required_documents"]
                or missing != data["missing"]
                or type(data["matched"]) is not list
            ):
                raise ValueError("Matching output must be stably deduplicated arrays")
            matched = []
            for group in data["matched"]:
                exact(group, ("requirement", "documents"), "matched group")
                text(group["requirement"], "requirement")
                if type(group["documents"]) is not list or not group["documents"]:
                    raise ValueError("Matched documents must be nonempty")
                seen = set()
                for ref in group["documents"]:
                    register(ref)
                    if ref["file_id"] in seen:
                        raise ValueError("Duplicate matched identity")
                    seen.add(ref["file_id"])
                matched.append(group["requirement"])
            if (
                len(set(matched)) != len(matched)
                or set(matched) & set(missing)
                or set(matched) | set(missing) != set(req)
                or matched != [x for x in req if x in matched]
                or missing != [x for x in req if x in missing]
            ):
                raise ValueError("Matching partition/order is inconsistent")
        elif tool == "detect_conflicts":
            exact(data, ("conflicts",), tool)
            if type(data["conflicts"]) is not list:
                raise ValueError("conflicts must be an array")
            for conflict in data["conflicts"]:
                if type(conflict) is not dict or set(conflict) not in (
                    {"field", "values"},
                    {"field", "values", "recommendation"},
                ):
                    raise ValueError("Invalid conflict record")
                if "recommendation" in conflict:
                    text(conflict["recommendation"], "recommendation")
                text(conflict["field"], "field")
                if type(conflict["values"]) is not list or len(conflict["values"]) < 2:
                    raise ValueError("Conflict needs multiple values")
                for value in conflict["values"]:
                    exact(value, ("value", "source"), "conflict value")
                    text(value["value"], "value")
                    text(value["source"], "source")
        else:
            exact(data, ("groups",), tool)
            if type(data["groups"]) is not list:
                raise ValueError("groups must be an array")
            for group in data["groups"]:
                exact(
                    group,
                    (
                        "group_id",
                        "documents",
                        "grouping",
                        "recommendation_reason",
                        "comparison_order",
                        "newest_candidate",
                        "changes",
                    ),
                    "Version group",
                )
                text(group["group_id"], "group_id")
                if type(group["documents"]) is not list or not group["documents"]:
                    raise ValueError("Version documents must be nonempty")
                full.extend(group["documents"])
                for doc in group["documents"]:
                    if type(doc) is not dict:
                        raise ValueError("Version document must be an object")
                    register({k: doc.get(k) for k in REF})
                candidate = group["newest_candidate"]
                if candidate is not None:
                    exact(candidate, (*REF, "reasons"), "newest_candidate")
                    ref = {k: candidate[k] for k in REF}
                    register(ref)
                    if ref not in [{k: d[k] for k in REF} for d in group["documents"]]:
                        raise ValueError(
                            "Version recommendation must reference a member"
                        )
                    names(candidate["reasons"], "reasons")
                if type(group["changes"]) is not list:
                    raise ValueError("changes must be an array")
                for change in group["changes"]:
                    exact(
                        change,
                        ("from", "to", "type", "before", "after", "summary"),
                        "Version change",
                    )
                    for side in ("from", "to"):
                        register(change[side])
                        if change[side] not in [
                            {k: d[k] for k in REF} for d in group["documents"]
                        ]:
                            raise ValueError(
                                "Version change must reference a group member"
                            )
                    if change["type"] not in (
                        "insert",
                        "delete",
                        "replace",
                        "identical",
                    ):
                        raise ValueError("Invalid Version change type")
                    text(change["summary"], "change summary")
                    for side in ("before", "after"):
                        location = change[side]
                        if location is not None:
                            exact(
                                location,
                                ("start_line", "end_line", "text"),
                                "Version location",
                            )
                            if (
                                type(location["start_line"]) is not int
                                or type(location["end_line"]) is not int
                                or location["start_line"] < 1
                                or location["end_line"] < location["start_line"]
                                or type(location["text"]) is not str
                            ):
                                raise ValueError("Invalid Version line location")
                exact(
                    group["grouping"],
                    (
                        "basis",
                        "normalized_name",
                        "similarity_method",
                        "minimum_pair_similarity",
                    ),
                    "Version grouping",
                )
                for key in ("basis", "normalized_name", "similarity_method"):
                    text(group["grouping"][key], key)
                score = group["grouping"]["minimum_pair_similarity"]
                if (
                    score is not None
                    and type(score) is not int
                    and type(score) is not float
                ):
                    raise ValueError("Invalid Version similarity")
                exact(
                    group["comparison_order"],
                    ("basis", "tie_breaker", "chronology_confirmed"),
                    "Version comparison order",
                )
                text(group["comparison_order"]["basis"], "comparison basis")
                text(group["comparison_order"]["tie_breaker"], "tie breaker")
                if group["comparison_order"]["chronology_confirmed"] is not False:
                    raise ValueError(
                        "Version order must not claim confirmed chronology"
                    )
                text(group["recommendation_reason"], "recommendation_reason")
    _, error = prepare_documents(full)
    if error:
        raise ValueError(error)
    extraction = analysis["extract_requirements"]
    matching = analysis["match_requirements"]
    if matching and (
        not extraction
        or matching["result"]["data"]["required_documents"]
        != names(extraction["result"]["data"]["required_documents"], "requirements")
    ):
        raise ValueError("Matching requires the same effective extraction requirements")
    if type(selected) is not list or not selected:
        raise ValueError("selected_files must be nonempty")
    unique = {}
    for item in selected:
        exact(item, ("source", "requirements", "reason"), "selected_files entry")
        register(item["source"])
        text(item["reason"], "reason")
        req = names(item["requirements"], "requirements")
        if extraction and not set(req) <= set(
            extraction["result"]["data"]["required_documents"]
        ):
            raise ValueError("Selection requirements are outside extracted checklist")
        identity = item["source"]["file_id"]
        if identity in unique and not _same_snapshot(unique[identity], item):
            raise ValueError(f"Contradictory selected record: {identity}")
        unique.setdefault(identity, item)
    return list(unique.values())
