"""Meta+N notes for the agent: saved as open tasks in SAINT Vault, shipped with the shortcut."""
from datetime import datetime
from pathlib import Path

import pytest

from ui import os_notes

ROOT = Path(__file__).resolve().parent.parent


def test_notes_append_as_open_tasks(tmp_path):
    t = datetime(2026, 11, 14, 20, 30)
    p = os_notes.add_note("Volume slider jumps\nwhen I scroll it", "Fix", root=tmp_path, now=t)
    os_notes.add_note("A clock widget", "Add", root=tmp_path, now=t)
    text = p.read_text(encoding="utf-8")
    assert text.startswith("# OS notes") and text.count("# OS notes") == 1
    assert "- [ ] **Fix** (2026-11-14 20:30) Volume slider jumps\n  when I scroll it\n" in text
    assert len(os_notes.open_items(tmp_path)) == 2
    with pytest.raises(ValueError):
        os_notes.add_note("   \n ", root=tmp_path)
    assert os_notes.add_note("x", "Weird", root=tmp_path).read_text(encoding="utf-8").endswith("**Fix** (" +
        datetime.now().strftime("%Y-%m-%d %H:%M") + ") x\n")


def test_shortcut_is_packaged():
    desk = (ROOT / "packaging/linux/rootfs/usr/share/applications/halos-note.desktop").read_text(encoding="utf-8")
    assert "Exec=/usr/bin/halos-note" in desk and "X-KDE-Shortcuts=Meta+N" in desk
    pkg = (ROOT / "packaging/arch/pkgbuilds/saint/PKGBUILD").read_text(encoding="utf-8")
    assert "halos-note," in pkg and "[services][halos-note.desktop]\n_launch=Meta+N" in pkg
    assert "ui.os_notes" in (ROOT / "packaging/linux/rootfs/usr/bin/halos-note").read_text(encoding="utf-8")
    assert "OS notes.md" in (ROOT / "core/vault.py").read_text(encoding="utf-8")
