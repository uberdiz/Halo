"""Bring SAINT's and Claude's history from Windows: merged without duplicates, never overwriting, no sign-in
tokens, nothing written to the old disk, and all of it undoable."""
import json

import pytest

from core import migrate_ai
from core.migration_journal import Journal, SourceIsReadOnly


@pytest.fixture
def setup(tmp_path):
    win = tmp_path / "windows"
    profile = win / "Users/me"
    saint = profile / "AppData/Local/SAINT"
    saint.mkdir(parents=True)
    rec = lambda ts, user: json.dumps({"ts": ts, "source": "voice", "user": user, "reply": "ok"})
    (saint / "history.jsonl").write_text("\n".join([rec(100.0, "play jazz"), rec(200.0, "open steam")]) + "\n")
    (saint / "memory").mkdir()
    (saint / "memory/facts.json").write_text('{"name": "Sebastian"}')
    claude = profile / ".claude"
    (claude / "projects/C--code-aide").mkdir(parents=True)
    (claude / "projects/C--code-aide/session1.jsonl").write_text("{}\n")
    (claude / "skills/my-skill").mkdir(parents=True)
    (claude / "skills/my-skill/SKILL.md").write_text("# skill")
    (claude / "settings.json").write_text('{"model": "opus"}')
    (claude / ".credentials.json").write_text('{"token": "secret"}')
    (claude / "history.jsonl").write_text("{}\n")
    (profile / "AppData/Roaming/Claude").mkdir(parents=True)
    (profile / "AppData/Roaming/Claude/claude_desktop_config.json").write_text('{"mcpServers": {}}')
    home = tmp_path / "home"
    data = home / ".local/share/saint"
    data.mkdir(parents=True)
    (data / "history.jsonl").write_text(rec(150.0, "what time is it") + "\n" + rec(200.0, "open steam") + "\n")
    journal = Journal(tmp_path / "journal.jsonl", protect=[win])
    return profile, home, data, journal


def test_saint_history_is_merged_in_order_without_duplicates(setup):
    profile, _home, data, journal = setup
    r = migrate_ai.import_saint(profile, journal, data_dir=data)
    lines = [json.loads(l) for l in (data / "history.jsonl").read_text().splitlines()]
    assert [l["user"] for l in lines] == ["play jazz", "what time is it", "open steam"]
    assert r["history_added"] == 1 and (data / "memory/facts.json").exists()


def test_claude_history_settings_and_skills_come_across_but_not_the_sign_in(setup):
    profile, home, _data, journal = setup
    (home / ".claude").mkdir()
    (home / ".claude/settings.json").write_text('{"model": "sonnet"}')          # already set up on HalOS
    r = migrate_ai.import_claude(profile, journal, home=home)
    assert (home / ".claude/projects/C--code-aide/session1.jsonl").exists()
    assert (home / ".claude/skills/my-skill/SKILL.md").exists()
    assert (home / ".config/Claude/claude_desktop_config.json").exists()
    assert (home / ".claude/settings.json").read_text() == '{"model": "sonnet"}'    # never overwritten
    assert not (home / ".claude/.credentials.json").exists()
    assert r["kept"] == 1 and "Sign in to Claude" in r["note"]


def test_everything_is_undone_and_the_old_disk_untouched(setup):
    profile, home, data, journal = setup
    before = sorted(p.relative_to(profile).as_posix() for p in profile.rglob("*"))
    migrate_ai.import_saint(profile, journal, data_dir=data)
    migrate_ai.import_claude(profile, journal, home=home)
    assert sorted(p.relative_to(profile).as_posix() for p in profile.rglob("*")) == before
    out = journal.undo()
    assert not out["kept"]
    assert not (home / ".claude").exists() and not (data / "memory").exists()
    assert "play jazz" not in (data / "history.jsonl").read_text()                  # the merge was undone too


def test_nothing_found_is_said_plainly(tmp_path):
    empty = tmp_path / "Users/nobody"
    empty.mkdir(parents=True)
    j = Journal(tmp_path / "j.jsonl")
    assert migrate_ai.import_saint(empty, j, data_dir=tmp_path / "d")["found"] is False
    assert "wasn't used" in migrate_ai.import_claude(empty, j, home=tmp_path / "h")["note"]
