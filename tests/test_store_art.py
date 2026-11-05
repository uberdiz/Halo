"""Store artwork (core/store_art.py): Flathub's own metadata, cached; nothing invented, nothing off-site."""

import json

from core import store_art
from core.store import Result

APPSTREAM = {"icon": "https://dl.flathub.org/media/x/icons/128x128/a.png", "developer_name": "Blender Foundation",
             "summary": "3D creation", "branding": [{"type": "primary", "value": "#ffd5c2", "scheme_preference": "light"},
                                                     {"type": "primary", "value": "#3a1b0a", "scheme_preference": "dark"}],
             "screenshots": [{"sizes": [{"src": "https://dl.flathub.org/s_2000.png", "width": "2000"},
                                        {"src": "https://dl.flathub.org/s_752.png", "width": "752"},
                                        {"src": "https://dl.flathub.org/s_224.png", "width": "224"}]}]}


def test_parse_appstream_keeps_real_fields():
    m = store_art.parse_appstream(APPSTREAM)
    assert m == {"icon": APPSTREAM["icon"], "screenshot": "https://dl.flathub.org/s_752.png",
                 "screenshots": ["https://dl.flathub.org/s_752.png"],
                 "developer": "Blender Foundation", "summary": "3D creation", "license": "", "homepage": "",
                 "categories": [], "brand_dark": "#3a1b0a", "brand_light": "#ffd5c2"}
    assert store_art.parse_appstream({})["icon"] is None
    more = store_art.parse_appstream({**APPSTREAM, "project_license": "GPL-3.0-or-later",
                                      "urls": {"homepage": "https://blender.org"}, "categories": ["Graphics"],
                                      "developer_name": None, "developer": {"name": "Blender"},
                                      "screenshots": APPSTREAM["screenshots"] * 6})
    assert more["license"] == "GPL-3.0-or-later" and more["homepage"] == "https://blender.org"
    assert more["developer"] == "Blender" and len(more["screenshots"]) == store_art.MAX_SHOTS


LOCAL_XML = """<?xml version="1.0"?>
<components><component type="desktop-application"><id>org.kde.kate</id><name>Kate</name>
<summary>Advanced text editor</summary><summary xml:lang="de">Texteditor</summary>
<developer id="kde.org"><name>KDE</name></developer><project_license>LGPL-2.0+</project_license>
<url type="homepage">https://kate-editor.org</url><categories><category>Utility</category></categories>
<icon type="cached">kate.png</icon><icon type="remote">https://dl.flathub.org/kate.png</icon>
<screenshots><screenshot type="default"><image type="source" width="1920">https://cdn.kde.org/k.png</image>
<image type="thumbnail" width="752">https://cdn.kde.org/k_752.png</image></screenshot></screenshots>
</component></components>"""


def test_local_appstream_xml_and_appstreamcli(tmp_path, monkeypatch):
    m = store_art.parse_appstream_xml(LOCAL_XML, "org.kde.kate")
    assert (m["summary"], m["developer"], m["license"], m["homepage"]) == \
        ("Advanced text editor", "KDE", "LGPL-2.0+", "https://kate-editor.org")
    assert m["icon"] == "https://dl.flathub.org/kate.png" and m["screenshots"] == ["https://cdn.kde.org/k_752.png"]
    assert store_art.parse_appstream_xml("<bad", "x") == {} and store_art.parse_appstream_xml(LOCAL_XML, "y") == {}
    calls = []
    run = lambda argv, **kw: calls.append(argv) or type("R", (), {"returncode": 0, "stdout": LOCAL_XML})()
    assert store_art.local_metadata("org.kde.kate", run=run, which=lambda t: "/usr/bin/" + t)["developer"] == "KDE"
    assert calls == [["appstreamcli", "dump", "org.kde.kate"]]
    assert store_art.local_metadata("org.kde.kate", run=run, which=lambda t: None) == {}
    assert store_art.local_metadata("-x.y.z", run=run, which=lambda t: "x") == {}


def test_metadata_falls_back_to_local_appstream(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    local = lambda i: {"summary": "from this system", "icon": None}

    def down(_u):
        raise ConnectionError("offline")
    assert store_art.metadata("org.kde.kate", fetch=down, local=local)["summary"] == "from this system"
    assert store_art.metadata("org.kde.okular", fetch=lambda u: {}, local=local)["summary"] == "from this system"


def test_flathub_id_for_each_kind_of_result():
    assert store_art.flathub_id(Result("flathub", "org.blender.Blender", "Blender")) == "org.blender.Blender"
    assert store_art.flathub_id(Result("featured", "obs", "OBS", extra={"method": "flatpak",
                                                                        "ref": "com.obsproject.Studio"})) \
        == "com.obsproject.Studio"
    assert store_art.flathub_id(Result("featured", "vscode", "VS Code", extra={"method": "aur", "ref": "x",
                                                                                "art": "com.visualstudio.code"})) \
        == "com.visualstudio.code"
    assert store_art.flathub_id(Result("aur", "blender-git", "blender-git")) is None


def test_metadata_is_cached_and_stale_cache_beats_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    calls = []
    m = store_art.metadata("org.blender.Blender", fetch=lambda u: calls.append(u) or APPSTREAM, now=1000)
    assert m["developer"] == "Blender Foundation" and len(calls) == 1
    store_art.metadata("org.blender.Blender", fetch=lambda u: calls.append(u) or APPSTREAM, now=2000)
    assert len(calls) == 1                                   # fresh cache: no second request

    def down(_u):
        raise ConnectionError("offline")
    m = store_art.metadata("org.blender.Blender", fetch=down, now=1000 + store_art.META_TTL + 1)
    assert m["developer"] == "Blender Foundation"            # expired, but offline: keep what we had
    assert store_art.metadata("bad id/../x", fetch=lambda u: APPSTREAM) == {}


def test_images_only_from_flathub_and_cached(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    got = []
    path = store_art.image("https://dl.flathub.org/a.png", fetch=lambda u: got.append(u) or b"\x89PNG data")
    assert path and open(path, "rb").read() == b"\x89PNG data"
    assert store_art.image("https://dl.flathub.org/a.png", fetch=lambda u: got.append(u) or b"x") == path
    assert len(got) == 1
    assert store_art.image("https://evil.example/a.png", fetch=lambda u: b"x") is None
    assert store_art.image("http://dl.flathub.org/a.png", fetch=lambda u: b"x") is None


def test_catalog_art_ids_are_valid():
    data = json.load(open("packaging/linux/apps/catalog.json", encoding="utf-8"))
    for a in data["apps"]:
        if a.get("art"):
            assert store_art._SAFE_ID.match(a["art"])
