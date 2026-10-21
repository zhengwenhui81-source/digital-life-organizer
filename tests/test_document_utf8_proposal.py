"""Isolated proposed formats, never a claim of public reader/Agent support."""

import copy
import hashlib
import os
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from fileforge.document import _utf8_proposal as candidate
from fileforge.document import compare_versions, read_document
from fileforge.task_intelligence import match_requirements


def read(path, root):
    return candidate._read_utf8_candidate(str(path), str(root))


def failed(result):
    assert result["tool"] == "read_document"
    assert result["success"] is False and result["data"] is None
    assert result["error"] and result["message"]


@pytest.mark.parametrize("suffix", [".cpp", ".h", ".hpp", ".json", ".csv"])
@pytest.mark.parametrize("bom", [False, True])
def test_exact_text_identity_preservation_and_public_gate(tmp_path, suffix, bom):
    parent = tmp_path / "中文 空格"
    parent.mkdir()
    path = parent / ("材料" + suffix.upper())
    # Literal text: quotes, CSV multiline records and CRLF must not be rewritten.
    body = '中文,列\r\n"带,逗号","多行\n内容"\r\nint main(){}\n'
    raw = (b"\xef\xbb\xbf" if bom else b"") + body.encode("utf-8")
    path.write_bytes(raw)
    before = (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_size)
    result = read(path, tmp_path)
    assert result["success"] is True and result["error"] is None, result
    document = result["data"]["document"]
    resolved = path.resolve()
    assert document == {
        "file_id": "file_"
        + hashlib.sha256(os.path.normcase(str(resolved)).encode("utf-8")).hexdigest(),
        "path": str(resolved),
        "filename": path.name,
        "extension": suffix,
        "text": body,
        "size": len(raw),
        "modified_time": datetime.fromtimestamp(
            path.stat().st_mtime, tz=UTC
        ).isoformat(),
        "metadata": {},
    }
    assert read(path, tmp_path) == result
    assert read(path.relative_to(tmp_path), tmp_path) == result
    failed(read_document(str(path)))  # Public contract gate remains closed.
    assert before == (path.read_bytes(), path.stat().st_mtime_ns, path.stat().st_size)


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"\xe4\xb8",  # truncated Chinese UTF-8
        b"\xc0\xaf",  # overlong sequence
        b"\xed\xa0\x80",  # surrogate
        "中文".encode("gbk"),
        "中文".encode("utf-16"),
        "中文".encode("utf-32"),
        b"x" * 65536 + b"\xff",  # invalid after a complete stream chunk
        b"\xef\xbb\xbf\xff",
    ],
)
def test_invalid_encoding_returns_no_partial_document(tmp_path, raw):
    path = tmp_path / "bad.json"
    path.write_bytes(raw)
    result = read(path, tmp_path)
    failed(result)
    assert "Invalid UTF-8" in result["error"]
    assert path.read_bytes() == raw


@pytest.mark.parametrize("raw", [b"", b" \r\n\t", b"\xef\xbb\xbf", b"a\x00b"])
def test_empty_and_binary_nul_rejected(tmp_path, raw):
    path = tmp_path / "empty.cpp"
    path.write_bytes(raw)
    failed(read(path, tmp_path))


@pytest.mark.parametrize("suffix", [".cpp", ".h", ".hpp", ".json", ".csv"])
def test_ascii_and_authored_replacement_character_are_not_guessed(tmp_path, suffix):
    path = tmp_path / ("plain" + suffix)
    body = "ASCII\n" + "\ufffd" + "\ufeff"
    path.write_bytes(body.encode("utf-8"))
    assert read(path, tmp_path)["data"]["document"]["text"] == body


@pytest.mark.parametrize("body", ['{"incomplete":', 'a,b\n"unterminated', "=1+2"])
def test_literal_text_does_not_claim_json_csv_syntax_validation(tmp_path, body):
    path = tmp_path / "literal.json"
    path.write_bytes(body.encode("utf-8"))
    assert read(path, tmp_path)["data"]["document"]["text"] == body


def test_never_executes_source_or_csv_formula(tmp_path):
    marker = tmp_path / "MUST_NOT_EXIST"
    body = f'__import__("pathlib").Path({str(marker)!r}).write_text("bad")'
    for suffix in (".cpp", ".json", ".csv"):
        path = tmp_path / ("literal" + suffix)
        path.write_bytes(body.encode("utf-8"))
        assert read(path, tmp_path)["data"]["document"]["text"] == body
    assert not marker.exists()


