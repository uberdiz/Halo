"""Universal installation assistant (core/install_assistant.py) and the Store's filters (core/store.py).
No network and no package tools: every fetch, command and process list is a fixture."""

import json
import os

import pytest

from core import install_assistant as ia
from core import store, winapps
from core.store import Result

SHA = "a" * 64
NO_ALTS = dict(search=lambda q: [])


def gh_release(*names, digest=True, tag="v2.15.2"):
    return {"tag_name": tag, "assets": [
        {"name": n, "browser_download_url": f"https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher/"
                                             f"releases/download/{tag}/{n}",
         **({"digest": f"sha256:{SHA}"} if digest else {})} for n in names]}


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(winapps, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(winapps, "PREFIXES", tmp_path / "wine")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    return tmp_path


# ---------------------------------------------------------------- detect
def test_kinds_by_file_name_and_refusals_say_why():
    assert ia.kind_of("heroic-2.1-1-x86_64.pkg.tar.zst") == "pacman"
    assert ia.kind_of("Heroic.flatpakref") == "flatpakref"
    assert ia.kind_of("Heroic-2.1.AppImage") == "appimage"
    assert ia.kind_of("obsidian_1.5_amd64.deb") == "deb"
    assert ia.kind_of("npp.Installer.x64.exe") == "windows" and ia.kind_of("app.msi") == "windows"
    for bad, word in (("x.rpm", "RPM"), ("x.dmg", "macOS"), ("x.zip", "archive"), ("x.txt", "recognise")):
        with pytest.raises(ValueError, match=word):
            ia.kind_of(bad)


def test_github_release_picks_the_native_package_and_githubs_digest():
    rel = gh_release("Heroic-2.15.2-arm64.AppImage", "Heroic-2.15.2.AppImage", "heroic_2.15.2_amd64.deb",
                     "heroic-2.15.2-1-x86_64.pkg.tar.zst", "Heroic-2.15.2-Setup.exe", "latest-linux.yml")
    calls = []
    t = ia.detect("https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher",
                  fetch_json=lambda u: calls.append(u) or rel, fetch_text=lambda u: "")
    assert calls == ["https://api.github.com/repos/Heroic-Games-Launcher/HeroicGamesLauncher/releases/latest"]
    assert (t.kind, t.filename, t.sha256, t.name) == ("pacman", "heroic-2.15.2-1-x86_64.pkg.tar.zst", SHA, "heroic")
    assert "release v2.15.2" in t.origin and t.checksum_from.startswith("GitHub")


def test_github_tag_and_checksum_file_in_the_release():
    rel = gh_release("App-1.0.AppImage", "SHA256SUMS", digest=False, tag="v1.0")
    sums = f"{'b' * 64}  App-1.0.AppImage\n{'c' * 64}  other\n"
    seen = []
    t = ia.detect("https://github.com/o/app/releases/tag/v1.0", fetch_json=lambda u: seen.append(u) or rel,
                  fetch_text=lambda u: sums)
    assert seen[0].endswith("/releases/tags/v1.0")
    assert t.kind == "appimage" and t.sha256 == "b" * 64 and t.checksum_from == "SHA256SUMS in the same release"


def test_github_release_with_nothing_for_halo():
    with pytest.raises(ValueError, match="nothing Halo can install"):
        ia.detect("https://github.com/o/r/releases/latest",
                  fetch_json=lambda u: gh_release("app-macos.dmg", "app-arm64.deb"), fetch_text=lambda u: "")


def test_checksum_file_formats():
    assert ia.parse_checksums(f"{SHA} *dir/app.deb", "app.deb") == SHA
    assert ia.parse_checksums(f"SHA256 (app.deb) = {SHA.upper()}", "app.deb") == SHA
    assert ia.parse_checksums(SHA, "anything") == SHA
    assert ia.parse_checksums(f"{SHA}  other.deb", "app.deb") == ""


def test_plain_links_flathub_and_bad_inputs():
    t = ia.detect("https://example.org/dl/Obsidian-1.5.3.AppImage")
    assert (t.kind, t.sha256, t.origin, t.name) == ("appimage", "", "example.org", "Obsidian")
    assert ia.detect("https://flathub.org/apps/com.heroicgameslauncher.hgl").flatpak_id == "com.heroicgameslauncher.hgl"
    assert ia.detect("org.gnome.Calculator").kind == "flathub"
    with pytest.raises(ValueError, match="https"):
        ia.detect("http://example.org/a.AppImage")
    with pytest.raises(ValueError, match="no file"):
        ia.detect("Heroic-2.1.AppImage", isfile=lambda p: False)
    with pytest.raises(ValueError):
        ia.detect("")


def test_local_file_has_its_checksum_worked_out(tmp_path):
    f = tmp_path / "tool-1.0-1-any.pkg.tar.zst"
    f.write_bytes(b"pkg")
    t = ia.detect(str(f))
    assert t.kind == "pacman" and t.path and t.sha256 == ia.sha256_file(str(f)) and t.name == "tool"


# ---------------------------------------------------------------- plans
def test_pacman_plan_downloads_with_the_checksum_and_is_high_risk():
    t = ia.Target("pacman", "heroic", filename="heroic-2.1-1-x86_64.pkg.tar.zst",
                  url="https://github.com/o/r/releases/download/v1/heroic-2.1-1-x86_64.pkg.tar.zst", sha256=SHA,
                  checksum_from="GitHub", origin="github.com/o/r")
    p = ia.build_plan(t, python="py", **NO_ALTS)
    assert p.app_id == "pacman:heroic" and p.risk == "high"
    fetch, install = p.steps
    assert fetch.argv[0] == "py" and fetch.argv[2:5] == ["fetch", t.url, SHA]
    assert install.argv[:4] == ["pkexec", "pacman", "-U", "--noconfirm"] and install.argv[4] == fetch.argv[5]
    assert install.needs_admin and p.verify == {"pacman": "heroic"}
    with pytest.raises(ValueError, match="aarch64"):
        ia.build_plan(ia.Target("pacman", "x", filename="x-1-1-aarch64.pkg.tar.zst", url=t.url), **NO_ALTS)


def test_no_checksum_is_said_and_raises_the_risk():
    t = ia.detect("https://example.org/Obsidian-1.5.3.AppImage")
    p = ia.build_plan(t, exists=lambda p: True, **NO_ALTS)
    assert p.risk == "high" and any("no checksum" in r for r in p.reasons)
    assert p.steps[0].argv[4] == winapps.UNVERIFIED and "no checksum published" in p.steps[0].label
    assert "none published" in p.checksum
    assert [s.argv[2] for s in p.steps] == ["fetch", "appimage"]          # libfuse there: no FUSE step


def test_appimage_needs_fuse2_when_missing():
    t = ia.Target("appimage", "Tool", filename="Tool.AppImage", url="https://github.com/o/r/x/Tool.AppImage",
                  sha256=SHA)
    p = ia.build_plan(t, exists=lambda p: False, **NO_ALTS)
    assert any(s.argv[-1] == "fuse2" for s in p.steps) and p.risk == "medium"


def test_flatpakref_installs_exactly_what_was_read(cache):
    ref = "[Flatpak Ref]\nName=com.example.App\nTitle=Example\nUrl=https://dl.flathub.org/repo/\n"
    t = ia.detect("https://example.org/Example.flatpakref", fetch_text=lambda u: ref)
    p = ia.build_plan(t, **NO_ALTS)
    path = p.steps[0].argv[-1]
    assert p.steps[0].argv[:-1] == ["flatpak", "install", "--user", "-y", "--noninteractive", "--from"]
    assert open(path, encoding="utf-8").read() == ref and p.risk == "low" and p.verify == {"flatpak": "com.example.App"}
    other = ia.build_plan(ia.detect("https://example.org/E.flatpakref",
                                    fetch_text=lambda u: ref.replace("dl.flathub.org", "repo.evil.example")), **NO_ALTS)
    assert other.risk == "medium" and "repo.evil.example" in other.reasons[0]
    with pytest.raises(ValueError, match="valid app"):
        ia.build_plan(ia.detect("https://example.org/E.flatpakref", fetch_text=lambda u: "[Flatpak Ref]\nName=--x\n"))


def test_windows_app_prefers_the_linux_version_and_refuses_anticheat():
    native = Result("flathub", "notepadqq.Notepadqq", "Notepad++ alternative")
    obs = Result("featured", "obs", "OBS Studio", extra={"method": "flatpak", "ref": "com.obsproject.Studio"})
    t = ia.Target("windows", "OBS Studio", filename="OBS-Studio-30.0-Full-Installer-x64.exe",
                  url="https://github.com/obsproject/obs-studio/releases/download/30/x.exe", sha256=SHA)
    p = ia.build_plan(t, which=lambda x: None, search=lambda q: [native, obs])
    assert p.alternatives == [obs] and "preferred" in p.notes[0]
    assert p.steps[0].argv[-3:] == winapps.WINE_PACKAGES                  # Wine first, it isn't installed
    assert p.steps[-1].argv[:2] == ["env", f"WINEPREFIX={winapps.prefix_for('assistant-obs-studio')}"]
    v = ia.build_plan(ia.Target("windows", "Valorant", filename="Install VALORANT.exe",
                                url="https://example.org/x.exe"), **NO_ALTS)
    assert v.blocked and not v.steps and "anti-cheat" in v.blocked


def test_deb_plan_converts_with_debtap():
    t = ia.Target("deb", "obsidian", filename="obsidian_1.5_amd64.deb", url="https://github.com/o/r/a.deb",
                  sha256=SHA)
    p = ia.build_plan(t, which=lambda x: None, python="py", **NO_ALTS)
    assert p.steps[1].argv[-1] == "debtap" and p.steps[2].argv == ["pkexec", "debtap", "-u"]
    assert p.steps[3].argv[:3] == ["py", ia.__file__ if ia.__file__.endswith(".py") else p.steps[3].argv[1], "deb"]
    assert p.risk == "high"


def test_flathub_plan_reuses_the_store_and_alternatives_match_names():
    p = ia.plan_for("com.heroicgameslauncher.hgl", **NO_ALTS)
    assert p.steps[-1].argv[-1] == "com.heroicgameslauncher.hgl" and p.risk == "low"
    assert all(s.apps in ([], ["flatpak:com.heroicgameslauncher.hgl"]) for s in p.steps)
    hits = [Result("repo", "gimp", "gimp"), Result("aur", "gimp-git", "gimp-git"), Result("repo", "x", "unrelated")]
    assert ia.alternatives("GIMP", lambda q: hits) == [hits[0]]
    assert ia.alternatives("GIMP", lambda q: (_ for _ in ()).throw(OSError())) == []


# ---------------------------------------------------------------- verify
class Proc:
    def __init__(self, rc=None, pid=10):
        self.rc, self.pid = rc, pid

    def poll(self):
        return self.rc


def clock_from(times):
    it = iter(times)
    return lambda: next(it)


def test_launch_passes_when_its_process_appears():
    lists = iter([[(1, "plasmashell")], [(1, "plasmashell"), (55, "/opt/heroic/heroic --no-sandbox")]])
    ok, why = ia.launch_check(["/usr/bin/heroic", "%U"], popen=lambda *a, **k: Proc(),
                              procs=lambda: next(lists), clock=clock_from([0, 0, 1]), sleep=lambda s: None)
    assert ok and "process" in why


def test_launch_fails_when_it_exits_with_an_error():
    ok, why = ia.launch_check(["/usr/bin/app"], popen=lambda *a, **k: Proc(rc=127), procs=lambda: [],
                              clock=clock_from([0, 0, 1]), sleep=lambda s: None)
    assert not ok and "code 127" in why
    ok, why = ia.launch_check(["missing"], popen=lambda *a, **k: (_ for _ in ()).throw(OSError("nope")),
                              procs=lambda: [])
    assert not ok and "couldn't start" in why


def test_launch_still_running_after_the_wait_passes():
    ok, why = ia.launch_check(["flatpak", "run", "com.x.Y"], popen=lambda *a, **k: Proc(), procs=lambda: [],
                              clock=clock_from([0, 0, 9, 9]), sleep=lambda s: None, wait=8)
    assert ok and "still running" in why


class Run:
    def __init__(self, rc=0, out=""):
        self.rc, self.out, self.calls = rc, out, []

    def __call__(self, argv, **kw):
        self.calls.append(argv)
        return type("R", (), {"returncode": self.rc, "stdout": self.out})()


def test_verify_finds_the_desktop_entry_of_a_package():
    run = Run(out="/usr/bin/heroic\n/usr/share/applications/heroic.desktop\n")
    read = lambda p: "[Desktop Entry]\nName=Heroic\nExec=/usr/bin/heroic %U\n[Desktop Action x]\nExec=bad\n"
    ok, argv, _ = ia.launcher({"pacman": "heroic"}, run=run, read=read)
    assert ok and argv == ["/usr/bin/heroic"] and run.calls == [["pacman", "-Qlq", "heroic"]]
    res = ia.verify({"pacman": "heroic"}, run=Run(rc=1))
    assert res == {"installed": False, "launched": None, "detail": "pacman doesn't list heroic."}
    res = ia.verify({"flatpak": "com.x.Y"}, launch=False, run=Run())
    assert res["installed"] and res["launched"] is None


def test_verify_wine_app_by_its_menu_entry(tmp_path):
    prefix = str(winapps.PREFIXES / "assistant-npp")
    entry = "[Desktop Entry]\nExec=env WINEPREFIX=\"%s\" wine C:\\\\Program\\ Files\\\\npp.exe\n" % prefix
    ok, argv, _ = ia.launcher({"wine_prefix": prefix}, exists=lambda p: True, read=lambda p: entry,
                              walk=lambda root: [(root, [], ["npp.desktop", "x.txt"])])
    assert ok and argv[0] == "env" and ia._token(argv) == "C:\\Program Files\\npp.exe".split("\\")[-1]


# ---------------------------------------------------------------- history, uninstall, repair
def test_history_records_merges_and_keeps_events(tmp_path):
    h = ia.History(tmp_path / "h.json")
    p = ia.plan_for("com.heroicgameslauncher.hgl", **NO_ALTS)
    h.record(ia.entry_from_plan(p, True, {"installed": True, "launched": True, "detail": "it started"}), now=1)
    h.record({"id": p.app_id, "status": "uninstalled"}, "uninstall", True, now=2)
    (e,) = h.entries()
    assert e["status"] == "uninstalled" and e["installed_at"] == 1 and [x["what"] for x in e["events"]] == \
        ["uninstall", "install"]
    bad = ia.entry_from_plan(p, True, {"installed": True, "launched": False, "detail": "code 1"})
    assert bad["status"] == "installed, won't start"


def test_store_installs_share_the_history_identity():
    e = ia.entry_from_store(Result("flathub", "com.heroicgameslauncher.hgl", "Heroic"), True)
    assert e["id"] == "flatpak:com.heroicgameslauncher.hgl" and e["verify"] == {"flatpak": e["id"][8:]}
    assert ia.entry_from_store(Result("aur", "paru-bin", "paru-bin"), False)["status"] == "failed"
    pick = Result("featured", "obs", "OBS", extra={"method": "flatpak", "ref": "com.obsproject.Studio"})
    assert ia.entry_from_store(pick, True)["id"] == "flatpak:com.obsproject.Studio"


def test_uninstall_is_rebuilt_from_checked_identifiers():
    assert ia.uninstall_steps({"id": "a", "verify": {"pacman": "heroic"}})[0].argv == \
        ["pkexec", "pacman", "-R", "--noconfirm", "heroic"]
    assert ia.uninstall_steps({"id": "a", "verify": {"flatpak": "com.x.Y"}})[0].argv[:3] == \
        ["flatpak", "uninstall", "--user"]
    assert ia.uninstall_steps({"id": "a", "verify": {"appimage": "tool"}}, python="py")[0].argv[2:] == \
        ["remove-appimage", "tool"]
    for v in ({"pacman": "--root=/"}, {"flatpak": "x; rm"}, {"appimage": "../x"}, {"wine_prefix": "/home"}, {}):
        with pytest.raises(ValueError):
            ia.uninstall_steps({"id": "a", "verify": v})
    ok = ia.uninstall_steps({"id": "a", "verify": {"wine_prefix": str(winapps.PREFIXES / "assistant-npp")}})
    assert ok[0].argv[2] == "remove-wine"


def test_repair_reinstalls_over_what_is_there():
    e = ia.entry_from_store(Result("repo", "blender", "Blender"), True)
    (s,) = ia.repair_steps(e)
    assert "--needed" not in s.argv and s.argv[-1] == "blender"
    e = ia.entry_from_plan(ia.plan_for("com.x.Y", **NO_ALTS), True)
    steps = ia.repair_steps(e, plan_kw=NO_ALTS)
    assert steps[-1].argv[:3] == ["flatpak", "install", "--reinstall"]
    assert "--needed" in steps[0].argv or steps[0].argv[1] == "remote-add"


def test_helpers_add_and_remove_an_appimage(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    src = tmp_path / "Tool.AppImage"
    src.write_bytes(b"ELF")
    assert ia.install_appimage(str(src), "tool", "Tool\nExec=evil") == 0
    desktop = tmp_path / "share" / "applications" / "saint-appimage-tool.desktop"
    text = desktop.read_text(encoding="utf-8")
    assert "Name=Tool Exec=evil\n" in text and [l for l in text.splitlines() if l.startswith("Exec=")] != [] \
        and len([l for l in text.splitlines() if l.startswith("Exec=")]) == 1      # no injected line
    assert (tmp_path / "Applications" / "tool.AppImage").exists()
    assert ia.remove_appimage("tool") == 0 and not desktop.exists()
    assert ia.install_appimage(str(src), "../x", "x") == 2


def test_remove_wine_only_inside_saints_prefixes(tmp_path):
    prefix = winapps.PREFIXES / "assistant-npp"
    (prefix / "drive_c").mkdir(parents=True)
    menu = tmp_path / "share" / "applications" / "wine" / "Programs"
    menu.mkdir(parents=True)
    (menu / "npp.desktop").write_text(f"Exec=env WINEPREFIX=\"{prefix.resolve()}\" wine x", encoding="utf-8")
    (menu / "other.desktop").write_text("Exec=env WINEPREFIX=/elsewhere wine y", encoding="utf-8")
    assert ia.remove_wine(str(tmp_path)) == 2
    assert ia.remove_wine(str(prefix)) == 0
    assert not prefix.exists() and not (menu / "npp.desktop").exists() and (menu / "other.desktop").exists()


# ---------------------------------------------------------------- Store filters
def test_compatibility_type_and_filters():
    repo = Result("repo", "blender", "Blender", installed=True)
    lib = Result("repo", "libfoo", "libfoo")
    game = Result("flathub", "com.x.Game", "Game", extra={"categories": ["Game"]})
    pick = Result("featured", "vscode", "VS Code", extra={"method": "aur", "category": "Developer"})
    blocked = Result("windows", "RiotGames.Valorant.Live", "Valorant", extra={"blocked": "anti-cheat"})
    wine = Result("windows", "Notepad++.Notepad++", "Notepad++")
    assert [store.compatibility(r) for r in (repo, game, pick, blocked, wine)] == \
        ["native", "flatpak", "aur", "blocked", "wine"]
    assert [store.app_type(r) for r in (repo, lib, game, pick)] == ["app", "system", "game", "developer"]
    allr = [repo, lib, game, pick, blocked, wine]
    assert [r.id for r in allr if store.matches(r)] == ["blender", "libfoo", "com.x.Game", "vscode",
                                                        "Notepad++.Notepad++"]
    assert [r.id for r in allr if store.matches(r, "blocked")] == ["RiotGames.Valorant.Live"]
    assert [r.id for r in allr if store.matches(r, installed=True)] == ["blender"]
    assert [r.id for r in allr if store.matches(r, "native", False, "system")] == ["libfoo"]


def test_installed_check_per_source():
    run = Run(rc=0)
    assert store.installed(Result("flathub", "com.x.Y", "Y"), run=run) and run.calls[-1] == ["flatpak", "info", "com.x.Y"]
    assert not store.installed(Result("aur", "paru-bin", "p"), run=Run(rc=1))
    assert not store.installed(Result("windows", "A.B", "A"))


def test_flathub_search_keeps_categories():
    hits = store.search_flathub("x", post=lambda u, b: {"hits": [{"app_id": "com.x.Game", "name": "G",
                                                                   "main_categories": "game"}]})
    assert hits[0].extra["categories"] == ["game"] and store.app_type(hits[0]) == "game"


def test_winapps_names_and_unverified_fetch(tmp_path, monkeypatch):
    assert winapps.blocked("", "FACEIT AC Setup")[0].startswith("It uses kernel-level anti-cheat")
    assert winapps.blocked("", "Notepad++ Installer") is None

    class R:
        headers = {"content-length": "3"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def raise_for_status(self):
            pass

        def iter_content(self, n):
            yield b"abc"
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    dest = tmp_path / "f.bin"
    assert winapps.fetch("https://x.example/f.bin", winapps.UNVERIFIED, str(dest)) == 0 and dest.read_bytes() == b"abc"
    assert winapps.fetch("https://x.example/f.bin", "nope", str(dest)) == 2
