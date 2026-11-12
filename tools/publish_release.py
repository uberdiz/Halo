"""Publish a HalOS pre-release on GitHub from a build folder (run it yourself; it uses YOUR GitHub login).

    python tools/publish_release.py v2.1.0-beta.1 dist/halo/build22 [--notes docs/RELEASE_NOTES_2.1.md] [--draft]

Uploads, in this order, exactly the layout HalOS-Setup.exe expects: SHA256SUMS, BUILD_INFO.json, VALIDATION.txt,
Halo-x86_64.packages, HalOS-Setup.exe, Halo-x86_64.iso.part1..N (GitHub's 2 GiB asset limit; split here if absent).
Before uploading it checks that the parts join back to the hash in SHA256SUMS. Publishing a release also triggers
the iOS workflow, which attaches SaintMobile-unsigned.ipa by itself.

Token: $GITHUB_TOKEN if set, otherwise your git credential helper for github.com (the same login git push uses).
Standard library only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = "uberdiz/Halo"
PART = 1600 * 2 ** 20                     # same part size as earlier releases
FIRST = ["SHA256SUMS", "BUILD_INFO.json", "VALIDATION.txt", "Halo-x86_64.packages", "HalOS-Setup.exe"]


def token() -> str:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True).stdout
    tok = next((l.split("=", 1)[1] for l in out.splitlines() if l.startswith("password=")), "")
    if not tok:
        sys.exit("No GitHub token: set GITHUB_TOKEN or sign in to github.com with git first.")
    return tok


def api(method: str, url: str, tok: str, body=None, data=None, ctype="application/json", length=None):
    req = urllib.request.Request(url, method=method, data=data if data is not None else
                                 (json.dumps(body).encode() if body is not None else None))
    req.add_header("Authorization", f"Bearer {tok}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Content-Type", ctype)
    if length is not None:
        req.add_header("Content-Length", str(length))
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        sys.exit(f"GitHub said {e.code} for {method} {url}: {e.read()[:400]!r}")


def sha256(paths) -> str:
    h = hashlib.sha256()
    for p in paths:
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8 * 2 ** 20), b""):
                h.update(chunk)
    return h.hexdigest()


def ensure_parts(folder: Path) -> list:
    parts = sorted(folder.glob("Halo-x86_64.iso.part*"), key=lambda p: int(p.suffix[5:]))
    if parts:
        return parts
    iso = folder / "Halo-x86_64.iso"
    with open(iso, "rb") as f:
        i = 1
        while chunk := f.read(PART):
            (folder / f"Halo-x86_64.iso.part{i}").write_bytes(chunk)
            i += 1
    return ensure_parts(folder)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tag")
    ap.add_argument("folder", type=Path)
    ap.add_argument("--notes", type=Path, default=Path("docs/RELEASE_NOTES_2.1.md"))
    ap.add_argument("--target", default="halo/roadmap-2026-11")
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()

    missing = [n for n in FIRST if not (a.folder / n).is_file()]
    if missing:
        sys.exit(f"Missing in {a.folder}: {missing}")
    parts = ensure_parts(a.folder)
    want = (a.folder / "SHA256SUMS").read_text().split()[0]
    print(f"checking {len(parts)} parts against SHA256SUMS …")
    if sha256(parts) != want:
        sys.exit("The parts don't join to the hash in SHA256SUMS — not uploading.")

    tok = token()
    notes = a.notes.read_text(encoding="utf-8") if a.notes.is_file() else ""
    notes += ("\n\n## Download\nEasiest: run **HalOS-Setup.exe** on Windows. For a USB stick join the parts "
              "(`copy /b Halo-x86_64.iso.part1+Halo-x86_64.iso.part2+Halo-x86_64.iso.part3 Halo-x86_64.iso`, or "
              "`cat Halo-x86_64.iso.part* > Halo-x86_64.iso`) and check it with `SHA256SUMS`. The iPhone app "
              "(SaintMobile-unsigned.ipa) is attached by CI a few minutes after publishing; sign it with "
              "Sideloadly or AltStore (mobile/docs/IPHONE_SETUP.md).")
    rel = api("POST", f"https://api.github.com/repos/{REPO}/releases", tok,
              {"tag_name": a.tag, "target_commitish": a.target, "name": f"HalOS {a.tag.lstrip('v')}",
               "body": notes, "prerelease": True, "draft": a.draft})
    upload = rel["upload_url"].split("{")[0]
    for f in [a.folder / n for n in FIRST] + parts:
        size = f.stat().st_size
        print(f"uploading {f.name} ({size / 2 ** 20:.0f} MiB) …", flush=True)
        with open(f, "rb") as fh:
            api("POST", f"{upload}?name={f.name}", tok, data=fh, ctype="application/octet-stream", length=size)
    print("published:", rel["html_url"])


if __name__ == "__main__":
    main()
