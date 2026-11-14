"""UI polish pass (2.3): plain-word Activity feed that re-filters, chat that follows the theme."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _app():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_activity_lines_read_as_plain_words():
    from ui.pages.activity import describe
    assert describe("tool.completed", {"tool": "spotify.next", "duration_ms": 212}).split() == \
        ["Finished", "spotify.next", "·", "212", "ms"]
    assert describe("conversation.turn.start", {"text": "play something"}).startswith("You said")
    assert describe("module.loaded", {"name": "x"}) == "module.loaded  {'name': 'x'}"   # unknown: raw, never hidden


def test_activity_filter_and_tabs_refilter_what_is_shown():
    _app()
    from core.events import Event
    from ui.pages.activity import GROUPS, ActivityPage
    page = ActivityPage()
    page._lines.clear()
    page._rerender()
    page._on_event(Event("tool.completed", {"tool": "spotify.next", "duration_ms": 5}))
    page._on_event(Event("wake.status", {"label": "ready"}))
    page.groups.set_index([g[0] for g in GROUPS].index("Spotify"))
    page.groups.changed.emit(page.groups.index())
    text = page.output.toPlainText()
    assert "spotify.next" in text and "Wake word" not in text
    page.groups.set_index(0)
    page.search.setText("wake")
    assert "Wake word" in page.output.toPlainText() and "spotify.next" not in page.output.toPlainText()


def test_chat_rerenders_in_the_new_theme():
    app = _app()
    from core.config import config
    from ui.theme import build_stylesheet, palette_for
    from ui.widgets import ChatView
    old = config.get("appearance.theme", "Dark")
    try:
        config.set("appearance.theme", "Dark", persist=False)
        chat = ChatView()
        chat.add("assistant", "hello")
        config.set("appearance.theme", "Light", persist=False)
        app.setStyleSheet(build_stylesheet("Light"))
        app.processEvents()
        assert palette_for("Light").text in chat.toHtml()
    finally:
        config.set("appearance.theme", old, persist=False)
        app.setStyleSheet("")
