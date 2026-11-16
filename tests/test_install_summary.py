"""The installer's last page names the target disk and the free space HalOS goes into (Calamares summaryq)."""

import os

import pytest

from core import install_target as it


@pytest.fixture
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6.QtQuick")             # loads Qt Quick's libraries for the QML imports below
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def _plan(**kw):
    gib = it.GIB
    return it.Candidate(disk="/dev/nvme1n1", model="XF-2TB", start=1702 * gib, end=1902 * gib,
                        existing=["/dev/nvme1n1p2 2nd_M.2 ntfs 1701.7 GiB"], **kw)


def test_summary_lines_name_disk_free_space_and_what_stays():
    lines = it.summary_lines(_plan())
    assert lines[0] == "Disk: /dev/nvme1n1 (XF-2TB)"
    assert "200.0 GiB" in lines[1]
    assert "512 MiB EFI" in lines[2] and "199.5 GiB HalOS partition" in lines[2]
    assert lines[3].startswith("Not touched: /dev/nvme1n1p2 2nd_M.2")


def test_summary_qml_is_written_and_loads(tmp_path, qapp):
    from PySide6.QtCore import QObject, Property, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine

    out = it.write_summary(_plan(), conf_dir=tmp_path)
    assert out == tmp_path / "branding" / "halo" / "summaryq.qml"

    class Config(QObject):
        def _model(self):
            return []
        summaryModel = Property("QVariantList", _model, constant=True)

    engine = QQmlEngine()
    cfg = Config()
    engine.rootContext().setContextProperty("config", cfg)
    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(out)))
    obj = comp.create()
    assert obj is not None, comp.errorString()
    def texts(item):
        for c in item.childItems():
            t = c.property("text")
            if isinstance(t, str):
                yield t
            yield from texts(c)
    shown = list(texts(obj))
    assert any("XF-2TB" in t for t in shown) and any("200.0 GiB" in t for t in shown)


def test_freespace_installer_uses_the_summary_with_the_disk():
    conf = (it.Path(__file__).resolve().parent.parent /
            "packaging/arch/pkgbuilds/halo-calamares-config/calamares/settings-freespace.conf").read_text()
    assert "  - summaryq" in conf