@pytest.mark.parametrize("bom", [False, True])
def test_exact_raw_byte_limit_and_multibyte_accounting(tmp_path, bom):
    path = tmp_path / "boundary.csv"
    prefix = b"\xef\xbb\xbf" if bom else b""
    room = candidate._MAX_BYTES - len(prefix)
    body = "中" * (room // 3) + "a" * (room % 3)
    raw = prefix + body.encode("utf-8")
    assert len(raw) == candidate._MAX_BYTES
    path.write_bytes(raw)
    document = read(path, tmp_path)["data"]["document"]
    assert document["text"] == body and document["size"] == len(raw)
    # Decoding crosses chunks without per-chunk replacement/corruption.
    path.write_bytes(raw + b"a")
    result = read(path, tmp_path)
    failed(result)
    assert "limit" in result["error"]


def test_large_stat_rejected_before_open(tmp_path, monkeypatch):
    path = tmp_path / "large.cpp"
    with path.open("wb") as stream:
        stream.truncate(candidate._MAX_BYTES + 1)

    def unexpected_open(*args, **kwargs):
        pytest.fail("Oversized source must fail before os.open")

    monkeypatch.setattr(candidate.os, "open", unexpected_open)
    failed(read(path, tmp_path))


def test_bounded_stream_detects_growth_and_closes_descriptor(tmp_path, monkeypatch):
    path = tmp_path / "grow.csv"
    path.write_bytes(b"a")
    original = os.read
    returned = 0
    requested = []
    descriptors = []

    def grows(fd, count):
        nonlocal returned
        requested.append(count)
        descriptors.append(fd)
        if not returned:
            with path.open("ab") as stream:
                stream.write(b"x" * candidate._MAX_BYTES)
        data = original(fd, count)
        returned += len(data)
        return data

    monkeypatch.setattr(candidate.os, "read", grows)
    failed(read(path, tmp_path))
    assert returned == candidate._MAX_BYTES + 1
    assert max(requested) <= candidate._CHUNK
    with pytest.raises(OSError):
        os.fstat(descriptors[0])


def test_observable_change_rejected_and_original_not_edited_by_reader(
    tmp_path, monkeypatch
):
    path = tmp_path / "change.h"
    path.write_bytes(b"before")
    original = os.read
    changed = False

    def mutate(fd, count):
        nonlocal changed
        data = original(fd, count)
        if not changed:
            with path.open("ab") as stream:
                stream.write(b" changed by test")
            changed = True
        return data

    monkeypatch.setattr(candidate.os, "read", mutate)
    result = read(path, tmp_path)
    failed(result)
    assert "changed" in result["error"]
    assert path.read_bytes() == b"before changed by test"


@pytest.mark.parametrize("kind", ["missing", "directory", "outside", "traversal"])
def test_path_boundaries(tmp_path, kind):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.cpp"
    outside.write_bytes(b"outside")
    paths = {
        "missing": root / "missing.cpp",
        "directory": root,
        "outside": outside,
        "traversal": root / ".." / "outside.cpp",
    }
    failed(read(paths[kind], root))
    assert outside.read_bytes() == b"outside"


@pytest.mark.parametrize("directory_link", [False, True])
def test_link_component_rejected(tmp_path, directory_link):
    root = tmp_path / "workspace"
    root.mkdir()
    original = root / "original"
    original.mkdir()
    path = original / "source.cpp"
    path.write_bytes(b"int main() {}")
    alias = root / ("alias" if directory_link else "alias.cpp")
    try:
        alias.symlink_to(original if directory_link else path, directory_link)
    except OSError as exc:
        pytest.skip(f"OS cannot create test symbolic link: {exc}")
    failed(read(alias / path.name if directory_link else alias, root))
    assert path.read_bytes() == b"int main() {}"


@pytest.mark.parametrize("suffix", [".py", ".md", ".exe", ".txt", ".docx"])
def test_candidate_does_not_expand_unproposed_formats(tmp_path, suffix):
    path = tmp_path / ("other" + suffix)
    path.write_bytes(b"body")
    failed(read(path, tmp_path))


def test_permission_error_standard_failure(tmp_path, monkeypatch):
    path = tmp_path / "locked.hpp"
    path.write_bytes(b"body")

    def denied(*args, **kwargs):
        raise PermissionError("test denial")

    monkeypatch.setattr(candidate.os, "open", denied)
    failed(read(path, tmp_path))


def test_public_matching_preserves_all_original_references_and_order(tmp_path):
    documents = []
    for name in ("主程序.cpp", "主程序_v2.hpp", "配置.json", "数据.csv", "声明.h"):
        path = tmp_path / name
        path.write_bytes("真实临时文件正文\n".encode())
        documents.append(read(path, tmp_path)["data"]["document"])
    before = copy.deepcopy(documents)
    result = match_requirements(["主程序", "配置", "数据", "声明", "缺少"], documents)
    assert result["success"] is True, result
    data = result["data"]
    assert data["missing"] == ["缺少"]
    assert [m["requirement"] for m in data["matched"]] == [
        "主程序",
        "配置",
        "数据",
        "声明",
    ]
    assert data["matched"][0]["documents"] == [
        {key: d[key] for key in ("file_id", "path", "filename")} for d in documents[:2]
    ]
    assert [ref for m in data["matched"] for ref in m["documents"]] == [
        {key: d[key] for key in ("file_id", "path", "filename")} for d in documents
    ]
    assert documents == before
    assert match_requirements([], documents)["data"]["matched"] == []
    assert match_requirements(["主程序"], [])["data"]["missing"] == ["主程序"]
    # Same path identity with contradictory full contents must fail, not match.
    changed = copy.deepcopy(documents[0])
    changed["text"] += "different"
    conflict = match_requirements(["主程序"], [documents[0], changed])
    assert conflict["success"] is False and conflict["data"] is None


def test_successful_read_does_not_bypass_version_limits(tmp_path, monkeypatch):
    from fileforge.document import versions

    path = tmp_path / "long.cpp"
    path.write_bytes(b"a" * 10001)
    document = read(path, tmp_path)["data"]["document"]

    def no_worker(*args, **kwargs):
        pytest.fail("Version must reject overlong input before worker creation")

    monkeypatch.setattr(versions.subprocess, "Popen", no_worker)
    result = compare_versions([document])
    assert result["success"] is False and result["data"] is None
    assert "10001" in result["error"] and "10000" in result["error"]


@pytest.mark.parametrize(
    "field", ["st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns"]
)
def test_windows_cross_api_still_requires_every_identity_field(monkeypatch, field):
    monkeypatch.setattr(candidate, "_WINDOWS_STAT", True)
    fields = dict(
        st_dev=1, st_ino=2, st_mode=3, st_size=4, st_mtime_ns=5, st_ctime_ns=6
    )
    before = SimpleNamespace(**fields)
    fields["st_ctime_ns"] += 1000
    assert candidate._signature(before, cross_api=True) == candidate._signature(
        SimpleNamespace(**fields), cross_api=True
    )
    assert candidate._signature(before) != candidate._signature(
        SimpleNamespace(**fields)
    )
    fields[field] += 1
    assert candidate._signature(before, cross_api=True) != candidate._signature(
        SimpleNamespace(**fields), cross_api=True
    )


def test_posix_keeps_cross_api_ctime(monkeypatch):
    monkeypatch.setattr(candidate, "_WINDOWS_STAT", False)
    fields = dict(
        st_dev=1, st_ino=2, st_mode=3, st_size=4, st_mtime_ns=5, st_ctime_ns=6
    )
    before = SimpleNamespace(**fields)
    fields["st_ctime_ns"] += 1
    assert candidate._signature(before, cross_api=True) != candidate._signature(
        SimpleNamespace(**fields), cross_api=True
    )


def test_reparse_attribute_rejected_in_isolated_probe(tmp_path, monkeypatch):
    path = tmp_path / "source.cpp"
    path.write_bytes(b"body")
    original = Path.lstat

    def reparse(p, *args, **kwargs):
        info = original(p, *args, **kwargs)
        if p == path:
            return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
        return info

    monkeypatch.setattr(Path, "lstat", reparse)
    result = read(path, tmp_path)
    failed(result)
    assert "reparse" in result["error"]


def test_success_and_decode_failure_close_descriptor(tmp_path, monkeypatch):
    path = tmp_path / "source.cpp"
    original = os.open
    descriptors = []

    def tracked(*args, **kwargs):
        fd = original(*args, **kwargs)
        descriptors.append(fd)
        return fd

    monkeypatch.setattr(candidate.os, "open", tracked)
    path.write_bytes(b"body")
    assert read(path, tmp_path)["success"] is True
    path.write_bytes(b"\xff")
    failed(read(path, tmp_path))
    assert len(descriptors) == 2
    for fd in descriptors:
        with pytest.raises(OSError):
            os.fstat(fd)
