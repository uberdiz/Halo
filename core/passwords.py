"""
core/passwords.py

HalOS Passwords: the vault behind ui/passwords_app.py and SAINT's passwords.* actions.

The whole vault is one JSON blob in the system keyring (KWallet / Secret Service on HalOS, Credential Manager on
Windows; chunked there because one credential holds ~1.2k characters). It is never written to disk in plain text and
never logged: log lines carry counts and exception types only.

Import is a repeatable merge of a CSV export (Apple Passwords, Chrome, Firefox, Bitwarden) keyed by (site,
username): new logins are added, changed ones updated, logins only kept here are left alone. Apple has no sync API
outside its own platforms, so re-importing a fresh export is how "sync from Apple" works.

Plain helpers (tested): parse_csv, merge, totp / totp_from_uri, strength, reused, generate, pending_exports.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import math
import re
import secrets
import string
import struct
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

log = logging.getLogger("saint.passwords")

VAULT_KEY = "vault"
CHUNK = 1000                     # characters per keyring item (Windows Credential Manager caps a blob at 2560 bytes)
EXPORT_RE = re.compile(r"^(.*passwords?.*|logins.*|bitwarden_export.*)\.csv$", re.I)


# --------------------------------------------------------------------------- entries
@dataclass
class Entry:
    title: str = ""
    url: str = ""
    username: str = ""
    password: str = ""
    notes: str = ""
    otpauth: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    updated: float = field(default_factory=time.time)

    @property
    def site(self) -> str:
        return site_of(self.url) or self.title.strip().lower()

    @property
    def key(self) -> Tuple[str, str]:
        return self.site, self.username.strip().casefold()

    def public(self) -> dict:
        """What SAINT (and so a model) may see: never the password, notes or the TOTP secret."""
        return {"id": self.id, "title": self.title or self.site, "site": self.site, "username": self.username,
                "has_totp": bool(self.otpauth)}

    def __repr__(self):                                   # a stray print or log never shows the secret
        return f"Entry({self.site!r}, {self.username!r})"


def site_of(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if "://" not in u:
        u = "https://" + u
    try:
        host = (urlparse(u).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# --------------------------------------------------------------------------- CSV import
# Column names per exporter, lower-cased. Apple: Title,URL,Username,Password,Notes,OTPAuth. Chrome:
# name,url,username,password,note. Firefox: url,username,password,httpRealm,... Bitwarden: folder,favorite,type,
# name,notes,fields,reprompt,login_uri,login_username,login_password,login_totp.
_COLS = {
    "title": ("title", "name"),
    "url": ("url", "login_uri", "website", "web site"),
    "username": ("username", "login_username", "user name", "login", "email"),
    "password": ("password", "login_password"),
    "notes": ("notes", "note", "comments"),
    "otpauth": ("otpauth", "login_totp", "totp"),
}


def parse_csv(src) -> List[Entry]:
    """Entries from an export (a path, or the CSV text). Handles a BOM, quoted commas/newlines and any column order;
    rows without a password (Bitwarden notes, cards) are skipped."""
    if isinstance(src, Path) or (isinstance(src, str) and "\n" not in src and src.lower().endswith(".csv")):
        text = Path(src).read_text(encoding="utf-8-sig", errors="replace")
    else:
        text = str(src).lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if not reader.fieldnames:
        return []
    names = {(h or "").strip().lstrip("﻿").lower(): h for h in reader.fieldnames}
    cols = {k: next((names[a] for a in aliases if a in names), None) for k, aliases in _COLS.items()}
    if not cols["password"]:
        raise ValueError("This CSV has no password column: is it a password export?")
    out = []
    for row in reader:
        get = lambda k: (row.get(cols[k]) or "").strip() if cols[k] else ""     # noqa: E731
        if row.get("type") not in (None, "", "login"):                         # Bitwarden: cards, notes...
            continue
        pw = row.get(cols["password"]) or ""
        if not pw:
            continue
        url = get("url").splitlines()[0].split(",")[0].strip() if get("url") else ""
        otp = get("otpauth")
        if otp and not otp.lower().startswith("otpauth://"):                    # Bitwarden may give a bare secret
            otp = f"otpauth://totp/{site_of(url) or 'login'}?secret={otp.replace(' ', '')}"
        out.append(Entry(title=get("title"), url=url, username=get("username"), password=pw,
                         notes=get("notes"), otpauth=otp))
    return out


def merge(existing: List[Entry], incoming: Iterable[Entry]) -> Tuple[List[Entry], Dict[str, int]]:
    """Merge an import into the vault by (site, username). New -> added; same key with a different password, notes,
    OTP or title -> updated in place (id kept); identical -> unchanged; logins only in the vault -> kept."""
    merged = list(existing)
    by_key = {e.key: e for e in merged}
    counts = {"added": 0, "updated": 0, "unchanged": 0, "kept": 0}
    seen = set()
    for new in incoming:
        old = by_key.get(new.key)
        seen.add(new.key)
        if old is None:
            merged.append(new)
            by_key[new.key] = new
            counts["added"] += 1
            continue
        changed = False
        for f in ("password", "notes", "otpauth", "title", "url"):
            v = getattr(new, f)
            if v and v != getattr(old, f):
                setattr(old, f, v)
                changed = True
        if changed:
            old.updated = time.time()
            counts["updated"] += 1
        else:
            counts["unchanged"] += 1
    counts["kept"] = sum(1 for e in merged if e.key not in seen)
    return merged, counts


# --------------------------------------------------------------------------- TOTP (RFC 6238)
def totp(key: bytes, at: Optional[float] = None, digits: int = 6, period: int = 30, algo: str = "SHA1") -> str:
    counter = int((time.time() if at is None else at) // period)
    mac = hmac.new(key, struct.pack(">Q", counter), getattr(hashlib, algo.lower())).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def parse_otpauth(uri: str) -> dict:
    """{"key": bytes, "digits", "period", "algo"} from an otpauth://totp/... URI. Raises ValueError."""
    u = urlparse((uri or "").strip())
    if u.scheme != "otpauth" or u.netloc.lower() != "totp":
        raise ValueError("not an otpauth://totp URI")
    q = {k.lower(): v[0] for k, v in parse_qs(u.query).items()}
    secret = unquote(q.get("secret", "")).replace(" ", "").upper()
    if not secret:
        raise ValueError("no secret")
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    algo = q.get("algorithm", "SHA1").upper()
    if algo not in ("SHA1", "SHA256", "SHA512"):
        raise ValueError(f"unsupported algorithm {algo}")
    return {"key": key, "digits": int(q.get("digits", 6)), "period": int(q.get("period", 30)), "algo": algo}


