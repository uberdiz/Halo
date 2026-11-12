"""The migration undo journal: every change is reversible, and the old OS's partition is never written to."""
import pytest

from core.migration_journal import Journal, SourceIsReadOnly


@pytest.fixture
def setup(tmp_path):
    old = tmp_path / "windows"
    (old / "Users/me/Documents").mkdir(parents=True)
    (old / "Users/me/Documents/cv.txt").write_text("my cv")
    home = tmp_path / "home"
    home.mkdir()
    return Journal(tmp_path / "journal.jsonl", protect=[old]), old, home


def test_copy_write_move_then_undo_puts_everything_back(setup):
    j, old, home = setup
    j.copy_file(old / "Users/me/Documents/cv.txt", home / "Documents/cv.txt")
    (home / "settings.conf").write_text("before")
    j.write_text(home / "settings.conf", "after")
    (home / "loose.txt").write_text("x")
    j.move(home / "loose.txt", home / "Sorted/loose.txt")
    assert (home / "Documents/cv.txt").read_text() == "my cv" and (home / "settings.conf").read_text() == "after"

    out = j.undo()
    assert out["kept"] == [] and out["undone"] >= 3
    assert not (home / "Documents").exists() and not (home / "Sorted").exists()
    assert (home / "settings.conf").read_text() == "before" and (home / "loose.txt").read_text() == "x"
    assert (old / "Users/me/Documents/cv.txt").read_text() == "my cv"           # the source is untouched
    assert j.undo()["undone"] == 0                                               # a second undo does nothing


def test_nothing_is_written_to_the_old_os(setup):
    j, old, home = setup
    (home / "a.txt").write_text("a")
    for change in (lambda: j.copy_file(home / "a.txt", old / "a.txt"),
                   lambda: j.write_text(old / "Users/me/note.txt", "hi"),
                   lambda: j.move(old / "Users/me/Documents/cv.txt", home / "cv.txt"),
                   lambda: j.mkdir(old / "New")):
        with pytest.raises(SourceIsReadOnly):
            change()
    assert sorted(p.name for p in old.rglob("*") if p.is_file()) == ["cv.txt"]


def test_copy_never_overwrites_and_undo_keeps_what_the_user_changed(setup):
    j, old, home = setup
    src = old / "Users/me/Documents/cv.txt"
    j.copy_file(src, home / "cv.txt")
    with pytest.raises(FileExistsError):
        j.copy_file(src, home / "cv.txt")
    (home / "cv.txt").write_text("my cv, edited after the migration")
    out = j.undo()
    assert (home / "cv.txt").exists() and out["kept"] and "changed" in out["kept"][0][1]
