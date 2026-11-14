"""Every literal -match / -replace / -split pattern in the Windows host scripts must be a valid regex.

prepare_disk_boot.ps1 shipped with '\\EFI\\BOOT...' written as '\EFI\BOOT...' (".NET: Unrecognized escape \\E"), which
stopped HalOS-Setup's Update after HALOLIVE was written. Python's re rejects the same unknown escapes.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "packaging" / "windows-host").rglob("*.ps1"))
PATTERN = re.compile(r"-(?:i?match|notmatch|replace|split)\s+'((?:[^']|'')*)'")


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_ps_patterns_compile(path):
    for m in PATTERN.finditer(path.read_text(encoding="utf-8-sig")):
        pat = m.group(1).replace("''", "'")
        try:
            re.compile(pat.replace("(?mi)", "(?im)"))
        except re.error as e:
            pytest.fail(f"{path.name}: bad regex {pat!r}: {e}")
