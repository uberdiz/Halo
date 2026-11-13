"""HalOS Passwords: CSV exports (Apple / Chrome / Firefox / Bitwarden quirks), merge rules, the keyring vault with a
fake keyring, TOTP against the RFC 6238 vectors, strength / reuse / generator, Downloads export detection, and the
SAINT actions (passwords.find never carries a password)."""
import json
import os
import sys
import time

import pytest

from core import passwords as pw

APPLE = ("﻿Title,URL,Username,Password,Notes,OTPAuth\r\n"
         'example.com (me@x.com),https://www.example.com/login,me@x.com,"pa,ss""word",'
         '"line one\nline, two",otpauth://totp/Example:me?secret=GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ&issuer=Example\r\n'
         "github.com,https://github.com,octo,hunter2-Strong!,,\r\n"
         "nopass,https://nopass.example,ghost,,,\r\n")
CHROME = "name,url,username,password,note\ngithub.com,https://github.com/session,octo,NEW-pass-123!,\n"
FIREFOX = ('"url","username","password","httpRealm","formActionOrigin","guid","timeCreated"\n'
           '"https://accounts.example.org","fox","f1r3f0x!",,"https://accounts.example.org","{abc}","1"\n')
BITWARDEN = ("folder,favorite,type,name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp\n"
             ",,login,Bank,,,0,https://bank.example,alice,B4nk!pass,JBSWY3DPEHPK3PXP\n"
             ",,note,Secret note,just a note,,0,,,,\n")


class FakeKeyring:
    def __init__(self, limit=None):
        self.store, self.limit = {}, limit

    def get_password(self, service, key):
        return self.store.get((service, key))

    def set_password(self, service, key, value):
        if self.limit and len(value) > self.limit:
            raise RuntimeError("too big")
        self.store[(service, key)] = value

    def delete_password(self, service, key):
        self.store.pop((service, key))


def test_apple_csv_bom_quotes_commas_newlines_and_skips_empty_password():
    rows = pw.parse_csv(APPLE)
    assert len(rows) == 2
    a = rows[0]
    assert (a.site, a.username, a.password) == ("example.com", "me@x.com", 'pa,ss"word')
    assert a.notes == "line one\nline, two" and a.otpauth.startswith("otpauth://totp/")
    assert rows[1].site == "github.com" and rows[1].notes == ""


def test_chrome_firefox_bitwarden_columns(tmp_path):
    assert [(e.site, e.username) for e in pw.parse_csv(CHROME)] == [("github.com", "octo")]
    assert [(e.site, e.password) for e in pw.parse_csv(FIREFOX)] == [("accounts.example.org", "f1r3f0x!")]
    bw = pw.parse_csv(BITWARDEN)
    assert len(bw) == 1 and bw[0].title == "Bank" and bw[0].otpauth.startswith("otpauth://totp/bank.example?secret=")
    f = tmp_path / "Passwords.csv"
    f.write_text(APPLE, encoding="utf-8")
    assert len(pw.parse_csv(f)) == 2
    with pytest.raises(ValueError):
        pw.parse_csv("a,b\n1,2\n")


def test_merge_adds_updates_keeps_and_counts():
    local_only = pw.Entry(url="https://local.example", username="me", password="x")
    existing, counts = pw.merge([local_only], pw.parse_csv(APPLE))
    assert counts == {"added": 2, "updated": 0, "unchanged": 0, "kept": 1}
    gh_id = next(e.id for e in existing if e.site == "github.com")
    merged, counts = pw.merge(existing, pw.parse_csv(CHROME) + [pw.parse_csv(APPLE)[0]])
    assert counts == {"added": 0, "updated": 1, "unchanged": 1, "kept": 1}
    gh = next(e for e in merged if e.site == "github.com")
    assert gh.id == gh_id and gh.password == "NEW-pass-123!" and len(merged) == 3
    # same site, username differs only in case: the same login
    _, counts = pw.merge(merged, [pw.Entry(url="https://github.com/session", username="OCTO", password="NEW-pass-123!")])
    assert counts["unchanged"] == 1


