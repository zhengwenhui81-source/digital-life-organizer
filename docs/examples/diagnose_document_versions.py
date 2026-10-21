"""Read-only public-tool diagnostics, not Agent/LLM execution or approval evidence.

Pass explicit file paths. JSON summaries omit extracted text and change excerpts.
Save diagnostic output outside the Workspace being scanned.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from fileforge.document import compare_versions, read_document


def _fingerprint(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    info = path.stat()
    return {
        "sha256": digest.hexdigest(),
        "size": info.st_size,
        "mtime_ns": info.st_mtime_ns,
    }


def diagnose(paths: list[Path]) -> dict:
    """Pass complete successful Documents, preserving the requested input order."""
    reads, documents, observations = [], [], []
    for index, path in enumerate(paths):
        try:
            before = _fingerprint(path)
        except OSError:
            before = None
        result = read_document(str(path))
        row = {
            "input_index": index,
            "filename": path.name,
            "read_success": result["success"],
            "error": result["error"],
            "file_sha256": before["sha256"] if before else None,
        }
        if result["success"]:
            document = result["data"]["document"]
            documents.append(document)
            row.update(
                file_id=document["file_id"],
                text_chars=len(document["text"]),
                text_sha256=hashlib.sha256(
                    document["text"].encode("utf-8")
                ).hexdigest(),
            )
        reads.append(row)
        observations.append((path, before))
    stable = True
    for path, before in observations:
        try:
            stable = before is not None and _fingerprint(path) == before and stable
        except OSError:
            stable = False
    output = {
        "mode": "direct public tools; not historical Agent arguments",
        "reads": reads,
        "source_observations_unchanged": stable,
        "compare_called": False,
        "compare_success": None,
        "error": None,
        "groups": [],
        "recommendation_scope": "group only; not final material selection",
    }
    if any(not row["read_success"] for row in reads):
        output["error"] = (
            "Read failure; comparison not run; no file was silently skipped"
        )
        return output
    if observations and not stable:
        output["error"] = (
            "Source observation changed or is unavailable; comparison not run"
        )
        return output
    result = compare_versions(documents)
    output.update(
        compare_called=True,
        compare_success=result["success"],
        error=result["error"],
        compare_input_order=[d["filename"] for d in documents],
    )
    if result["success"]:
        output["groups"] = [
            {
                "documents": [
                    {k: d[k] for k in ("file_id", "filename")}
                    for d in group["documents"]
                ],
                "candidate": (
                    {k: group["newest_candidate"][k] for k in ("file_id", "filename")}
                    if group["newest_candidate"]
                    else None
                ),
                "reason": group["recommendation_reason"],
                "minimum_pair_similarity": group["grouping"]["minimum_pair_similarity"],
                "change_types": [change["type"] for change in group["changes"]],
            }
            for group in result["data"]["groups"]
        ]
    for path, before in observations:
        try:
            if _fingerprint(path) != before:
                output["source_observations_unchanged"] = False
        except OSError:
            output["source_observations_unchanged"] = False
    return output


def inspect_snapshot(snapshot: dict, expected_filenames: list[str]) -> dict:
    """Inspect an exported Snapshot, never infer unrecorded runtime arguments."""
    if not isinstance(snapshot, dict):
        raise ValueError("Snapshot must be an object")
    results = snapshot.get("results")
    if not isinstance(results, list):
        raise ValueError("Snapshot.results must be an array")
    index = next(
        (
            i
            for i in range(len(results) - 1, -1, -1)
            if isinstance(results[i], dict)
            and results[i].get("tool") == "compare_versions"
        ),
        None,
    )
    if index is None:
        raise ValueError(
            "No compare_versions result; historical comparison not established"
        )
    collection = max(
        (
            i
            for i, r in enumerate(results[:index])
            if isinstance(r, dict) and r.get("tool") in {"list_files", "search_files"}
        ),
        default=-1,
    )
    reads = [
        r["data"]["document"]
        for r in results[collection + 1 : index]
        if isinstance(r, dict)
        and r.get("tool") == "read_document"
        and r.get("success") is True
        and isinstance(r.get("data"), dict)
        and isinstance(r["data"].get("document"), dict)
    ]
    result = results[index]
    compared = []
    if result.get("success") is True:
        data = result.get("data")
        if not isinstance(data, dict):
            raise ValueError("Successful comparison data must be an object")
        groups = data.get("groups")
        if not isinstance(groups, list):
            raise ValueError("Successful comparison has no groups array")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(
                group.get("documents"), list
            ):
                raise ValueError("Comparison group documents are invalid")
            if any(not isinstance(d, dict) for d in group["documents"]):
                raise ValueError("Comparison contains an invalid Document")
            compared.extend(group["documents"])

    def fingerprint(document):
        return json.dumps(document, ensure_ascii=False, sort_keys=True, allow_nan=False)

    read_names = {d.get("filename") for d in reads}
    compared_names = {d.get("filename") for d in compared}
    prior = {fingerprint(d) for d in reads}
    return {
        "mode": "exported Snapshot evidence; not a runtime argument log",
        "task_id": snapshot.get("task", {}).get("task_id"),
        "comparison_result_index": index,
        "compare_success": result.get("success") is True,
        "failed_read_before_comparison": any(
            isinstance(r, dict)
            and r.get("tool") == "read_document"
            and r.get("success") is False
            for r in results[collection + 1 : index]
        ),
        "error": result.get("error"),
        "successful_read_names": [d.get("filename") for d in reads],
        "compared_names": [d.get("filename") for d in compared],
        "missing_successful_reads": [
            n for n in expected_filenames if n not in read_names
        ],
        "missing_from_successful_comparison": (
            [n for n in expected_filenames if n not in compared_names]
            if result.get("success") is True
            else None
        ),
        "comparison_documents_match_prior_full_reads": (
            all(fingerprint(d) in prior for d in compared)
            if result.get("success") is True
            else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--expect", action="append", default=[])
    args = parser.parse_args()
    if args.snapshot:
        if args.paths:
            parser.error("Use explicit paths OR --snapshot")
        with args.snapshot.open(encoding="utf-8-sig") as stream:
            snapshot = json.load(stream)
        result = inspect_snapshot(snapshot, args.expect)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        ok = (
            result["compare_success"]
            and not result["failed_read_before_comparison"]
            and not result["missing_successful_reads"]
            and not result["missing_from_successful_comparison"]
            and result["comparison_documents_match_prior_full_reads"]
        )
        raise SystemExit(0 if ok else 1)
    if not args.paths or args.expect:
        parser.error("Provide file paths; --expect requires --snapshot")
    result = diagnose(args.paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(
        0
        if result["compare_success"] is True and result["source_observations_unchanged"]
        else 1
    )


if __name__ == "__main__":
    main()