def totp_from_uri(uri: str, at: Optional[float] = None) -> Tuple[str, int]:
    """(code, seconds left) for an otpauth URI."""
    p = parse_otpauth(uri)
    now = time.time() if at is None else at
    return totp(p["key"], now, p["digits"], p["period"], p["algo"]), int(p["period"] - now % p["period"])


# --------------------------------------------------------------------------- strength, reuse, generator
_COMMON = {"password", "123456", "12345678", "123456789", "qwerty", "abc123", "111111", "letmein", "iloveyou",
           "admin", "welcome", "monkey", "dragon", "football", "baseball", "sunshine", "princess", "master",
           "passw0rd", "password1", "qwerty123", "1q2w3e4r", "000000", "trustno1", "login", "starwars"}
LABELS = ("Very weak", "Weak", "Fair", "Good", "Strong")


def strength(pw: str) -> Tuple[int, str]:
    """(0..4, label) from length and character variety, with common passwords and runs knocked down. Local and
    deterministic: a quick guide, not a cracking estimate."""
    if not pw:
        return 0, LABELS[0]
    low = pw.lower()
    if low in _COMMON or len(set(pw)) <= 2 or low in string.digits * 2 or low in string.ascii_lowercase * 2:
        return 0, LABELS[0]
    pool = sum(n for ok, n in ((any(c.islower() for c in pw), 26), (any(c.isupper() for c in pw), 26),
                               (any(c.isdigit() for c in pw), 10), (any(not c.isalnum() for c in pw), 33)) if ok)
    bits = len(pw) * math.log2(max(pool, 2)) * min(1.0, len(set(pw)) / max(len(pw) * 0.6, 1))
    score = 0 if len(pw) < 8 else 1 if bits < 40 else 2 if bits < 60 else 3 if bits < 80 else 4
    return score, LABELS[score]


def reused(entries: Iterable[Entry]) -> set:
    """Ids of entries whose password is used by another entry too."""
    groups: Dict[str, List[str]] = {}
    for e in entries:
        if e.password:
            groups.setdefault(hashlib.sha256(e.password.encode()).hexdigest(), []).append(e.id)
    return {i for ids in groups.values() if len(ids) > 1 for i in ids}


def generate(length: int = 20, symbols: bool = True) -> str:
    """A random password with at least one of each character class asked for (secrets, not random)."""
    length = max(8, min(int(length), 128))
    classes = [string.ascii_lowercase, string.ascii_uppercase, string.digits] + (["!@#$%^&*-_=+?"] if symbols else [])
    pw = [secrets.choice(c) for c in classes]
    alphabet = "".join(classes)
    pw += [secrets.choice(alphabet) for _ in range(length - len(pw))]
    secrets.SystemRandom().shuffle(pw)
    return "".join(pw)


