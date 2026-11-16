"""SAINT Link carries the whole Evolve side between PCs: SAINT Vault (notes, Fix notes + screenshots) and Evolve chats."""

from modules.link import sync


def _engine(tmp_path, name, root):
    return sync.SyncEngine(name, adapters=[sync.FolderAdapter("vault", root)],
                           mirror=sync.Mirror(str(tmp_path / f"{name}.db")))


def _exchange(a, b):
    a.scan(); b.scan()
    want, offer = a.diff(b.manifest())
    b.apply(offer)
    want, offer = b.diff(a.manifest())
    a.apply(offer)


def test_vault_notes_and_screenshots_reach_the_other_pc_and_deletes_follow(tmp_path):
    pc1, pc2 = tmp_path / "pc1", tmp_path / "pc2"
    (pc1 / "Fix" / "shots").mkdir(parents=True)
    (pc1 / "Fix" / "note.md").write_text("---\nstatus: open\n---\nAvatar floats off screen", encoding="utf-8")
    (pc1 / "Fix" / "shots" / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(range(256)))
    (pc1 / ".obsidian").mkdir()
    (pc1 / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")      # per-window: stays here
    pc2.mkdir()
    a, b = _engine(tmp_path, "pc1", pc1), _engine(tmp_path, "pc2", pc2)
    _exchange(a, b)
    assert (pc2 / "Fix" / "note.md").read_text(encoding="utf-8").endswith("off screen")
    assert (pc2 / "Fix" / "shots" / "a.png").read_bytes() == (pc1 / "Fix" / "shots" / "a.png").read_bytes()
    assert not (pc2 / ".obsidian" / "workspace.json").exists()

    (pc2 / "Fix" / "note.md").write_text("---\nstatus: done\n---\nAvatar floats off screen", encoding="utf-8")
    _exchange(a, b)
    assert "status: done" in (pc1 / "Fix" / "note.md").read_text(encoding="utf-8")

    (pc1 / "Fix" / "shots" / "a.png").unlink()
    _exchange(a, b)
    assert not (pc2 / "Fix" / "shots" / "a.png").exists()


def test_a_peer_cannot_write_outside_the_folder_or_odd_files(tmp_path):
    ad = sync.FolderAdapter("vault", tmp_path / "v")
    refused = ad.apply_batch([("../evil.md", {"text": "x"}), ("/etc/x.md", {"text": "x"}), ("C:/x.md", {"text": "x"}),
                              ("run.sh", {"text": "x"}), ("big.md", {"text": "x" * (ad.MAX_FILE + 1)}),
                              ("ok.md", {"text": "fine"})])
    assert refused == ["../evil.md", "/etc/x.md", "C:/x.md", "run.sh", "big.md"]
    assert (tmp_path / "v" / "ok.md").read_text(encoding="utf-8") == "fine"
    assert not (tmp_path / "evil.md").exists()


def test_pcs_offer_vault_and_evolve_chats():
    kinds = {a.kind for a in sync.default_adapters()}
    assert {"vault", "evolvechat"} <= kinds