def test_vault_lives_only_in_the_keyring_chunked_and_round_trips(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kr = FakeKeyring(limit=pw.CHUNK)
    v = pw.Vault(kr=kr, service="test-pw")
    v.unlock()
    assert v.entries == []
    for i in range(40):
        v.entries.append(pw.Entry(url=f"https://site{i}.example", username=f"u{i}", password=f"secret-{i}-xyz"))
    v.save()
    assert kr.store[("test-pw", "vault")].startswith("parts:") and int(kr.store[("test-pw", "vault")][6:]) > 1
    assert list(tmp_path.iterdir()) == []                         # nothing on disk
    w = pw.Vault(kr=kr, service="test-pw")
    assert w.locked and len(w.unlock()) == 40 and w.find("site7")[0].password == "secret-7-xyz"
    w.entries = w.entries[:1]
    w.save()                                                      # shrinking drops the stale parts
    assert sum(1 for s, k in kr.store if k.startswith("vault.")) == int(kr.store[("test-pw", "vault")][6:])
    w.lock()
    assert w.locked and w.entries is None


def test_vault_import_csv_and_repr_hides_the_password(tmp_path):
    v = pw.Vault(kr=FakeKeyring(), service="t")
    f = tmp_path / "Passwords.csv"
    f.write_text(APPLE, encoding="utf-8")
    assert v.import_csv(f)["added"] == 2
    assert v.import_csv(f) == {"added": 0, "updated": 0, "unchanged": 2, "kept": 0}
    assert "hunter2" not in repr(v.entries) and "hunter2" not in json.dumps([e.public() for e in v.entries])


@pytest.mark.parametrize("t,algo,code", [
    (59, "SHA1", "94287082"), (1111111109, "SHA1", "07081804"), (1111111111, "SHA1", "14050471"),
    (1234567890, "SHA1", "89005924"), (2000000000, "SHA1", "69279037"), (20000000000, "SHA1", "65353130"),
    (59, "SHA256", "46119246"), (1111111109, "SHA256", "68084774"), (59, "SHA512", "90693936"),
    (1111111109, "SHA512", "25091201")])
def test_totp_rfc6238_vectors(t, algo, code):
    key = {"SHA1": b"12345678901234567890", "SHA256": b"12345678901234567890123456789012",
           "SHA512": b"1234567890123456789012345678901234567890123456789012345678901234"}[algo]
    assert pw.totp(key, t, 8, 30, algo) == code


def test_totp_from_otpauth_uri():
    import base64
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=").lower()
    code, left = pw.totp_from_uri(f"otpauth://totp/X:me?secret={secret}&digits=8&issuer=X", at=59)
    assert code == "94287082" and left == 1
    with pytest.raises(ValueError):
        pw.parse_otpauth("https://example.com")


def test_strength_reuse_and_generator():
    assert pw.strength("password")[0] == 0 and pw.strength("12345678")[0] == 0 and pw.strength("aaaaaaaa")[0] == 0
    assert pw.strength("short1!")[0] == 0
    assert pw.strength("correct-Horse-battery-9")[0] >= 3
    a, b, c = (pw.Entry(password="same"), pw.Entry(password="same"), pw.Entry(password="other"))
    assert pw.reused([a, b, c]) == {a.id, b.id}
    g = pw.generate(24)
    assert len(g) == 24 and any(ch.isupper() for ch in g) and any(ch.isdigit() for ch in g)
    assert pw.strength(g)[0] == 4 and g != pw.generate(24)
    assert all(ch.isalnum() for ch in pw.generate(16, symbols=False))


def test_pending_exports_in_downloads(tmp_path):
    for name in ("Passwords.csv", "Chrome Passwords.csv", "logins.csv", "bitwarden_export_2026.csv", "budget.csv",
                 "Passwords.txt"):
        (tmp_path / name).write_text("x")
    found = {p.name for p in pw.pending_exports(tmp_path)}
    assert found == {"Passwords.csv", "Chrome Passwords.csv", "logins.csv", "bitwarden_export_2026.csv"}
    seen = [pw.export_id(tmp_path / "Passwords.csv")]
    assert "Passwords.csv" not in {p.name for p in pw.pending_exports(tmp_path, seen)}
    assert pw.pending_exports(tmp_path / "missing") == []


# --------------------------------------------------------------------------- SAINT actions
@pytest.fixture
def saint(tmp_path, monkeypatch):
    from core import actions
    from core.actions import ActionLog, executor, log as log_mod
    from core.actions.sets import halos_apps
    fresh = ActionLog(tmp_path / "log.jsonl")
    for mod in (log_mod, executor, actions):
        monkeypatch.setattr(mod, "action_log", fresh)
    actions.load_builtin()
    for name, mod in list(sys.modules.items()):
        if name.startswith("core.actions") and hasattr(mod, "platform_name"):
            monkeypatch.setattr(mod, "platform_name", lambda: "linux")
    v = pw.Vault(kr=FakeKeyring(), service="t")
    v.unlock()
    v.entries += [pw.Entry(url="https://github.com", username="octo", password="hunter2-Strong!"),
                  pw.Entry(url="https://mail.example.com", username="a", password="pw-a-123456"),
                  pw.Entry(url="https://mail.example.com", username="b", password="pw-b-123456")]
    v.save()
    monkeypatch.setattr(pw, "_vault", v)
    spawned = []
    monkeypatch.setattr(halos_apps, "_spawn", spawned.append)
    return v, tmp_path / "log.jsonl", spawned


def test_find_never_returns_or_logs_a_password(saint):
    from core.actions import SAFE, execute, registry
    v, log_file, _ = saint
    assert registry.get("passwords.find").risk == SAFE
    r = execute("passwords.find", {"query": "github"}, source="saint")
    assert r.ok and r.data["items"][0]["username"] == "octo"
    blob = json.dumps(r.to_dict() if hasattr(r, "to_dict") else r.__dict__, default=str)
    assert "hunter2" not in blob and "hunter2" not in r.text
    assert not log_file.exists() or "hunter2" not in log_file.read_text()


def test_fill_is_risky_and_types_username_tab_password(saint, monkeypatch):
    from core.actions import RISKY, execute, registry
    from modules.desktop import controller
    v, log_file, _ = saint
    assert registry.get("passwords.fill").risk == RISKY
    typed = []
    monkeypatch.setattr(controller.desktop, "type_text", lambda text, **kw: typed.append(text))
    asked = []
    r = execute("passwords.fill", {"query": "github"}, source="saint", confirm=lambda req: asked.append(req) or False)
    assert asked and not r.ok and typed == []                      # asked first; declined: nothing typed
    r = execute("passwords.fill", {"query": "github"}, source="saint", confirmed=True)
    assert r.ok and typed == ["octo\thunter2-Strong!"] and "hunter2" not in r.text
    assert execute("passwords.fill", {"query": "mail"}, source="saint", confirmed=True).code == "AMBIGUOUS"
    r = execute("passwords.fill", {"query": "mail", "username": "b"}, source="saint", confirmed=True)
    assert r.ok and typed[-1] == "b\tpw-b-123456"
    assert not log_file.exists() or "pw-b-123456" not in log_file.read_text()


def test_import_action_and_open(saint, tmp_path):
    from core.actions import execute
    v, _, spawned = saint
    f = tmp_path / "Passwords.csv"
    f.write_text(APPLE, encoding="utf-8")
    r = execute("passwords.import", {"path": str(f)}, source="saint")
    assert r.ok and (r.data["added"], r.data["updated"], r.data["kept"]) == (1, 1, 2)   # github.com: new password
    assert execute("passwords.import", {"path": str(tmp_path / "no.csv")}, source="saint").code == "NOT_FOUND"
    assert execute("passwords.open", {"query": "github"}, source="saint").ok
    assert spawned[-1][-1] == "github"


def test_app_builds_offscreen_and_offers_a_downloads_export(saint, tmp_path, monkeypatch):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from core.config import config
    store = {}
    monkeypatch.setattr(config, "get", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(config, "set", lambda k, val, persist=True: store.__setitem__(k, val))
    from ui import passwords_app
    v, _, _ = saint
    (tmp_path / "Passwords.csv").write_text(APPLE, encoding="utf-8")
    w = passwords_app.PasswordsWindow(vault=v, downloads=tmp_path)
    app.processEvents()
    assert w.list.count() == 3 and w._offer and w._offer.name == "Passwords.csv"
    assert "hunter2" not in w.d_pass.text()                        # hidden until revealed
    w.list.setCurrentRow(0)
    w.toggle_reveal()
    assert w.d_pass.text() == w.current().password
    w._dismiss_offer()
    assert w._offer is None and store["passwords.seen_exports"]
    w.lock()
    assert v.locked and w.list.count() == 0
    w.close()
