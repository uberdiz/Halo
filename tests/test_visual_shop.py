import hashlib
import json
import zipfile

import pytest

from core import visual_shop as vs
from core.visual_shop import PackError, Shop

PNG = b"\x89PNG\r\n\x1a\n" + b"x" * 40


def manifest(files, **kw):
    fl = [{"path": p, "sha256": hashlib.sha256(b).hexdigest(), "size": len(b)} for p, b in files.items()]
    m = {"id": "my-pack", "name": "My pack", "category": "wallpaper", "creator": "Me", "license": "CC0-1.0",
         "attribution": "none needed", "version": "1.0", "size": sum(f["size"] for f in fl),
         "sha256": vs.package_digest(fl), "compatibility": ["any"], "preview": next(iter(files)), "files": fl}
    m.update(kw)
    return m


def write_pack(d, files, m=None):
    d.mkdir(parents=True, exist_ok=True)
    for p, b in files.items():
        (d / p).parent.mkdir(parents=True, exist_ok=True)
        (d / p).write_bytes(b)
    (d / "manifest.json").write_text(json.dumps(m or manifest(files)))
    return d


@pytest.fixture
def shop(tmp_path):
    return Shop(root=tmp_path / "profile")


def test_builtin_catalog_is_valid_and_present():
    s = Shop(root="unused")
    raw = json.loads(vs.CATALOG.read_text(encoding="utf-8"))["items"]
    assert raw and all(vs.validate(m) == [] for m in raw)
    assert len(s.catalog()) == len(raw)
    assert all(m["creator"] == "HalOS" for m in raw)          # only HalOS-made items ship


def test_builtin_install_verifies_and_uninstalls(shop):
    m = next(m for m in shop.catalog() if m["id"] == "accent-ocean")
    seen = []
    d = shop.install(m, progress=lambda a, b: seen.append((a, b)))
    assert (d / "palette.json").is_file() and "accent-ocean" in shop.installed()
    assert seen[-1][0] == m["size"]
    assert [x["id"] for x in shop.search(view="installed")] == ["accent-ocean"]
    assert shop.uninstall("accent-ocean") and not d.exists() and not shop.installed()


def test_manifest_validation():
    good = manifest({"a.png": PNG})
    assert vs.validate(good) == []
    assert "missing license" in vs.validate({k: v for k, v in good.items() if k != "license"})
    assert vs.validate(dict(good, category="malware"))
    assert vs.validate(dict(good, version="latest"))
    assert vs.validate(dict(good, size=1))
    assert vs.validate(dict(good, preview="nope.png"))
    assert vs.validate("not a dict")


@pytest.mark.parametrize("bad", ["../x.png", "/etc/x.png", "a/../../x.png", "C:/x.png", "a\\x.png", "./x.png"])
def test_traversal_rejected(bad):
    with pytest.raises(PackError):
        vs.safe_rel(bad)
    assert vs.validate(manifest({"a.png": PNG})) == []
    m = manifest({"a.png": PNG})
    m["files"][0]["path"] = bad
    assert vs.validate(m)


@pytest.mark.parametrize("name", ["run.py", "x.sh", "setup.exe", "a.js", "main.qml", "lib.so", "x.desktop", "x"])
def test_executable_types_rejected(name):
    with pytest.raises(PackError):
        vs.safe_rel(name)


def test_program_disguised_as_image_rejected(shop, tmp_path):
    files = {"a.png": b"MZ\x90\x00 this is an exe"}
    with pytest.raises(PackError, match="program"):
        shop.import_pack(write_pack(tmp_path / "p", files))
    svg = {"a.svg": b"<svg><script>alert(1)</script></svg>"}
    with pytest.raises(PackError, match="script"):
        shop.import_pack(write_pack(tmp_path / "q", svg))
    assert not shop.installed()


def test_sha_mismatch_installs_nothing(shop, tmp_path):
    files = {"a.png": PNG, "b.json": b"{}"}
    d = write_pack(tmp_path / "p", files)
    (d / "b.json").write_bytes(b"[]")                          # changed after the manifest was made
    with pytest.raises(PackError, match="sha256"):
        shop.import_pack(d)
    assert not shop.installed() and not (shop.root / "installed" / "wallpaper" / "my-pack").exists()


def test_unlisted_file_rejected(shop, tmp_path):
    d = write_pack(tmp_path / "p", {"a.png": PNG})
    (d / "evil.py").write_text("import os")
    with pytest.raises(PackError, match="not in the manifest"):
        shop.import_pack(d)


def test_zip_import_and_traversal(shop, tmp_path):
    files = {"a.png": PNG, "sub/b.svg": b"<svg/>"}
    z = tmp_path / "pack.zip"
    with zipfile.ZipFile(z, "w") as f:
        f.writestr("manifest.json", json.dumps(manifest(files)))
        for p, b in files.items():
            f.writestr(p, b)
    m = shop.import_pack(z)
    assert (shop.item_dir(m) / "sub" / "b.svg").is_file()
    assert [x["id"] for x in shop.items()].count("my-pack") == 1
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as f:
        f.writestr("manifest.json", json.dumps(manifest({"a.png": PNG})))
        f.writestr("a.png", PNG)
        f.writestr("../escape.png", PNG)
    with pytest.raises(PackError):
        shop.import_pack(bad)


def test_oversize_rejected():
    m = manifest({"a.png": PNG})
    m["files"][0]["size"] = vs.MAX_FILE + 1
    assert any("size" in e for e in vs.validate(m))


def test_search_filter_favourites_updates(shop, tmp_path):
    assert {m["category"] for m in shop.search(category="palette")} == {"palette"}
    assert [m["id"] for m in shop.search("ocean")] == ["accent-ocean"]
    assert shop.search("no such thing at all") == []
    shop.set_favourite("accent-teal")
    assert [m["id"] for m in shop.search(view="favourites")] == ["accent-teal"]
    shop.set_favourite("accent-teal", False)
    assert shop.search(view="favourites") == []
    old = manifest({"a.png": PNG}, id="accent-teal", category="palette", version="0.9")
    shop.import_pack(write_pack(tmp_path / "old", {"a.png": PNG}, old))
    assert [m["id"] for m in shop.search(view="updates")] == ["accent-teal"]


def test_apply_palette_and_disabled_reason(shop, monkeypatch):
    m = next(m for m in shop.catalog() if m["id"] == "accent-violet")
    assert shop.can_apply(m) == (False, "Install it first.")
    shop.install(m)
    from core.config import config
    monkeypatch.setattr(config, "set", lambda k, v, persist=True: setattr(test_apply_palette_and_disabled_reason, "got", (k, v)))
    assert "#7c3aed" in shop.apply(m)
    assert test_apply_palette_and_disabled_reason.got == ("appearance.accent", "#7c3aed")
    icons = next(m for m in shop.catalog() if m["id"] == "halos-icons")
    shop.install(icons)
    ok, why = shop.can_apply(icons)
    assert not ok and why
