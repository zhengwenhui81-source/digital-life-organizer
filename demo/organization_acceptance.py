"""Local test-data generator and READ-ONLY observation checker, not an Agent API."""
from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import sys
import uuid
import zipfile
from xml.sax.saxutils import escape

SCHEMA = "b-organization-acceptance-v1"  # Private test artifact, NOT a public contract.
LABELS = {"course", "finance", "personal", "needs_confirmation"}
OUTPUT = "整理结果"


class UnsafeInput(ValueError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def guarded(path):
    """Reject symlinks/reparse points in every existing ancestor; never resolve them."""
    path = Path(os.path.abspath(path))
    for item in [*reversed(path.parents), path]:
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise UnsafeInput("Symbolic link/reparse point rejected")
        if item != path and not stat.S_ISDIR(info.st_mode):
            raise UnsafeInput("Non-directory ancestor")
    return path


def relative(value):
    if not isinstance(value, str) or not value or "\x00" in value:
        raise UnsafeInput("Invalid relative path")
    value = value.replace("\\", "/")
    win = PureWindowsPath(value)
    parts = value.split("/")
    if win.drive or win.root or PurePosixPath(value).is_absolute() or any(
        part in ("", ".", "..") or part.rstrip(" .") != part
        or any(c in part for c in '<>:"|?*')
        or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *[f"COM{i}" for i in range(1, 10)], *[f"LPT{i}" for i in range(1, 10)]}
        for part in parts
    ):
        raise UnsafeInput("Unsafe Windows-relative path")
    return "/".join(parts)


def stable_bytes(path):
    path = guarded(path)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise UnsafeInput("Not an exclusive regular file")
    if before.st_size > 64 * 1024 * 1024:
        raise UnsafeInput("Test artifact exceeds 64 MiB safety limit")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    try:
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            data = stream.read(64 * 1024 * 1024 + 1)
            after = os.fstat(stream.fileno())
        observed = path.lstat()
        identity = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_nlink)
        # Retain ctime checks within each API; Windows lstat/fstat can disagree.
        if len(data) > 64 * 1024 * 1024 or not (
            identity(before) == identity(opened) == identity(after) == identity(observed)
            and before.st_ctime_ns == observed.st_ctime_ns
            and opened.st_ctime_ns == after.st_ctime_ns
        ):
            raise UnsafeInput("File changed during observation")
        guarded(path)
        return data, after
    except BaseException:
        # fdopen owns fd once entered. No cleanup or retry of observed files.
        raise


def inventory(root):
    root = guarded(root)
    if not root.is_dir():
        raise UnsafeInput("Workspace must be a directory")
    found, keys = {}, set()

    def walk(folder):
        guarded(folder)
        for item in sorted(folder.iterdir(), key=lambda p: p.name):
            guarded(item)
            name = relative(item.relative_to(root).as_posix())
            key = name.casefold()
            if key in keys:
                raise UnsafeInput("Windows case-insensitive path collision")
            keys.add(key)
            info = item.lstat()
            if stat.S_ISDIR(info.st_mode):
                walk(item)
            else:
                data, info = stable_bytes(item)
                found[name] = {"size": len(data), "sha256": digest(data), "mtime_ns": str(info.st_mtime_ns)}

    walk(root)
    return found


def docx(text="合成课程大纲：本学期学习线性代数，每周完成习题。"):
    buffer = io.BytesIO()
    files = {
        "[Content_Types].xml": '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>' + escape(text) + '</w:t></w:r></w:p></w:body></w:document>',
    }
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in files.items():
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            archive.writestr(entry, value.encode("utf-8"))
    return buffer.getvalue()


def pdf(text="Synthetic course notes: algebra exercises for students."):
    literal = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = ("BT /F1 12 Tf 30 100 Td (" + literal + ") Tj ET").encode("ascii")
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
               b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
               b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    data = b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    start = len(data)
    data += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{n:010d} 00000 n \n".encode() for n in offsets[1:])
    return data + f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()


