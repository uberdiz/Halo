"""Duplicate merging between the Windows folders and the HalOS ones: found by content, proposed, only approved items
done, through the undo journal, never touching Windows."""
import pytest

from core import merge_plan as mp
from core.migration_journal import Journal


@pytest.fixture
def two_sides(tmp_path):
    old = tmp_path / "windows/Users/me/Documents"
    new = tmp_path / "home/Documents"
    for root in (old, new):
        (root / "Taxes").mkdir(parents=True)
    (old / "Taxes/2025.pdf").write_bytes(b"same content" * 1000)
    (new / "Taxes/2025.pdf").write_bytes(b"same content" * 1000)
    (old / "cv.docx").write_bytes(b"old cv")
    (new / "CV.docx").write_bytes(b"new cv, edited on HalOS")
    (old / "only-windows.txt").write_text("x")
    (new / "only-halos.txt").write_text("y")
    return tmp_path, old, new


def test_proposal_finds_identical_and_conflicting_files(two_sides):
    _tmp, old, new = two_sides
    plan = mp.propose(old, new)
    kinds = {i.rel: i.kind for i in plan.items}
    assert kinds == {"Taxes/2025.pdf": "same", "cv.docx": "conflict"}
    assert plan.bytes_same == 12000 and "1 files are on both sides" in plan.summary()


def test_only_approved_items_happen_and_all_can_be_undone(two_sides):
    tmp, old, new = two_sides
    plan = mp.propose(old, new)
    journal = Journal(tmp / "journal.jsonl", protect=[tmp / "windows"])
    same = next(i for i in plan.items if i.kind == "same")
    conflict = next(i for i in plan.items if i.kind == "conflict")
    done = mp.apply(plan, journal, approved=[same, conflict], duplicates=tmp / "home/Duplicates")
    assert done == {"same": 1, "conflict": 1}
    assert (tmp / "home/Duplicates/Taxes/2025.pdf").exists() and not (new / "Taxes/2025.pdf").exists()
    assert (new / "CV (Windows).docx").read_bytes() == b"old cv" and (new / "CV.docx").read_bytes().startswith(b"new")
    assert (old / "Taxes/2025.pdf").exists() and (old / "cv.docx").exists()          # Windows untouched
    journal.undo()
    assert (new / "Taxes/2025.pdf").exists() and not (new / "CV (Windows).docx").exists()


def test_nothing_happens_without_approval(two_sides):
    tmp, old, new = two_sides
    plan = mp.propose(old, new)
    assert mp.apply(plan, Journal(tmp / "j.jsonl"), approved=[]) == {"same": 0, "conflict": 0}
    assert (new / "Taxes/2025.pdf").exists()
