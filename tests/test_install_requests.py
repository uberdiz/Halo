"""PC note: "Download and install usbmuxd. It may be preinstalled..." got a long chat reply instead of an install."""
from modules.agent import os_intents, router


def test_multi_sentence_download_and_install_is_an_install(monkeypatch):
    seen = []
    monkeypatch.setattr(router, "run_tool", lambda tool, describe, on_ok, **kw: seen.append((tool, kw)) or
                        router.Reply("Installing."))
    intent = os_intents.parse_os("Download and install usbmuxd. It may be preinstalled with your system already.")
    assert intent is not None and intent.name == "apps.install"
    intent.run()
    assert seen == [("apps.install", {"name": "usbmuxd"})]


def test_several_apps_are_one_question_then_installed_in_turn(monkeypatch):
    asked, ran = [], []
    monkeypatch.setattr(router.confirmations, "ask", asked.append)

    class Reg:
        def execute(self, tool, _confirmed=False, **kw):
            ran.append(kw["name"])
            return router.ToolResult(success=True, result={"summary": f"Installed {kw['name']}."})
    monkeypatch.setattr(router, "get_tool_registry", lambda: Reg())
    reply = os_intents.parse_os("install usbmuxd and iloader").run()
    assert reply.expects_reply and reply.text == "Do you want me to install usbmuxd and iloader?"
    assert len(asked) == 1 and asked[0].run() == "Installed usbmuxd. Installed iloader."
    assert ran == ["usbmuxd", "iloader"]


def test_plain_chat_is_not_an_install():
    assert os_intents.parse_os("install it") is None