def samples():
    """Human-authored content and labels for this small controlled set only."""
    txt = lambda s: ("合成验收数据，非用户资料。\n" + s + "\n").encode("utf-8")
    return [
        ("学习/笔记.txt", txt("线性代数课程笔记：矩阵乘法练习与每周作业。"), "course", "supported_text"),
        ("财务/笔记.txt", txt("财务记账凭证：办公用品支出100元，报销经费。"), "finance", "supported_text"),
        ("中文路径/计划.txt", txt("个人生活安排：周末散步、买菜和家庭聚会。"), "personal", "supported_text"),
        ("资料/说明.txt", txt("课程教学计划：学习几何并完成课堂练习。"), "course", "supported_text"),
        ("资料/票据.txt", txt("财务费用记录：交通费20元待报销。"), "finance", "supported_text"),
        ("资料/空白.txt", b"", "needs_confirmation", "empty_do_not_claim_read"),
        ("不可解析/损坏.pdf", b"deliberately invalid PDF", "needs_confirmation", "expected_parse_failure"),
        ("不可解析/损坏.docx", b"deliberately invalid ZIP", "needs_confirmation", "expected_parse_failure"),
        ("图像/像素.png", base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7WQAAAAASUVORK5CYII="), "needs_confirmation", "unsupported_no_ocr"),
        ("文档/课程大纲.docx", docx(), "course", "body_text_only"),
        ("文档/课程材料.pdf", pdf(), "course", "text_layer_only"),
        ("未知/数据.bin", b"\x00\x01\x02\xff", "needs_confirmation", "unsupported"),
    ]


def generate(directory):
    directory = Path(directory)
    if not directory.is_absolute():
        raise UnsafeInput("Specify an absolute NEW test directory")
    parent = guarded(directory.parent)
    if not parent.is_dir():
        raise UnsafeInput("Parent must already exist")
    parent_id = (parent.stat().st_dev, parent.stat().st_ino)
    directory.mkdir()  # Exclusive: existing directories (even empty) are refused.
    root = guarded(directory)

    def create(name, content):
        target = root / relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)  # Only inside our newly created root.
        guarded(target.parent)
        if (parent.stat().st_dev, parent.stat().st_ino) != parent_id:
            raise UnsafeInput("Test parent changed")
        with target.open("xb") as stream:
            stream.write(content)
        guarded(root)

    rows = samples()
    for name, data, _, _ in rows:
        create("workspace/" + name, data)
    create(f"workspace/{OUTPUT}/保留/既有.txt", b"Preexisting synthetic output: MUST NOT CHANGE\n")
    create(f"workspace/{OUTPUT}/财务/笔记.txt", b"Occupied target: MUST NOT OVERWRITE\n")
    baseline = {"schema": SCHEMA, "dataset_id": str(uuid.uuid4()), "synthetic": True,
                "files": inventory(root / "workspace"),
                "truth": {name: {"label": label, "handling": handling} for name, _, label, handling in rows},
                "note": "Human-authored test labels, not a production taxonomy or measured classification."}
    content = json_bytes(baseline)
    create("evidence/baseline.json", content)
    table = "# 合成人工标准答案（不是分类实测结果）\n\n| 相对路径 | 人工标签 | 预期处理 |\n| --- | --- | --- |\n"
    table += "".join(f"| {name} | {label} | {handling} |\n" for name, _, label, handling in rows)
    table += "\n已有整理结果为保护哨兵，不参与源分类；标签应按正文人工核对，不能只看文件名。\n当前未调用解析器；预期可读取不等于已实测读取。\n"
    create("evidence/ground-truth.md", table.encode("utf-8"))
    create("READY.json", json_bytes({"schema": SCHEMA, "dataset_id": baseline["dataset_id"], "baseline_sha256": digest(content)}))
    return {"status": "prepared", "dataset_id": baseline["dataset_id"], "source_files": len(rows), "protected_output_files": 2,
            "classification": "blocked", "execution": "not_run", "directory": str(root)}


def load_json(path):
    return json.loads(stable_bytes(path)[0])


def pointer(value, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise UnsafeInput("Evidence needs an explicit JSON pointer")
    for key in path[1:].split("/"):
        key = key.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) and key.isdecimal() else value[key]
    return value


def source_name(value, workspace):
    if not isinstance(value, str):
        raise UnsafeInput("Evidence source path must be text")
    # Native absolute paths from a Windows run are accepted only under this Workspace.
    path = Path(value)
    if path.is_absolute():
        value = path.relative_to(workspace).as_posix()
    return relative(value)


