"""The Store page's filters, details view and installation assistant panel, headless (no network, nothing run)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication
    from core.config import config
    config.set("store.artwork", False, persist=False)           # no artwork requests from tests
    return QApplication.instance() or QApplication([])


def test_store_filters_details_and_assistant(app, tmp_path):
    from core import install_assistant as ia
    from core.store import Result
    from ui.pages.store import StorePage
    page = StorePage()
    page._results = [Result("repo", "blender", "Blender", installed=True), Result("aur", "libfoo", "libfoo"),
                     Result("windows", "RiotGames.Valorant.Live", "Valorant",
                            extra={"blocked": "anti-cheat", "instead": ""})]
    page.query.blockSignals(True)
    page.query.setText("bl")
    page.query.blockSignals(False)
    page._show_results()
    assert page.status.text() == "2 result(s)"
    page.filter.set_index(5)                                    # Won't work
    page._show_results()
    assert page.status.text() == "1 result(s)"
    page.filter.set_index(0)
    page.installed_filter.set_index(1)                          # Installed
    page._show_results()
    assert page.status.text() == "1 result(s)"

    page.show_details(page._results[2])
    from ui.components.store_tiles import AppDetails
    details = page._details
    assert isinstance(details, AppDetails) and not details.action.isEnabled()

    queued = []
    page.enqueue = lambda r, steps=None, after=None: queued.append((r, steps, after))
    page.show_assistant(0)
    panel = page.assistant
    panel.history = ia.History(tmp_path / "h.json")
    plan = ia.plan_for("com.heroicgameslauncher.hgl", search=lambda q: [])
    panel.show_plan(plan)
    assert not panel.plan_card.isHidden()
    panel.queue = page.enqueue
    panel.approve()
    (r, steps, after), = queued
    assert r.id == "flatpak:com.heroicgameslauncher.hgl" and steps == plan.steps
    after({r.id: False}, {r.id: "Not enough disk space."})     # a failed install is recorded with why
    (e,) = panel.history.entries()
    assert e["status"] == "failed" and e["detail"] == "Not enough disk space."
    panel.tabs.set_index(1)
    panel._tab(1)
    assert panel.history_list.count() == 1
