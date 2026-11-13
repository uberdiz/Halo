"""core/updater.py: versions, channels from faked GitHub JSON, install/swap/rollback in a temp dir. No network."""
import io
import json
import os
import tarfile
from pathlib import Path

import pytest

from core import updater

SHA_A, SHA_B, SHA_C = "a" * 40, "b" * 40, "c" * 40
RELEASES = [
    {"tag_name": "v2.1.0-beta.2", "prerelease": True, "body": "beta notes", "assets": []},
    {"tag_name": "v2.0.0", "prerelease": False, "body": "stable notes", "assets": [
        {"name": "saint-src.tar.gz", "browser_download_url": updater.ASSET_PREFIX + "v2.0.0/saint-src.tar.gz"},
        {"name": "saint-src.tar.gz.sha256", "browser_download_url": updater.ASSET_PREFIX + "v2.0.0/saint-src.tar.gz.sha256"}]},
    {"tag_name": "v2.2.0", "draft": True},
]
COMMITS = {"v2.1.0-beta.2": SHA_B, "v2.0.0": SHA_A, "main": SHA_C}
VERSIONS = {SHA_A: "0.4.0", SHA_B: "0.5.0", SHA_C: "0.5.1"}


def fake_json(url):
    if url.endswith("/releases?per_page=30"):
        return RELEASES
    return {"sha": COMMITS[url.rsplit("/", 1)[1]], "commit": {"message": "dev commit"}}


def fake_text(url):
    if url.endswith(".sha256"):
        return "d" * 64 + "  saint-src.tar.gz\n"
    sha = url.split("/")[-3]
    return f'"""v"""\nVERSION = "{VERSIONS[sha]}"\n'


def test_versions():
    p = updater.parse_version
    assert p("v2.1.0-beta.2") < p("v2.1.0") < p("2.1.1") < p("v10.0")
    assert p("0.4") == p("0.4.0") and p("junk") == ()
    assert updater.is_newer("0.5.0", SHA_B, "0.4.0", SHA_A)
    assert not updater.is_newer("0.3.9", SHA_B, "0.4.0", SHA_A)
    assert updater.is_newer("0.4.0", SHA_B, "0.4.0", SHA_A)          # same version, another commit
    assert not updater.is_newer("0.4.0", SHA_A, "0.4.0", SHA_A)
    assert not updater.is_newer("0.4.0", SHA_B, "0.4.0", "")         # unknown local commit: version only


@pytest.mark.parametrize("channel, ref, latest, asset", [
    ("stable", "v2.0.0", "0.4.0", True), ("beta", "v2.1.0-beta.2", "0.5.0", False), ("dev", "main", "0.5.1", False)])
def test_channels(channel, ref, latest, asset):
    r = updater.check(fake_json, fake_text, {"channel": channel, "branch": "main"},
                      {"version": "0.4.0", "sha": SHA_A}, save=False)
    assert r["ok"] and r["ref"] == ref and r["latest"] == latest
    assert r["available"] == (channel != "stable")
    assert bool(r["asset"]) == asset
    if asset:
        assert r["asset"]["sha256"] == "d" * 64


def test_check_never_raises_offline():
    def down(url):
        raise OSError("no network")
    r = updater.check(down, down, {"channel": "stable", "branch": "main"}, {"version": "0.4.0", "sha": ""}, save=False)
    assert not r["ok"] and not r["available"] and "Couldn't check" in r["message"]


def test_helper_arguments_are_checked():
    assert updater.helper_argv({"sha": SHA_A}) == ["pkexec", updater.HELPER, "install", SHA_A]
    good = {"sha": SHA_A, "asset": {"url": updater.ASSET_PREFIX + "v2/x.tar.gz", "sha256": "d" * 64}}
    assert updater.helper_argv(good)[-2:] == [good["asset"]["url"], "d" * 64]
    evil = {"sha": SHA_A, "asset": {"url": "https://evil.example/x.tar.gz", "sha256": "d" * 64}}
    assert updater.helper_argv(evil) == ["pkexec", updater.HELPER, "install", SHA_A]
    with pytest.raises(ValueError):
        updater.helper_argv({"sha": "main; rm -rf /"})
    for bad in (["install", "main"], ["install", SHA_A, "https://evil.example/x", "d" * 64], ["rm"], []):
        assert updater._root_main(bad) != 0


