"""Integration through C's real TXT reader and D's public analysis tools."""

from __future__ import annotations

import json
import runpy
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from fileforge.document import read_document
from fileforge.task_intelligence import detect_conflicts, extract_requirements


def _read_notices(tmp_path: Path, texts: list[str]):
    documents = []
    for index, text in enumerate(texts):
        folder = tmp_path / str(index)
        folder.mkdir()
        path = folder / "通知.txt"
        path.write_text(text, encoding="utf-8")
        result = read_document(path=str(path))
        assert result["success"] is True, result
        assert result["tool"] == "read_document"
        assert result["error"] is None
        assert result["data"]["document"]["text"] == text
        documents.append(result["data"]["document"])
    return documents


def test_real_documents_preserve_conflicts_sources_and_requirement_order(tmp_path):
    docs = _read_notices(
        tmp_path,
        [
            "报名截止：2026年10月18日\n提交材料：\n1. 报名表\n2. 学生证（必交）\n",
            "报名截止：2026-10-20\n无需提交学生证；必须提交项目介绍、报名表\n",
        ],
    )
    original = deepcopy(docs)
    assert docs[0]["filename"] == docs[1]["filename"]
    assert docs[0]["file_id"] != docs[1]["file_id"]
    assert docs[0]["path"] != docs[1]["path"]
    result = detect_conflicts(documents=docs)
    assert result["success"] is True
    assert result["data"]["conflicts"] == [
        {
            "field": "deadline:报名",
            "values": [
                {"value": "2026-10-18", "source": docs[0]["path"]},
                {"value": "2026-10-20", "source": docs[1]["path"]},
            ],
            "recommendation": "请人工确认",
        },
        {
            "field": "required_documents:学生证",
            "values": [
                {"value": "required", "source": docs[0]["path"]},
                {"value": "not_required", "source": docs[1]["path"]},
            ],
            "recommendation": "请人工确认",
        },
    ]
    requirements = extract_requirements(documents=docs)
    assert requirements["success"] is True
    assert requirements["data"] == {
        "required_documents": ["报名表", "学生证", "项目介绍"]
    }
    assert docs == original
    for doc in docs:
        assert Path(doc["path"]).read_text(encoding="utf-8") == doc["text"]


def test_real_documents_without_conflicts_still_extract_required_materials(tmp_path):
    docs = _read_notices(
        tmp_path,
        [
            "报名截止：2026年10月18日\n必须提交报名表、学生证\n",
            "报名截止：2026-10-18\n必交材料：\n1. 项目介绍\n2. 报名表\n",
        ],
    )
    assert detect_conflicts(documents=docs)["data"] == {"conflicts": []}
    result = extract_requirements(documents=docs)
    assert result["success"] is True
    assert result["data"] == {"required_documents": ["报名表", "学生证", "项目介绍"]}


@pytest.mark.parametrize("failure", ["missing", "empty", "unsupported"])
def test_demo_stops_before_d_tools_on_real_c_failure(tmp_path, failure):
    valid = tmp_path / "通知.txt"
    valid.write_text("必须提交报名表", encoding="utf-8")
    invalid = tmp_path / ("材料.pdf" if failure == "unsupported" else "失败.txt")
    if failure != "missing":
        invalid.write_text("内容" if failure == "unsupported" else "", encoding="utf-8")
    namespace = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/task_intelligence_demo.py")
    )
    analyze = namespace["_analyze_paths"]
    conflicts = Mock(side_effect=AssertionError("Must not analyze after read failure"))
    requirements = Mock(
        side_effect=AssertionError("Must not analyze after read failure")
    )
    with patch.dict(
        analyze.__globals__,
        {"detect_conflicts": conflicts, "extract_requirements": requirements},
    ):
        report = analyze([valid, invalid])
    assert report["read_results"][0]["success"] is True
    failed = report["read_results"][1]
    assert failed["success"] is False
    assert failed["data"] is None
    assert failed["error"]
    assert report["analysis"] is None
    conflicts.assert_not_called()
    requirements.assert_not_called()


def test_demo_outputs_json_and_cleans_up_temporary_notices(capsys):
    namespace = runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "scripts/task_intelligence_demo.py")
    )
    assert namespace["main"]() == 0
    report = json.loads(capsys.readouterr().out)
    assert all(read["success"] for read in report["read_results"])
    analysis = report["analysis"]
    assert len(analysis["detect_conflicts"]["data"]["conflicts"]) == 2
    assert analysis["extract_requirements"]["data"] == {
        "required_documents": ["报名表", "学生证", "项目介绍"]
    }
    for read in report["read_results"]:
        assert not Path(read["data"]["document"]["path"]).parent.exists()