# --------------------------------------------------------------------------- exports left in Downloads
def pending_exports(folder: Optional[Path] = None, seen: Iterable[str] = ()) -> List[Path]:
    """Password CSV exports in Downloads not offered yet, newest first. ``seen`` holds export_id()s."""
    folder = Path(folder) if folder else Path.home() / "Downloads"
    seen = set(seen)
    try:
        found = [p for p in folder.iterdir() if p.is_file() and EXPORT_RE.match(p.name)]
    except OSError:
        return []
    found = [p for p in found if export_id(p) not in seen]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def export_id(p: Path) -> str:
    try:
        return f"{p}|{int(p.stat().st_mtime)}"
    except OSError:
        return str(p)


# --------------------------------------------------------------------------- the vault
class Vault:
    """The keyring-backed vault. ``kr`` is a keyring-like module (get/set/delete_password); tests pass a fake."""

    def __init__(self, kr=None, service: Optional[str] = None):
        self._kr = kr
        self._service = service
        self.entries: Optional[List[Entry]] = None       # None = locked
        self._lock = threading.Lock()

    @property
    def service(self) -> str:
        if not self._service:
            from core.paths import keyring_service
            self._service = keyring_service() + "-passwords"
        return self._service

    @property
    def kr(self):
        if self._kr is None:
            import keyring
            self._kr = keyring
        return self._kr

    @property
    def locked(self) -> bool:
        return self.entries is None

    # ---- storage
    def _read(self) -> str:
        if self._kr is None:
            from core.paths import secret_collection_missing
            if secret_collection_missing():
                return ""                      # no wallet yet: don't pop KWallet's wizard just to read nothing
        head = self.kr.get_password(self.service, VAULT_KEY) or ""
        if head.startswith("parts:"):
            n = int(head[6:])
            return "".join(self.kr.get_password(self.service, f"{VAULT_KEY}.{i}") or "" for i in range(n))
        return head

    def _write(self, blob: str):
        parts = [blob[i:i + CHUNK] for i in range(0, len(blob), CHUNK)] or [""]
        old = self.kr.get_password(self.service, VAULT_KEY) or ""
        old_n = int(old[6:]) if old.startswith("parts:") else 0
        for i, part in enumerate(parts):
            self.kr.set_password(self.service, f"{VAULT_KEY}.{i}", part)
        self.kr.set_password(self.service, VAULT_KEY, f"parts:{len(parts)}")
        for i in range(len(parts), old_n):
            try:
                self.kr.delete_password(self.service, f"{VAULT_KEY}.{i}")
            except Exception:
                pass

    def unlock(self) -> List[Entry]:
        with self._lock:
            try:
                blob = self._read()
            except Exception as e:
                log.warning("passwords.read_failed %s", type(e).__name__)
                raise RuntimeError("The keyring (KWallet) couldn't be opened.") from None
            data = json.loads(blob) if blob else {}
            fields = set(Entry.__dataclass_fields__)
            self.entries = [Entry(**{k: v for k, v in d.items() if k in fields}) for d in data.get("entries", [])]
            return self.entries

    def ensure(self) -> List[Entry]:
        return self.entries if self.entries is not None else self.unlock()

    def lock(self):
        self.entries = None

    def save(self):
        with self._lock:
            blob = json.dumps({"v": 1, "entries": [asdict(e) for e in self.ensure()]}, separators=(",", ":"))
            try:
                self._write(blob)
            except Exception as e:
                log.warning("passwords.write_failed %s", type(e).__name__)
                raise RuntimeError("The keyring (KWallet) refused to save the vault.") from None
        log.info("passwords.saved %d", len(self.entries))

    # ---- edits
    def get(self, entry_id: str) -> Optional[Entry]:
        return next((e for e in self.ensure() if e.id == entry_id), None)

    def upsert(self, entry: Entry):
        entries = self.ensure()
        i = next((n for n, e in enumerate(entries) if e.id == entry.id), None)
        entry.updated = time.time()
        if i is None:
            entries.append(entry)
        else:
            entries[i] = entry
        self.save()

    def delete(self, entry_id: str):
        self.entries = [e for e in self.ensure() if e.id != entry_id]
        self.save()

    def find(self, query: str = "") -> List[Entry]:
        """Entries matching every word of ``query`` in site, title or username, best (site match) first."""
        words = [w for w in (query or "").lower().split() if w]
        hits = []
        for e in self.ensure():
            hay = f"{e.site} {e.title} {e.username}".lower()
            if all(w in hay for w in words):
                hits.append((0 if words and any(w in e.site for w in words) else 1, e.site, e.username, e))
        return [h[-1] for h in sorted(hits, key=lambda h: h[:3])]

    def import_csv(self, path) -> Dict[str, int]:
        incoming = parse_csv(Path(path))
        self.entries, counts = merge(self.ensure(), incoming)
        self.save()
        log.info("passwords.imported %s", counts)
        return counts


_vault: Optional[Vault] = None


def vault() -> Vault:
    global _vault
    if _vault is None:
        _vault = Vault()
    return _vault
