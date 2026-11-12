"""iPhone photos: imported over USB (new ones only, nothing on the phone changes), and the PC's Pictures browsable
from a paired phone over SAINT Link, without leaving the Pictures folder."""
import base64
import os
import time

import pytest

from core import iphone_photos as ip
from modules.link import photos
from modules.link.wire import LinkError


def runner(outputs):
    calls = []

    def run(argv, **kw):
        calls.append(list(argv))
        code, out = outputs.get(argv[0], (0, ""))
        if argv[0] == "idevicepair" and argv[-1] == "validate":
            code, out = outputs.get("validate", (0, ""))
        return type("R", (), {"returncode": code, "stdout": out, "stderr": ""})()
    run.calls = calls
    return run


def test_status_in_plain_words():
    assert "isn't installed" in ip.status(runner({"idevice_id": (127, "")}))["message"]
    assert "No iPhone is plugged in" in ip.status(runner({"idevice_id": (0, "")}))["message"]
    untrusted = runner({"idevice_id": (0, "abc123\n"), "ideviceinfo": (0, "Seb's iPhone\n"), "validate": (1, "")})
    st = ip.status(untrusted)
    assert not st["paired"] and "tap Trust" in st["message"] and ["idevicepair", "-u", "abc123", "pair"] in untrusted.calls
    ok = ip.status(runner({"idevice_id": (0, "abc123\n"), "ideviceinfo": (0, "Seb's iPhone\n")}))
    assert ok["paired"] and ok["name"] == "Seb's iPhone"


def test_only_new_photos_are_copied_by_month(tmp_path):
    dcim = tmp_path / "phone/DCIM/100APPLE"
    dcim.mkdir(parents=True)
    for name in ("IMG_0001.HEIC", "IMG_0002.MOV", "notes.txt"):
        (dcim / name).write_bytes(b"x" * 10)
    month = time.strftime("%Y-%m")
    dest = tmp_path / "Pictures/iPhone"
    first = ip.copy_new(tmp_path / "phone/DCIM", dest)
    assert first == {"copied": 2, "skipped": 0} and (dest / month / "IMG_0001.HEIC").exists()
    (dcim / "IMG_0003.JPG").write_bytes(b"y" * 5)
    again = ip.copy_new(tmp_path / "phone/DCIM", dest)
    assert again == {"copied": 1, "skipped": 2}


def test_import_mounts_read_only_and_always_unmounts(tmp_path, monkeypatch):
    run = runner({"idevice_id": (0, "abc\n"), "ideviceinfo": (0, "iPhone\n"), "ifuse": (0, "")})
    out = ip.import_photos(tmp_path / "dest", run=run)
    ifuse = next(c for c in run.calls if c[0] == "ifuse")
    assert ifuse[3:5] == ["-o", "ro"]
    assert any(c[:2] == ["fusermount", "-u"] for c in run.calls)
    assert "No photos found" in out["message"]                     # the fake mount is empty


@pytest.fixture
def pictures(tmp_path, monkeypatch):
    root = tmp_path / "Pictures"
    (root / "Trips").mkdir(parents=True)
    from PIL import Image
    Image.new("RGB", (800, 600), (200, 100, 50)).save(root / "Trips/beach.jpg")
    (root / "older.png").write_bytes(b"not really a png")
    os.utime(root / "older.png", (time.time() - 3600, time.time() - 3600))
    (root / "secret.txt").write_text("no")
    (tmp_path / "outside.jpg").write_bytes(b"x")
    monkeypatch.setattr(photos, "pictures_dir", lambda: root)
    return root


def test_phone_lists_photos_newest_first_and_only_photos(pictures):
    listed = photos.list_photos()
    assert [p["path"] for p in listed["photos"]] == ["Trips/beach.jpg", "older.png"] and listed["total"] == 2


def test_thumbnails_are_small_jpegs(pictures):
    t = photos.thumbnail("Trips/beach.jpg")
    assert t["w"] == 256 and t["h"] == 192 and base64.b64decode(t["jpeg"])[:2] == b"\xff\xd8"
    assert photos.thumbnail("older.png")["jpeg"] == ""               # unreadable: the phone shows an icon


@pytest.mark.parametrize("bad", ["../outside.jpg", "/etc/passwd", "secret.txt", "Trips/../../outside.jpg", ""])
def test_nothing_outside_pictures_can_be_reached(pictures, bad):
    with pytest.raises(LinkError):
        photos._inside(pictures, bad)


def test_photos_is_for_your_own_devices_only_by_default():
    from modules.link import identity
    assert identity.ROLE_DEFAULTS[identity.OWN]["photos"] == identity.ALLOW
    assert identity.ROLE_DEFAULTS[identity.COLLABORATOR]["photos"] == identity.DENY


def test_handlers_check_permission_and_send_the_file(pictures):
    sent, asked = [], []

    class Node:
        handlers = {}

        def register(self, name, fn):
            self.handlers[name] = fn

        def send_file(self, peer_id, path):
            sent.append((peer_id, path))

    service = type("S", (), {"node": Node()})()
    photos.register(service)
    ctx = type("C", (), {"peer": type("P", (), {"id": "phone1"})(), "require": lambda self, p, d="": asked.append(p)})()
    assert service.node.handlers["photos.list"](ctx, {})["total"] == 2
    assert service.node.handlers["photos.get"](ctx, {"path": "Trips/beach.jpg"}) == {"sent": True}
    assert sent == [("phone1", str(pictures / "Trips/beach.jpg"))] and asked == ["photos", "photos"]
