"""Store artwork (core/store_art.py): Flathub's own metadata, cached; nothing invented, nothing off-site."""

import json

from core import store_art
from core.store import Result

APPSTREAM = {"icon": "https://dl.flathub.org/media/x/icons/128x128/a.png", "developer_name": "Blender Foundation",
             "summary": "3D creation", "branding": [{"type": "primary", "value": "#ffd5c2", "scheme_preference": "light"},
                                                     {"type": "primary", "value": "#3a1b0a", "scheme_preference": "dark"}],
             "screenshots": [{"sizes": [{"src": "https://dl.flathub.org/s_2000.png", "width": "2000"},
                                        {"src": "https://dl.flathub.org/s_1248.png", "width": "1248"},
                                        {"src": "https://dl.flathub.org/s_752.png", "width": "752"},
                                        {"src": "https://dl.flathub.org/s_224.png", "width": "224"}]}]}


def test_parse_appstream_keeps_real_fields():
    m = store_art.parse_appstream(APPSTREAM)
    assert m == {"icon": APPSTREAM["icon"], "screenshot": "https://dl.flathub.org/s_752.png",
                 "screenshots": ["https://dl.flathub.org/s_752.png"], "thumb": "https://dl.flathub.org/s_752.png",
                 "hero": "https://dl.flathub.org/s_1248.png", "shots_large": ["https://dl.flathub.org/s_1248.png"],
                 "description": "",
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


def test_an_old_cache_entry_is_refetched_for_the_new_sizes(tmp_path, monkeypatch):
    """A cache written before hero and card sizes existed would otherwise hide them for a week."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    (store_art.cache_dir() / "org.blender.Blender.json").write_text(json.dumps(
        {"icon": "x", "screenshot": "https://dl.flathub.org/old.png", "_at": 1000}), encoding="utf-8")
    assert store_art.metadata("org.blender.Blender", fetch=lambda u: APPSTREAM, now=1001)["hero"].endswith("s_1248.png")

    def down(_u):
        raise ConnectionError("offline")
    (store_art.cache_dir() / "org.kde.krita.json").write_text(json.dumps(
        {"icon": "x", "screenshot": "https://dl.flathub.org/old.png", "_at": 1000}), encoding="utf-8")
    assert store_art.metadata("org.kde.krita", fetch=down, now=1001)["icon"] == "x"     # stale beats nothing


def test_description_keeps_structure_and_drops_everything_else():
    clean = store_art.clean_description('<p class="x">A <b>bold</b>  <a href="http://e.vil">link</a></p>'
                                        '<ul><li onclick="x">one</li></ul><img src="file:///etc/passwd"><script>1</script>')
    assert clean.startswith("<p>A bold link</p><ul><li>one</li></ul>")
    assert "href" not in clean and "img" not in clean and "<script" not in clean and "onclick" not in clean
    assert store_art.clean_description("&lt;img src=x&gt;") == "&lt;img src=x&gt;"
    assert store_art.clean_description(None) == ""
    assert store_art.parse_appstream({"description": "<p>Hi</p>"})["description"] == "<p>Hi</p>"


def test_packages_get_art_by_exact_name_only(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    calls = []
    hits = {"hits": [{"app_id": "org.other.KritaHelper", "name": "Krita Helper"}, {"app_id": "org.kde.krita", "name": "Krita"}]}
    assert store_art.match_flathub("krita-bin", post=lambda b: calls.append(b) or hits) == "org.kde.krita"
    assert store_art.match_flathub("krita-bin", post=lambda b: calls.append(b) or hits) == "org.kde.krita"
    assert len(calls) == 1                                   # the answer is cached
    assert store_art.match_flathub("kritaish", post=lambda b: hits) == ""     # near isn't good enough

    def down(_b):
        raise ConnectionError("offline")
    assert store_art.match_flathub("blender", post=down) == ""
    assert store_art.match_flathub("blender", post=lambda b: {"hits": [{"app_id": "org.blender.Blender",
                                                                        "name": "Blender"}]}) == "org.blender.Blender"


CATALOG_XML = """<components origin="archlinux-arch-extra">
<component type="desktop-application"><id>org.kde.kate.desktop</id><pkgname>kate</pkgname><name>Kate</name>
<summary>Text editor</summary><description><p>Edits text.</p><p xml:lang="de">Text.</p></description>
<icon type="cached" width="128">kate_kate.png</icon><categories><category>Utility</category></categories>
<screenshots><screenshot><image type="source" width="1920">https://cdn.kde.org/k.png</image></screenshot></screenshots>
</component>
<component type="addon"><id>x.addon</id><pkgname>addon</pkgname><name>Addon</name></component>
</components>"""


def test_system_catalog_lists_apps_with_cached_icons(tmp_path):
    import gzip
    (tmp_path / "xml").mkdir()
    (tmp_path / "icons/archlinux-arch-extra/128x128").mkdir(parents=True)
    icon = tmp_path / "icons/archlinux-arch-extra/128x128/kate_kate.png"
    icon.write_bytes(b"png")
    (tmp_path / "xml/extra.xml.gz").write_bytes(gzip.compress(CATALOG_XML.encode()))
    index = store_art.package_index((str(tmp_path),))
    assert list(index) == ["kate"]                           # desktop apps only
    kate = index["kate"]
    assert (kate["name"], kate["repo"], kate["icon_path"]) == ("Kate", "extra", str(icon))
    assert kate["description"] == "<p>Edits text.</p>" and kate["hero"] == "https://cdn.kde.org/k.png" and kate["local"]
    assert store_art.package_index((str(tmp_path / "none"),)) == {}


def test_system_catalog_images_may_come_from_the_publishers_site(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert store_art.image("https://cdn.kde.org/k.png", fetch=lambda u: b"x") is None
    assert store_art.image("https://cdn.kde.org/k.png", fetch=lambda u: b"x", any_host=True)
    assert store_art.image("http://cdn.kde.org/k.png", fetch=lambda u: b"x", any_host=True) is None


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
