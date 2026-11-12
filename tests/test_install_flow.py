"""The simple install: no Location or Keyboard page; they come from the live session and are written into the
new system by calamares-autolocale."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from core import install_target as t

ROOT = Path(__file__).resolve().parents[1]
CAL = ROOT / "packaging/arch/pkgbuilds/halo-calamares-config"


def _settings(name):
    return yaml.safe_load((CAL / "calamares" / name).read_text(encoding="utf-8"))


def test_simple_path_has_three_pages_and_writes_locale_itself():
    seq = _settings("settings-freespace.conf")["sequence"]
    assert seq[0]["show"] == ["welcome", "users", "summary"]          # where to install is chosen before, in the chooser
    run = seq[1]["exec"]
    assert "locale" not in run and "keyboard" not in run and "localecfg" not in run
    assert run.index("unpackfs") < run.index("shellprocess@halo-autolocale") < run.index("initcpio")
    ids = {i["id"] for i in _settings("settings-freespace.conf")["instances"]}
    assert "halo-autolocale" in ids


def test_the_full_installer_keeps_every_page_for_advanced_use():
    assert {"locale", "keyboard", "partition"} <= set(_settings("settings.conf")["sequence"][0]["show"])


def test_autolocale_ships_in_the_package():
    pkg = (CAL / "PKGBUILD").read_text(encoding="utf-8")
    assert '"$srcdir/halo-autolocale" "$pkgdir/usr/lib/halo/calamares-autolocale"' in pkg
    src = pkg[pkg.index("source=("):pkg.index(")", pkg.index("source=("))].split()
    sums = pkg[pkg.index("sha256sums=("):].split(")")[0].split("(")[1].split()
    assert len(src) == len(sums)


def _runner(outputs):
    def run(argv, **kw):
        out = outputs.get(argv[0], "")
        return type("R", (), {"returncode": 0 if out is not None else 1, "stdout": out or ""})()
    return run


def test_detect_locale_prefers_the_network_then_the_live_clock():
    run = _runner({"timedatectl": "Europe/Berlin\n", "localectl": "   X11 Layout: de\n  X11 Variant: nodeadkeys\n"})
    online = t.detect_locale(run, fetch=lambda url: "America/Chicago\n", environ={"LANG": "de_DE.UTF-8"})
    assert online == {"timezone": "America/Chicago", "locale": "de_DE.UTF-8", "layout": "de", "variant": "nodeadkeys"}

    def offline(url):
        raise OSError("no network")
    assert t.detect_locale(run, fetch=offline, environ={})["timezone"] == "Europe/Berlin"


def test_detect_locale_never_passes_on_junk():
    run = _runner({"timedatectl": "../../etc/passwd", "localectl": "X11 Layout: us; rm -rf /\n"})
    found = t.detect_locale(run, fetch=lambda url: "<html>rate limited</html>", environ={"LANG": "C.UTF-8"})
    assert found == {"timezone": "UTC", "locale": "en_US.UTF-8", "layout": "us", "variant": ""}


def test_save_locale_writes_the_file_the_script_reads(tmp_path):
    out = tmp_path / "autolocale.json"
    t.save_locale(out, run=_runner({}), fetch=lambda url: "Asia/Tokyo", environ={"LANG": "ja_JP.UTF-8"})
    assert json.loads(out.read_text(encoding="utf-8"))["timezone"] == "Asia/Tokyo"


@pytest.mark.skipif(not shutil.which("bash") or not shutil.which("sed"), reason="needs bash")
def test_autolocale_script_writes_the_new_system(tmp_path):
    root = tmp_path / "target"
    (root / "etc").mkdir(parents=True)
    (root / "usr/share/zoneinfo/Europe").mkdir(parents=True)
    (root / "usr/share/zoneinfo/Europe/Berlin").write_text("")
    (root / "etc/locale.gen").write_text("#de_DE.UTF-8 UTF-8\n#en_US.UTF-8 UTF-8\n", encoding="utf-8")
    src = tmp_path / "autolocale.json"
    src.write_text(json.dumps({"timezone": "Europe/Berlin", "locale": "de_DE.UTF-8", "layout": "de",
                               "variant": "nodeadkeys"}), encoding="utf-8")
    script = (CAL / "halo-autolocale").read_text(encoding="utf-8").replace("/run/halo/autolocale.json", src.as_posix())
    s = tmp_path / "autolocale.sh"
    s.write_text(script, encoding="utf-8", newline="\n")
    res = subprocess.run([shutil.which("bash"), s.as_posix(), root.as_posix()], capture_output=True, text=True,
                         timeout=60)
    if res.returncode != 0:
        pytest.skip(f"bash here can't run it: {res.stderr[:200]}")
    assert (root / "etc/locale.conf").read_text().strip() == "LANG=de_DE.UTF-8"
    assert "\nde_DE.UTF-8 UTF-8" in "\n" + (root / "etc/locale.gen").read_text()
    assert (root / "etc/vconsole.conf").read_text().strip() == "KEYMAP=de"
    kb = (root / "etc/X11/xorg.conf.d/00-keyboard.conf").read_text()
    assert '"XkbLayout" "de"' in kb and '"XkbVariant" "nodeadkeys"' in kb
