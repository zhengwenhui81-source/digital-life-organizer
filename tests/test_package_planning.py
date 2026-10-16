"""Pure package planning: no filesystem assumptions or operations."""

from copy import deepcopy
from unittest.mock import patch

import pytest

from fileforge.package._planning import _plan_package


def ref(name="报名表.pdf", folder="/inputs", file_id="file_a"):
    return {"file_id": file_id, "path": f"{folder}/{name}", "filename": name}


def plan(selected=None, destination="/workspace/Hackathon_Package", requirements=None):
    return _plan_package(
        "task_1",
        requirements or [],
        [ref()] if selected is None else selected,
        destination,
    )


def test_deterministic_mapping_order_dedup_and_targets():
    first, second = ref(), ref("项目介绍.txt", file_id="file_b")
    selected = [first, second, deepcopy(first)]
    result = plan(selected, requirements=["报名表", "项目介绍", "报名表"])
    assert result == plan(selected, requirements=["报名表", "项目介绍", "报名表"])
    assert result["status"] == "planned"
    assert result["planned_package_path"] == "/workspace/Hackathon_Package"
    assert (
        result["planned_report_path"]
        == "/workspace/Hackathon_Package/PACKAGE_REPORT.md"
    )
    assert result["requirements"] == ["报名表", "项目介绍"]
    assert result["copies"] == [
        {
            "source_file_id": "file_a",
            "source": "/inputs/报名表.pdf",
            "filename": "报名表.pdf",
            "destination": "/workspace/Hackathon_Package/报名表.pdf",
        },
        {
            "source_file_id": "file_b",
            "source": "/inputs/项目介绍.txt",
            "filename": "项目介绍.txt",
            "destination": "/workspace/Hackathon_Package/项目介绍.txt",
        },
    ]
    assert result["verification_targets"] == {
        "base": "/workspace/Hackathon_Package",
        "files": ["报名表.pdf", "项目介绍.txt", "PACKAGE_REPORT.md"],
        "archive": [],
    }


@pytest.mark.parametrize("name", ["报名表.pdf", "FORM.pdf", "e\u0301.txt"])
def test_different_sources_colliding_names_rejected(name):
    other = {
        "报名表.pdf": "报名表.pdf",
        "FORM.pdf": "form.PDF",
        "e\u0301.txt": "é.txt",
    }[name]
    with pytest.raises(ValueError, match="target"):
        plan([ref(name), ref(other, folder="/other", file_id="file_b")])


@pytest.mark.parametrize("name", ["PACKAGE_REPORT.md", "package_report.MD"])
def test_report_name_reserved(name):
    with pytest.raises(ValueError, match="reserved"):
        plan([ref(name)])


@pytest.mark.parametrize("change", ["id", "path", "filename"])
def test_identity_inconsistency(change):
    first = ref()
    second = ref("other.pdf", file_id="file_b")
    if change == "id":
        second["file_id"] = first["file_id"]
    elif change == "path":
        second["path"], second["filename"] = first["path"], first["filename"]
    else:
        second = deepcopy(first)
        second["filename"] = "other.pdf"
    with pytest.raises(ValueError):
        plan([first, second])


@pytest.mark.parametrize(
    "destination",
    [
        "relative/package",
        "~/package",
        "/workspace/../outside",
        "/workspace/./package",
        "/workspace//package",
        "/workspace/package/",
        "C:\\data\\package",
        "C:package",
        "\\\\server\\share\\package",
        "//server/share/package",
        "file:///tmp/pkg",
        "",
        "/workspace/CON",
        "/workspace/name.",
        "/workspace/name ",
    ],
)
def test_invalid_or_foreign_destination(destination):
    with pytest.raises(ValueError):
        plan(destination=destination)


@pytest.mark.parametrize(
    "name",
    [
        "",
        "../escape.txt",
        "a/b.txt",
        "a\\b.txt",
        "CON.txt",
        "LPT1.pdf",
        "NUL",
        "x.",
        "x ",
        "a:b.txt",
        "a?.txt",
        "a\n.txt",
        "a\x00.txt",
    ],
)
def test_invalid_filenames(name):
    with pytest.raises(ValueError):
        plan([ref(name)])


def test_foreign_source_rejected_and_filename_must_agree():
    for source in (
        "C:\\inputs\\报名表.pdf",
        "/inputs/../报名表.pdf",
        "/inputs/other.pdf",
    ):
        item = ref()
        item["path"] = source
        with pytest.raises(ValueError):
            plan([item])


@pytest.mark.parametrize(
    "destination", ["/inputs", "/inputs/报名表.pdf", "/inputs/报名表.pdf/package"]
)
def test_source_target_or_directory_overlap(destination):
    with pytest.raises(ValueError, match="overlaps"):
        plan(destination=destination)


@pytest.mark.parametrize("selected", [[], None, {}, [None], [{}]])
def test_empty_or_invalid_selection(selected):
    with pytest.raises(ValueError):
        _plan_package("task", [], selected, "/workspace/package")


@pytest.mark.parametrize(
    "task,requirements",
    [("", []), (None, []), ("task", None), ("task", [None]), ("task", [""])],
)
def test_invalid_task_or_requirements(task, requirements):
    with pytest.raises(ValueError):
        _plan_package(task, requirements, [ref()], "/workspace/package")


def test_no_filesystem_access_or_mutation():
    selected, requirements = [ref()], ["报名表"]
    before = deepcopy((selected, requirements))
    with (
        patch("io.open", side_effect=AssertionError("No IO")),
        patch("builtins.open", side_effect=AssertionError("No IO")),
        patch("os.stat", side_effect=AssertionError("No stat")),
        patch("os.mkdir", side_effect=AssertionError("No mkdir")),
    ):
        result = _plan_package("task", requirements, selected, "/workspace/package")
    assert (selected, requirements) == before
    result["requirements"].append("changed")
    result["copies"][0]["source_file_id"] = "changed"
    assert (selected, requirements) == before