def classification_metrics(truth, decisions):
    """Pure arithmetic only; caller must first bind every decision to raw evidence."""
    if set(truth) != set(decisions) or any(label not in LABELS for label in decisions.values()):
        return {"status": "unverifiable", "accuracy": None, "coverage": None, "reason": "Require exactly one evidenced decision per source, including abstentions"}
    classified = [name for name, label in decisions.items() if label != "needs_confirmation"]
    correct = sum(decisions[name] == truth[name]["label"] for name in classified)
    return {"status": ("passed" if correct / len(classified) >= 0.95 else "failed") if classified else "unverifiable", "accuracy": correct / len(classified) if classified else None,
            "coverage": len(classified) / len(truth) if truth else None, "correct": correct, "classified": len(classified),
            "total": len(truth), "abstained": len(truth) - len(classified), "target_accuracy": 0.95,
            "target_met": correct / len(classified) >= 0.95 if classified else None}


def check(directory, review_path=None, raw_path=None):
    if not Path(directory).is_absolute():
        raise UnsafeInput("Specify an absolute test directory")
    root = guarded(directory)
    ready = load_json(root / "READY.json")
    baseline_bytes, _ = stable_bytes(root / "evidence/baseline.json")
    baseline = json.loads(baseline_bytes)
    if not isinstance(ready, dict) or not isinstance(baseline, dict) or baseline.get("synthetic") is not True or ready.get("schema") != SCHEMA or baseline.get("schema") != SCHEMA or ready.get("dataset_id") != baseline.get("dataset_id") or ready.get("baseline_sha256") != digest(baseline_bytes):
        raise UnsafeInput("Missing or changed dataset baseline")
    files, truth = baseline["files"], baseline["truth"]
    if not isinstance(files, dict) or not isinstance(truth, dict) or not truth:
        raise UnsafeInput("Invalid baseline")
    for name, record in files.items():
        relative(name)
        if not isinstance(record, dict) or type(record.get("size")) is not int or record["size"] < 0 or not isinstance(record.get("sha256"), str) or len(record["sha256"]) != 64 or any(c not in "0123456789abcdef" for c in record["sha256"]) or not isinstance(record.get("mtime_ns"), str):
            raise UnsafeInput("Invalid inventory record")
    sources = {name for name in files if relative(name).split("/")[0].casefold() != OUTPUT.casefold()}
    if set(truth) != sources or any(not isinstance(row, dict) or row.get("label") not in LABELS for row in truth.values()):
        raise UnsafeInput("Invalid gold labels or output included as source")
    workspace = guarded(root / "workspace")
    current = inventory(workspace)
    changed = [name for name in files if current.get(name) != files[name]]
    report = {"schema": SCHEMA, "dataset_id": ready["dataset_id"], "status": "blocked", "e2e_certified": False,
              "scope": "Current bytes and operator-supplied artifacts; approval authority/history not authenticated",
              "originals": {"status": "failed" if any(name in truth for name in changed) else "passed", "changed_or_missing": [name for name in changed if name in truth]},
              "preexisting_output": {"status": "failed" if any(name not in truth for name in changed) else "passed", "changed_or_missing": [name for name in changed if name not in truth]},
              "classification": {"status": "blocked", "accuracy": None, "coverage": None, "reason": "No real classification artifact and reviewed mapping"},
              "execution": {"status": "not_run", "copies": [], "unexpected_files": []}, "issues": []}
    expected_targets, decisions = set(), {}
    if review_path is not None or raw_path is not None:
        try:
            if review_path is None or raw_path is None:
                raise UnsafeInput("Both raw results and local review are required")
            raw_bytes, _ = stable_bytes(raw_path)
            raw, review = json.loads(raw_bytes), load_json(review_path)
            if not isinstance(review, dict) or review.get("dataset_id") != ready["dataset_id"] or review.get("baseline_sha256") != ready["baseline_sha256"] or review.get("raw_sha256") != digest(raw_bytes) or review.get("run_kind") != "real" or not isinstance(review.get("task_id"), str) or not review["task_id"].strip():
                raise UnsafeInput("Evidence provenance mismatch or non-real run")
            if pointer(raw, review["task_pointer"]) != review["task_id"]:
                raise UnsafeInput("Raw artifact task does not match reviewed task")
            aliases = review.get("category_labels")
            if not isinstance(aliases, dict) or any(label not in LABELS for label in aliases.values()):
                raise UnsafeInput("Human-reviewed category aliases required")
            for entry in review["classifications"]:
                name = relative(entry["source"])
                if name not in truth or name in decisions or source_name(pointer(raw, entry["source_pointer"]), workspace) != name:
                    raise UnsafeInput("Unknown/duplicate/foreign classification source")
                category = pointer(raw, entry["category_pointer"])
                if not isinstance(category, str) or category not in aliases:
                    raise UnsafeInput("Raw category lacks a reviewed alias")
                decisions[name] = aliases[category]
            report["classification"] = classification_metrics(truth, decisions)
            state = review["execution_status"]
            if state not in ("not_run", "completed", "failed") or not isinstance(review["copies"], list) or (state == "not_run" and review["copies"]):
                raise UnsafeInput("Invalid execution observations")
            copied_sources, target_keys = set(), set()
            for entry in review["copies"]:
                name, target = relative(entry["source"]), relative(entry["target"])
                status = entry["status"]
                if name not in truth or target.split("/")[0] != OUTPUT or len(target.split("/")) < 3 or target.casefold() in target_keys or name in copied_sources or target.casefold() in {n.casefold() for n in files}:
                    raise UnsafeInput("Duplicate copy, occupied target or invalid source/destination")
                if source_name(pointer(raw, entry["source_pointer"]), workspace) != name or source_name(pointer(raw, entry["target_pointer"]), workspace) != target or status not in ("succeeded", "failed") or pointer(raw, entry["success_pointer"]) is not (status == "succeeded"):
                    raise UnsafeInput("Copy observation does not match raw artifact")
                copied_sources.add(name)
                target_keys.add(target.casefold())
                expected_targets.add(target)
                actual = current.get(target)
                matched = actual is not None and all(actual[k] == files[name][k] for k in ("size", "sha256"))
                report["execution"]["copies"].append({"source": name, "target": target, "reported_status": status,
                    "status": "passed" if status == "succeeded" and matched else "failed", "bytes_match": matched})
            report["execution"]["status"] = "not_run" if state == "not_run" else "failed" if state == "failed" or any(row["status"] == "failed" for row in report["execution"]["copies"]) else "passed" if report["execution"]["copies"] else "unverifiable"
            report["status"] = "unverifiable"  # No public approval/execution contract can be authenticated here.
        except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
            expected_targets.clear()
            for row in report["execution"]["copies"]:
                row["status"] = "unverifiable"
            report["issues"].append(type(exc).__name__ + ": " + str(exc))
            report["classification"] = {"status": "unverifiable", "accuracy": None, "coverage": None, "reason": "Invalid or non-real evidence"}
            report["execution"]["status"] = "unverifiable"
            report["status"] = "unverifiable"
    extra = sorted(set(current) - set(files) - expected_targets)
    report["execution"]["unexpected_files"] = extra
    if changed or extra or report["execution"]["status"] == "failed" or report["classification"]["status"] == "failed":
        report["status"] = "failed"
    report["inventory"] = current
    return report


