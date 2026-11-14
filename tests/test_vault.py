"""core/vault.py: SAINT's Obsidian vault (seeding, memory notes, the Claude Code --add-dir, the Obsidian skills)."""

from core import vault


def test_ensure_seeds_once_and_keeps_the_persons_edits(tmp_path):
    root = vault.ensure(tmp_path / "v", skills=False)
    for rel in ("CLAUDE.md", "AGENTS.md", "HalOS/What HalOS and SAINT can do.md", "HalOS/This PC.md"):
        assert (root / rel).is_file(), rel
    assert "Memory/" in (root / "CLAUDE.md").read_text(encoding="utf-8")
    (root / "CLAUDE.md").write_text("mine", encoding="utf-8")
    vault.ensure(root, skills=False)
    assert (root / "CLAUDE.md").read_text(encoding="utf-8") == "mine"


def test_remember_writes_a_note_and_appends_to_the_same_title(tmp_path):
    n = vault.remember("Sebastian's dog is called Max", title="Dog", tags=["person", "pets"], root=tmp_path)
    assert n == tmp_path / "Memory" / "Dog.md"
    text = n.read_text(encoding="utf-8")
    assert text.startswith("---\ncreated:") and "tags: [person, pets]" in text and "- Sebastian's dog is called Max" in text
    vault.remember("Max is a beagle", title="Dog", root=tmp_path)
    assert "- Max is a beagle" in n.read_text(encoding="utf-8")
    assert vault.remember("likes: tea / coffee?", root=tmp_path).name == "likes tea  coffee.md".replace("  ", " ")
    try:
        vault.remember("  ", root=tmp_path)
        assert False
    except ValueError:
        pass


def test_claude_args_add_the_vault(monkeypatch, tmp_path):
    monkeypatch.setenv("SAINT_VAULT", str(tmp_path / "brain"))
    assert vault.claude_args() == ["--add-dir", str(tmp_path / "brain")]
    monkeypatch.setattr(vault, "ensure", lambda: (_ for _ in ()).throw(PermissionError("read-only")))
    assert vault.claude_args() == []


SKILL = b"---\nname: %s\ndescription: x\n---\n# body\n"


def test_install_skills_checks_downloads_and_fails_gracefully(tmp_path):
    asked = []

    def fetch(url):
        asked.append(url)
        name = url.split("/skills/")[1].split("/")[0]
        return SKILL % name.encode() if url.endswith("SKILL.md") else b"ref"
    assert vault.install_skills(tmp_path, fetch) == ["obsidian-markdown", "obsidian-bases", "json-canvas"]
    assert vault.skills_installed(tmp_path)
    assert (tmp_path / "obsidian-markdown" / "references" / "CALLOUTS.md").read_bytes() == b"ref"
    assert all(u.startswith("https://raw.githubusercontent.com/kepano/obsidian-skills/") for u in asked)
    assert vault.install_skills(tmp_path, fetch) == []                 # already there: nothing fetched again

    def offline(url):
        raise OSError("no network")
    assert vault.install_skills(tmp_path / "off", offline) == [] and not (tmp_path / "off").exists()
    assert vault.install_skills(tmp_path / "bad", lambda u: b"<html>not a skill</html>") == []
    assert not (tmp_path / "bad").exists()

