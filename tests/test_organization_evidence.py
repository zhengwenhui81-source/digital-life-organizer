"""Private planner evidence/selection boundaries; no public classifier schema."""

from __future__ import annotations

import copy
import os
from dataclasses import replace
from pathlib import Path, PurePosixPath

import pytest

from fileforge.organization._draft import _Item, _plan, _Source


def entry(root: Path, name: str = "中文 文件.bin") -> _Item:
    path = root / name
    path.write_bytes(b"fixture only; no classifier assertion")
    return _Item(
        _Source(None, str(path), name),
        "动态类别",
        ({"type": "synthetic", "reference": {"raw_index": 2}, "quote": "fixture"},),
        selected=True,
        needs_confirmation=False,
        basis="synthetic_basis",
        reason="Explicit synthetic test decision",
    )


def test_scan_reference_needs_no_invented_file_id(tmp_path):
    item = entry(tmp_path)
    draft = _plan(str(tmp_path), (item,))
    mapping = draft.mappings[0]
    assert mapping.source == item.source
    assert mapping.source.file_id is None
    assert mapping.target == "整理结果/动态类别/中文 文件.bin"
    assert not PurePosixPath(mapping.target).is_absolute()
    assert not hasattr(draft, "preview_id")
    assert not hasattr(draft, "operations")


def test_structured_evidence_basis_reason_are_detached_and_unchanged(tmp_path):
    item = entry(tmp_path)
    before = copy.deepcopy(item.evidence)
    mapping = _plan(str(tmp_path), (item,)).mappings[0]
    assert mapping.evidence == before
    assert mapping.basis == item.basis and mapping.reason == item.reason
    item.evidence[0]["reference"]["raw_index"] = 100
    assert mapping.evidence == before


@pytest.mark.parametrize("selected", [False, True])
def test_unknown_category_keeps_evidence_without_target(tmp_path, selected):
    item = replace(entry(tmp_path), category=None, selected=selected)
    draft = _plan(str(tmp_path), (item,))
    mapping = draft.mappings[0]
    assert mapping.disposition == "pending" and mapping.target is None
    assert mapping.evidence == item.evidence
    assert mapping.basis == item.basis and mapping.reason == item.reason
    assert draft.directories == ()


@pytest.mark.parametrize(
    "selected,confirmed", [(False, False), (False, True), (True, False)]
)
def test_selection_and_confirmation_are_independent(tmp_path, selected, confirmed):
    item = replace(entry(tmp_path), selected=selected, needs_confirmation=not confirmed)
    draft = _plan(str(tmp_path), (item,))
    assert draft.mappings[0].disposition != "proposed"
    assert not draft.directories


@pytest.mark.parametrize(
    "bad", [{1: "value"}, float("nan"), float("inf"), b"bytes", (1,)]
)
def test_non_json_evidence_is_rejected_even_when_unselected(tmp_path, bad):
    item = replace(entry(tmp_path), selected=False, evidence=(bad,))
    with pytest.raises(ValueError):
        _plan(str(tmp_path), (item,))
    assert not (tmp_path / "整理结果").exists()


def test_cyclic_evidence_fails_without_deepcopy_or_writes(tmp_path):
    cyclic = []
    cyclic.append(cyclic)
    item = replace(entry(tmp_path), evidence=(cyclic,))
    with pytest.raises(ValueError, match="cycle"):
        _plan(str(tmp_path), (item,))


def test_duplicate_evidence_uses_strict_types_not_numeric_equality(tmp_path):
    item = replace(entry(tmp_path), evidence=({"score": 1},))
    for changed in [1.0, True]:
        duplicate = replace(item, evidence=({"score": changed},))
        with pytest.raises(ValueError, match="Contradictory"):
            _plan(str(tmp_path), (item, duplicate))


def test_evidence_key_order_does_not_create_duplicate_sources(tmp_path):
    item = replace(entry(tmp_path), evidence=({"a": 1, "b": {"c": 2}},))
    duplicate = replace(item, evidence=({"b": {"c": 2}, "a": 1},))
    assert len(_plan(str(tmp_path), (item, duplicate)).mappings) == 1


def test_same_name_collision_keeps_sources_for_diagnostic_only(tmp_path):
    first = entry(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    second = entry(other)
    draft = _plan(str(tmp_path), (first, second))
    assert "Destination name collision" in draft.diagnostics
    assert len(draft.mappings) == 2
    assert draft.mappings[0].target == draft.mappings[1].target
    assert not (tmp_path / "整理结果").exists()


def test_planning_has_no_write_or_content_read_entry(tmp_path, monkeypatch):
    item = entry(tmp_path)
    before = Path(item.source.path).read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Planner attempted file IO beyond stat/enumeration")

    with monkeypatch.context() as guarded:
        for name in (
            "open",
            "read_bytes",
            "read_text",
            "write_bytes",
            "write_text",
            "mkdir",
            "unlink",
            "rename",
            "replace",
        ):
            guarded.setattr(Path, name, forbidden)
        guarded.setattr(os, "open", forbidden)
        draft = _plan(str(tmp_path), (item,))
    assert draft.mappings[0].disposition == "proposed"
    assert Path(item.source.path).read_bytes() == before


def test_source_removed_after_classification_rejects_entire_draft(tmp_path):
    item = entry(tmp_path)
    Path(item.source.path).unlink()
    with pytest.raises(FileNotFoundError):
        _plan(str(tmp_path), (item,))
    assert not (tmp_path / "整理结果").exists()


def test_reparse_observation_rejected_without_claiming_windows_execution(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    item = entry(tmp_path)
    original = Path.lstat

    def marked(path):
        info = original(path)
        if path != Path(item.source.path):
            return info
        return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)

    monkeypatch.setattr(Path, "lstat", marked)
    with pytest.raises(ValueError, match="reparse"):
        _plan(str(tmp_path), (item,))


def test_changed_bytes_are_not_claimed_as_verified_freshness(tmp_path):
    item = entry(tmp_path)
    Path(item.source.path).write_bytes(b"different bytes before read-only planning")
    draft = _plan(str(tmp_path), (item,))
    assert draft.mappings[0].disposition == "proposed"
    assert not hasattr(draft, "approved")
    assert not hasattr(draft, "source_sha256")
    assert not (tmp_path / "整理结果").exists()