def markdown(report):
    return "# 智能整理验收观察报告\n\n" + "\n".join(
        f"- {key}: {json.dumps(report[key], ensure_ascii=False)}" for key in ("status", "e2e_certified", "originals", "preexisting_output", "classification", "execution", "issues")
    ) + "\n\n未认证真实审批或执行历史；当前字节相等不能证明从未发生过覆盖。\n\n| 相对路径 | 字节数 | SHA-256 |\n| --- | --- | --- |\n" + "".join(
        f"| {name} | {row['size']} | {row['sha256']} |\n" for name, row in report["inventory"].items())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--directory", required=True, type=Path)
    read = sub.add_parser("check")
    read.add_argument("--directory", required=True, type=Path)
    read.add_argument("--review", type=Path)
    read.add_argument("--raw-results", type=Path)
    read.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            print(json.dumps(generate(args.directory), ensure_ascii=True, indent=2))
            return 0
        report = check(args.directory, args.review, args.raw_results)
        print(markdown(report) if args.format == "markdown" else json.dumps(report, ensure_ascii=True, indent=2))
        return 1 if report["status"] == "failed" else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "unverifiable", "error": type(exc).__name__, "reason": str(exc)}, ensure_ascii=True))
        return 2 if args.command == "check" else 1


if __name__ == "__main__":
    sys.exit(main())
