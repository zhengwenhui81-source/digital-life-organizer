"""Isolated planner experiments, not classifier or approved-execution acceptance."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from fileforge.organization._draft import _Item, _plan, _Source


def item(root: Path, name: str = "HARNESS_report.txt", **changes: object) -> _Item:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("HARNESS source evidence\n", encoding="utf-8")
    return replace(
        _Item(
            _Source("id_" + name, str(path), path.name),
            "实验资料",
            ("synthetic test decision; NOT a classifier output",),
            selected=True,
            needs_confirmation=False,
        ),
        **changes,
    )


def state(root: Path) -> dict[str, tuple[int, str, int] | None]:
    return {
        str(path.relative_to(root)): (
            (
                path.stat().st_size,
                hashlib.sha256(path.read_bytes()).hexdigest(),
                path.stat().st_mtime_ns,
            )
            if path.is_file()
            else None
        )
        for path in root.rglob("*")
    }


def test_empty_workspace_has_no_operations(tmp_path: Path) -> None:
    assert _plan(str(tmp_path), ()).mappings == ()
    assert _plan(str(tmp_path), ()).directories == ()
    assert list(tmp_path.iterdir()) == []


def test_dynamic_categories_preserve_sources_and_make_no_writes(tmp_path: Path) -> None:
    first = item(tmp_path, "HARNESS_中文 空格.txt")
    second = item(tmp_path, "HARNESS_other.bin", category="自定义资料")
    before = state(tmp_path)
    result = _plan(str(tmp_path), (first, second))
    assert state(tmp_path) == before
    assert result.diagnostics == ()
    assert result.directories == (
        "整理结果",
        "整理结果/实验资料",
        "整理结果/自定义资料",
    )
    assert [mapping.disposition for mapping in result.mappings] == [
        "proposed",
        "proposed",
    ]
    assert result.mappings[0].source == first.source
    assert result.mappings[0].target == "整理结果/实验资料/" + first.source.filename
    assert not hasattr(result, "operations")


@pytest.mark.parametrize(
    "changes", [{"category": None}, {"evidence": ()}, {"needs_confirmation": True}]
)
def test_uncertain_sources_remain_pending(tmp_path: Path, changes: dict) -> None:
    entry = item(tmp_path, **changes)
    result = _plan(str(tmp_path), (entry,))
    assert result.mappings[0].disposition == "pending"
    assert result.mappings[0].target is None
    assert not result.directories


def test_explicit_classification_confirmation_is_not_execution(tmp_path: Path) -> None:
    entry = item(tmp_path, needs_confirmation=True, classification_confirmed=True)
    before = state(tmp_path)
    assert _plan(str(tmp_path), (entry,)).mappings[0].disposition == "proposed"
    assert state(tmp_path) == before


def test_unselected_source_is_retained(tmp_path: Path) -> None:
    result = _plan(str(tmp_path), (item(tmp_path, selected=False),))
    assert result.mappings[0].disposition == "unselected"
    assert not result.directories


@pytest.mark.parametrize(
    "category",
    [
        "../escape",
        "a/b",
        "a\\b",
        "CON",
        "NUL.txt",
        "COM¹",
        "CONIN$",
        "CON .txt",
        "x.",
        " ",
        "x:",
        "整理结果",
    ],
)
def test_invalid_categories_fail_without_writes(tmp_path: Path, category: str) -> None:
    entry = item(tmp_path, category=category)
    before = state(tmp_path)
    with pytest.raises(ValueError):
        _plan(str(tmp_path), (entry,))
    assert state(tmp_path) == before


@pytest.mark.parametrize("categories", [("Reports", "reports"), ("é", "e\u0301")])
def test_category_alias_collision_blocks_all_operations(
    tmp_path: Path, categories: tuple[str, str]
) -> None:
    first = item(tmp_path, "HARNESS_one.txt", category=categories[0])
    second = item(tmp_path, "HARNESS_two.txt", category=categories[1])
    result = _plan(str(tmp_path), (first, second))
    assert "Category spelling collision" in result.diagnostics
    assert result.diagnostics


def test_same_target_filename_in_different_source_folders_is_not_overwritten(
    tmp_path: Path,
) -> None:
    entries = tuple(item(tmp_path, f"HARNESS_{n}/same.txt") for n in (1, 2))
    before = state(tmp_path)
    result = _plan(str(tmp_path), entries)
    assert "Destination name collision" in result.diagnostics
    assert result.diagnostics
    assert state(tmp_path) == before


@pytest.mark.parametrize("occupied_by_file", [True, False])
def test_preexisting_output_blocks_even_first_plan(
    tmp_path: Path, occupied_by_file: bool
) -> None:
    entry = item(tmp_path)
    output = tmp_path / "整理结果"
    if occupied_by_file:
        output.write_bytes(b"HARNESS existing")
    else:
        output.mkdir()
        (output / "HARNESS_original.txt").write_bytes(b"do not overwrite")
    before = state(tmp_path)
    for _ in range(2):
        result = _plan(str(tmp_path), (entry,))
        assert "Organization output already exists" in result.diagnostics
        assert result.diagnostics
    assert state(tmp_path) == before


def test_output_subtree_is_rejected_as_input_not_silently_consumed(
    tmp_path: Path,
) -> None:
    entry = item(tmp_path, "整理结果/HARNESS_input.txt")
    with pytest.raises(ValueError, match="output"):
        _plan(str(tmp_path), (entry,))


def test_source_outside_workspace_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "HARNESS_workspace"
    root.mkdir()
    entry = item(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        _plan(str(root), (entry,))


def test_symlink_source_is_rejected(tmp_path: Path) -> None:
    original = item(tmp_path)
    link = tmp_path / "HARNESS_link.txt"
    try:
        link.symlink_to(original.source.path)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Symlink creation unavailable: {exc}")
    entry = replace(original, source=_Source("link", str(link), link.name))
    with pytest.raises(ValueError, match="Links/reparse"):
        _plan(str(tmp_path), (entry,))


def test_source_filename_mismatch_is_rejected(tmp_path: Path) -> None:
    entry = item(tmp_path)
    entry = replace(entry, source=replace(entry.source, filename="HARNESS_other.txt"))
    with pytest.raises(ValueError, match="mismatch"):
        _plan(str(tmp_path), (entry,))


def test_symbolic_link_parent_is_rejected(tmp_path: Path) -> None:
    entry = item(tmp_path, "HARNESS_real/HARNESS_source.txt")
    link = tmp_path / "HARNESS_alias"
    try:
        link.symlink_to(tmp_path / "HARNESS_real", target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Directory symlink unavailable: {exc}")
    entry = replace(
        entry, source=replace(entry.source, path=str(link / entry.source.filename))
    )
    with pytest.raises(ValueError, match="Links/reparse"):
        _plan(str(tmp_path), (entry,))


def test_missing_workspace_and_directory_source_fail(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        _plan(str(tmp_path / "HARNESS_absent"), ())
    source = tmp_path / "HARNESS_directory"
    source.mkdir()
    entry = _Item(_Source("id", str(source), source.name), None, ())
    with pytest.raises(ValueError, match="regular file"):
        _plan(str(tmp_path), (entry,))


def test_traversal_source_is_not_resolved_into_safe_spelling(tmp_path: Path) -> None:
    entry = item(tmp_path)
    entry = replace(
        entry,
        source=replace(
            entry.source,
            path=str(tmp_path / "HARNESS_unused" / ".." / entry.source.filename),
        ),
    )
    with pytest.raises(ValueError, match="non-traversing"):
        _plan(str(tmp_path), (entry,))


def test_unconfirmed_item_does_not_block_other_explicit_selection(
    tmp_path: Path,
) -> None:
    selected = item(tmp_path)
    unknown = item(tmp_path, "HARNESS_unknown.dat", category=None)
    result = _plan(str(tmp_path), (selected, unknown))
    assert [mapping.disposition for mapping in result.mappings] == [
        "proposed",
        "pending",
    ]
    assert len([m for m in result.mappings if m.disposition == "proposed"]) == 1


def test_different_workspace_preserves_relative_targets(tmp_path: Path) -> None:
    roots = [tmp_path / "HARNESS_first", tmp_path / "HARNESS_second"]
    results = []
    for root in roots:
        root.mkdir()
        entry = item(root)
        results.append(_plan(str(root), (entry,)))
    assert results[0].mappings[0].target == results[1].mappings[0].target
    assert results[0].mappings[0].source.path != results[1].mappings[0].source.path


def test_duplicate_identity_keeps_first_but_contradiction_fails(tmp_path: Path) -> None:
    entry = item(tmp_path)
    assert len(_plan(str(tmp_path), (entry, entry)).mappings) == 1
    with pytest.raises(ValueError, match="Contradictory"):
        _plan(str(tmp_path), (entry, replace(entry, category="其他")))


def test_invalid_unselected_item_is_still_checked(tmp_path: Path) -> None:
    entry = item(tmp_path, selected=False)
    Path(entry.source.path).unlink()
    with pytest.raises(FileNotFoundError):
        _plan(str(tmp_path), (entry,))


def test_changed_source_is_not_claimed_as_fresh_analysis(tmp_path: Path) -> None:
    # This lexical draft supplies no approved digest or history claim. This test
    # deliberately makes the remaining A evidence/approval dependency explicit.
    entry = item(tmp_path)
    path = Path(entry.source.path)
    path.write_text("HARNESS changed bytes", encoding="utf-8")
    result = _plan(str(tmp_path), (entry,))
    assert result.mappings[0].disposition == "proposed"
    assert not hasattr(result, "approved")
    assert not hasattr(result, "source_sha256")
    assert not (tmp_path / "整理结果").exists()
