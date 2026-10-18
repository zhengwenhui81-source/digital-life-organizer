"""Real temporary files through both public C tools; portable Windows acceptance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from fileforge.document import compare_versions, read_document
from tests.test_document_parser import _make_docx, _make_pdf, _make_xlsx


def _write(path: Path, body: str, tail: str) -> None:
    if path.suffix == ".pdf":
        _make_pdf(path, [[body], [tail]])
    elif path.suffix == ".docx":
        _make_docx(path, [body, tail])
    elif path.suffix == ".xlsx":
        _make_xlsx(path, {"Body": [[body]], "Tail": [[tail]]})
    else:
        path.write_text(body + "\n" + tail, encoding="utf-8")


@pytest.mark.parametrize("extension", [".txt", ".pdf", ".docx", ".xlsx"])
@pytest.mark.parametrize(
    "scenario", ["qualifying", "unrelated", "identical", "no_version"]
)
def test_real_formats_read_then_compare(tmp_path, extension, scenario):
    folder = tmp_path / "中文 空格目录"
    folder.mkdir()
    second_suffix = "最终版" if scenario == "no_version" else "v2"
    paths = [
        folder / ("材料_v1" + extension),
        folder / (f"材料_{second_suffix}" + extension),
    ]
    body_a = "shared information " * 30
    body_b = body_a
    tails = ["old evidence", "new evidence"]
    if scenario == "unrelated":
        body_a, body_b = "x" * 600, "y" * 600
    elif scenario == "identical":
        tails = ["identical evidence"] * 2
    for path, body, tail in zip(paths, [body_a, body_b], tails, strict=True):
        _write(path, body, tail)
        # Comparable equal times prevent fixture creation order from inventing
        # an opposing time signal. Only pytest's own temporary files are changed.
        os.utime(path, ns=(1_760_000_000_000_000_000,) * 2)
    before = [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths]
    documents = []
    for path in paths:
        result = read_document(str(path))
        assert result["success"], result
        d = result["data"]["document"]
        assert d["extension"] == extension
        assert len(d["text"]) >= 100
        assert read_document(str(path)) == result
        documents.append(d)
    assert documents[0]["file_id"] != documents[1]["file_id"]
    result = compare_versions(documents)
    assert result["success"] and result["error"] is None, result
    groups = result["data"]["groups"]
    retained = [d for group in groups for d in group["documents"]]
    assert sorted(retained, key=lambda d: d["file_id"]) == sorted(
        documents, key=lambda d: d["file_id"]
    )
    if scenario == "unrelated":
        assert len(groups) == 2
        assert all(g["recommendation_reason"] == "single_document" for g in groups)
        assert all(g["newest_candidate"] is None and g["changes"] == [] for g in groups)
    else:
        assert len(groups) == 1 and len(groups[0]["documents"]) == 2
        group = groups[0]
        if scenario == "qualifying":
            assert group["recommendation_reason"] == "unique_highest_explicit_version"
            assert group["newest_candidate"]["file_id"] == documents[1]["file_id"]
            assert group["comparison_order"]["basis"] == "explicit_version"
            assert group["changes"] and all(
                c["type"] == "replace" for c in group["changes"]
            )
            assert "old evidence" in group["changes"][0]["before"]["text"]
            assert "new evidence" in group["changes"][0]["after"]["text"]
        else:
            expected = (
                "identical_content"
                if scenario == "identical"
                else "insufficient_evidence"
            )
            assert group["recommendation_reason"] == expected
            assert group["newest_candidate"] is None
            assert group["changes"]
            if scenario == "identical":
                assert [c["type"] for c in group["changes"]] == ["identical"]
    assert [(p.read_bytes(), p.stat().st_mtime_ns) for p in paths] == before