def _tarball(path: Path, version: str, top="Halo-abc", with_app=True):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        files = {f"{top}/core/version.py": f'VERSION = "{version}"\n', f"{top}/README.md": os.urandom(2000).hex()}   # incompressible: over the 1 KiB floor
        if with_app:
            files[f"{top}/app.py"] = "print('saint')\n"
        for name, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    path.write_bytes(buf.getvalue())
    return path


def test_install_swap_and_rollback(tmp_path):
    import hashlib
    root = tmp_path / "opt"
    app = root / "app"
    (app / "core").mkdir(parents=True)
    (app / "app.py").write_text("old", encoding="utf-8")
    (app / "core" / "version.py").write_text('VERSION = "0.4.0"\n', encoding="utf-8")
    (app / "data/tts/kokoro-onnx").mkdir(parents=True)
    (app / "data/tts/kokoro-onnx/voices.bin").write_bytes(b"voice")
    tb = _tarball(tmp_path / "new.tar.gz", "0.5.0")
    with pytest.raises(ValueError, match="checksum"):
        updater.install_tree(tb, root, SHA_B, "0" * 64)
    assert (app / "app.py").read_text(encoding="utf-8") == "old"         # nothing changed
    digest = hashlib.sha256(tb.read_bytes()).hexdigest()
    assert updater.install_tree(tb, root, SHA_B, digest) == "0.5.0"
    assert (app / "app.py").read_text(encoding="utf-8") == "print('saint')\n"
    assert (app / "data/tts/kokoro-onnx/voices.bin").read_bytes() == b"voice"     # not in git: carried over
    assert json.loads((app / updater.STAMP).read_text(encoding="utf-8"))["sha"] == SHA_B
    assert updater.installed(app) == {"version": "0.5.0", "sha": SHA_B}
    assert updater.can_rollback(root) and not (root / "app.new").exists()
    assert updater.rollback_tree(root) == "0.4.0"
    assert (app / "app.py").read_text(encoding="utf-8") == "old"
    assert updater.rollback_tree(root) == "0.5.0"                       # and forward again


def test_install_refuses_what_isnt_saint(tmp_path):
    root = tmp_path / "opt"
    (root / "app").mkdir(parents=True)
    (root / "app" / "app.py").write_text("old", encoding="utf-8")
    with pytest.raises(ValueError, match="isn't SAINT"):
        updater.install_tree(_tarball(tmp_path / "x.tar.gz", "1.0", with_app=False), root)
    assert (root / "app" / "app.py").read_text(encoding="utf-8") == "old" and not (root / "app.new").exists()
    tiny = tmp_path / "tiny.tar.gz"
    tiny.write_bytes(b"x")
    with pytest.raises(ValueError, match="bytes"):
        updater.install_tree(tiny, root)
    with pytest.raises(ValueError):
        updater.rollback_tree(root)


def test_helper_and_rule_ship_together():
    pkg = Path(__file__).resolve().parents[1] / "packaging/arch/pkgbuilds/halo-system"
    assert "core/updater.py root" in (pkg / "halo-update").read_text(encoding="utf-8")
    assert "org.halos.update" in (pkg / "50-halo-drives.rules").read_text(encoding="utf-8")
    text = (pkg / "PKGBUILD").read_text(encoding="utf-8")
    assert "usr/lib/halo/halo-update" in text and "org.halos.update.policy" in text
    import re
    src = re.search(r"source=\((.*?)\)", text, re.S)[1].split()
    sums = re.search(r"sha256sums=\((.*?)\)", text, re.S)[1].split()
    assert len(src) == len(sums)


def test_actions_and_phrases(monkeypatch):
    from core import actions
    from core.actions import RISKY, SAFE
    actions.load_builtin()
    assert actions.registry.get("system.check_updates").max_risk == SAFE
    assert actions.registry.get("system.update_saint").max_risk == RISKY
    from modules.agent import os_intents
    monkeypatch.setattr(os_intents, "_available", lambda _a: True)
    assert os_intents.parse_os("check for updates").name == "os.system.check_updates"
    assert os_intents.parse_os("update SAINT").name == "os.system.update_saint"
