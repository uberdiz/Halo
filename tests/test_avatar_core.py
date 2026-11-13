import json
import struct

import pytest

from core.avatar import SIZE_MAX, AvatarState, AvatarStateMachine, from_assistant, settings
from core.avatar import library as lib
from core.events import EventType


def glb(doc, bin_data=b"\0" * 8, magic=b"glTF", version=2, pad_len=0):
    j = json.dumps(doc).encode()
    j += b" " * (-len(j) % 4)
    body = struct.pack("<II", len(j), 0x4E4F534A) + j
    if bin_data is not None:
        body += struct.pack("<II", len(bin_data), 0x004E4942) + bin_data
    return magic + struct.pack("<II", version, 12 + len(body) + pad_len) + body


VRM1 = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 8}], "bufferViews": [{"buffer": 0, "byteLength": 8}],
        "extensions": {"VRMC_vrm": {"meta": {"name": "Saint", "authors": ["Seb"], "licenseUrl": "https://x/l"}}}}


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("SAINT_DATA_DIR", str(tmp_path / "data"))
    return tmp_path


def test_good_vrm1_meta_and_import(data):
    f = data / "Saint.vrm"
    f.write_bytes(glb(VRM1))
    info = lib.inspect(f)
    assert info["kind"] == "3d" and info["meta"] == {"version": "1.0", "title": "Saint", "author": "Seb",
                                                      "license": "https://x/l"}
    rec = lib.import_file(f)
    assert rec["name"] == "Saint" and lib.get(rec["id"])["file"].endswith("model.vrm")
    assert [a["id"] for a in lib.list_avatars()] == ["default", rec["id"]]
    assert lib.remove(rec["id"]) and len(lib.list_avatars()) == 1
    assert not lib.remove("default") and not lib.remove("../x")


def test_vrm0_meta():
    doc = {"asset": {"version": "2.0"}, "extensions": {"VRM": {"meta": {"title": "T", "author": "A",
                                                                         "licenseName": "CC0"}}}}
    assert lib.vrm_meta(doc) == {"version": "0.x", "title": "T", "author": "A", "license": "CC0"}


@pytest.mark.parametrize("raw,msg", [
    (glb(VRM1, magic=b"gLTF"), "bad magic"),
    (glb(VRM1, version=1), "version"),
    (glb(VRM1, pad_len=4), "truncated"),
    (glb(VRM1, bin_data=None), "missing its data"),
    (glb(dict(VRM1, buffers=[{"byteLength": 8, "uri": "x.bin"}])), "outside file"),
    (glb(dict(VRM1, bufferViews=[{"buffer": 3}])), "isn't there"),
    (glb(dict(VRM1, extensions={})), "no VRM data"),
])
def test_bad_models(data, raw, msg):
    f = data / "bad.vrm"
    f.write_bytes(raw)
    with pytest.raises(lib.AvatarError, match=msg):
        lib.inspect(f)


def test_oversize_and_unsupported(data, monkeypatch):
    f = data / "big.glb"
    f.write_bytes(glb(VRM1))
    monkeypatch.setattr(lib, "MAX_MODEL_BYTES", 10)
    with pytest.raises(lib.AvatarError, match="200 MB"):
        lib.inspect(f)
    (data / "a.fbx").write_bytes(b"x")
    with pytest.raises(lib.AvatarError, match="isn't supported"):
        lib.inspect(data / "a.fbx")
    (data / "fake.png").write_bytes(b"GIF89a....")
    with pytest.raises(lib.AvatarError, match="real PNG"):
        lib.inspect(data / "fake.png")


def test_gltf_with_files(data):
    d = data / "m"
    d.mkdir()
    (d / "buf.bin").write_bytes(b"\0" * 8)
    doc = {"asset": {"version": "2.0"}, "buffers": [{"byteLength": 8, "uri": "buf.bin"}]}
    (d / "m.gltf").write_text(json.dumps(doc))
    rec = lib.import_file(d / "m.gltf")
    assert (data / "data" / "avatars" / rec["id"] / "buf.bin").is_file()
    doc["buffers"][0]["uri"] = "../secret.bin"
    (d / "m.gltf").write_text(json.dumps(doc))
    with pytest.raises(lib.AvatarError, match="outside"):
        lib.inspect(d / "m.gltf")


def test_png_import(data):
    f = data / "me.png"
    f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 20)
    assert lib.import_file(f)["kind"] == "2d"


def test_default_is_the_shipped_3d_saint():
    a = lib.default_avatar()                             # data/avatars/saint: the VRoid SAINT + balsam QML scene
    assert a["kind"] == "3d" and a["file"].endswith("saint.vrm") and a["qml"].endswith("Saint.qml")
    assert a["meta"]["title"] == "SAINT" and a["meta"]["version"] == "1.0"


def test_state_mapping():
    assert from_assistant("wake_listening") == AvatarState.IDLE
    assert from_assistant("command_listening") == AvatarState.LISTENING
    assert from_assistant("processing") == AvatarState.THINKING
    assert from_assistant("observing") == AvatarState.WORKING
    assert from_assistant("nonsense") == AvatarState.IDLE
    m = AvatarStateMachine("idle")
    assert m.feed(EventType.ASSISTANT_STATE, {"state": "processing"}, now=0) == AvatarState.THINKING
    assert m.feed(EventType.PLAN_STARTED, {}, now=0) == AvatarState.PLANNING
    assert m.feed(EventType.PLAN_DONE, {"ok": True}, now=1) == AvatarState.SUCCESS
    assert m.current(now=4) == AvatarState.THINKING
    assert m.feed(EventType.ERROR, {}, now=5) == AvatarState.ERROR
    assert m.feed(EventType.ASSISTANT_STATE, {"state": "speaking"}, now=5) == AvatarState.SPEAKING


def test_settings_persist(tmp_path):
    from core.config import Config
    cfg = Config(path=str(tmp_path / "c.json"))
    assert settings(cfg)["placement"] == "floating" and settings(cfg)["pos"] is None
    cfg.set("avatar.placement", "widget")
    cfg.set("avatar.size", 9999)
    cfg.set("avatar.pos", [10, 20])
    cfg.set("avatar.name", "Halo")
    s = settings(Config(path=str(tmp_path / "c.json")))
    assert (s["placement"], s["size"], s["pos"], s["name"]) == ("widget", SIZE_MAX, [10, 20], "Halo")
    cfg.set("avatar.placement", "sideways")
    assert settings(cfg)["placement"] == "floating"
