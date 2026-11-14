"""SAINT's chat: persona, the system-knowledge block, fresh conversations, short memories, Claude (Haiku) chat."""

import io
import json
import threading

import pytest

from core import claude_chat
from modules.ai import knowledge
from modules.ai.context import ConversationContext


# --------------------------------------------------------------------------- persona
def test_old_terse_default_gets_the_new_persona_but_a_custom_prompt_is_kept():
    from core.config import DEFAULT_CONFIG
    assert knowledge.persona(DEFAULT_CONFIG["voice"]["system_prompt"]) == knowledge.PERSONA
    assert knowledge.persona("") == knowledge.PERSONA
    assert knowledge.persona("You are a pirate.") == "You are a pirate."
    assert "HalOS" in knowledge.PERSONA and "markdown" in knowledge.PERSONA


# --------------------------------------------------------------------------- system knowledge
class _Sys:
    @staticmethod
    def system():
        return {"os": "HalOS 2026.11"}

    @staticmethod
    def cpu_info():
        return {"model": "Ryzen 7 5800X", "threads": 16}

    @staticmethod
    def memory():
        return {"total": 32 * 2 ** 30}

    @staticmethod
    def gpus():
        return [{"name": "GeForce RTX 3070"}]


class _Act:
    def __init__(self, title):
        self.title = title


class _Reg:
    def categories(self):
        return ["power", "settings"]

    def list(self, cat):
        return {"power": [_Act("Lock the screen"), _Act("Restart the PC")],
                "settings": [_Act("Set the volume")]}[cat]


def test_knowledge_block_is_built_from_the_system_and_the_action_registry():
    text = knowledge.build(sysinfo=_Sys, registry=_Reg(), claude=lambda: True)
    assert "HalOS 2026.11" in text and "SAINT " in text
    assert "Ryzen 7 5800X (16 threads), 32 GB RAM, GeForce RTX 3070" in text
    assert "power: lock the screen, restart the pc" in text and "settings: set the volume" in text
    assert "Claude Code is signed in" in text
    assert len(text) < 1500                              # compact: it goes with every chat turn


def test_broken_sysinfo_never_breaks_the_block():
    class Broken:
        def __getattr__(self, name):
            raise RuntimeError("no /proc")
    text = knowledge.build(sysinfo=Broken(), registry=_Reg(), claude=lambda: False)
    assert "SAINT " in text and "Hardware" not in text and "Claude" not in text


def test_system_knowledge_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(knowledge, "build", lambda: calls.append(1) or "block")
    monkeypatch.setattr(knowledge, "_cache", {"at": 0.0, "text": ""})
    assert knowledge.system_knowledge(now=1000.0) == "block"
    assert knowledge.system_knowledge(now=1000.0 + knowledge.TTL - 1) == "block"
    assert len(calls) == 1
    knowledge.system_knowledge(now=1000.0 + knowledge.TTL + 1)
    assert len(calls) == 2


# --------------------------------------------------------------------------- fresh conversations
def test_a_long_silence_starts_a_fresh_conversation():
    now = [0.0]
    ctx = ConversationContext(max_turns=6, system_prompt="sys", idle_reset_sec=600, clock=lambda: now[0])
    ctx.add_user_turn("my sound isn't working")
    ctx.add_assistant_turn("Let's check the output device.")
    now[0] = 300
    ctx.add_user_turn("still nothing")
    assert len(ctx) == 3                                 # same conversation
    now[0] = 300 + 601
    ctx.add_user_turn("what's a good movie tonight?")
    msgs = ctx.format_messages()
    assert [m["content"] for m in msgs] == ["sys", "what's a good movie tonight?"]


def test_turns_that_scroll_out_leave_a_short_note():
    ctx = ConversationContext(max_turns=1, system_prompt="sys")
    ctx.add_user_turn("tell me about the Roman empire and why it fell so slowly")
    ctx.add_assistant_turn("It was long.")
    ctx.add_user_turn("and Byzantium?")
    ctx.add_assistant_turn("It lasted longer.")
    msgs = ctx.format_messages()
    assert msgs[1]["role"] == "system" and "tell me about the Roman empire and why..." in msgs[1]["content"]
    assert [m["content"] for m in msgs[2:]] == ["and Byzantium?", "It lasted longer."]
    ctx.clear()
    assert len(ctx.format_messages()) == 1


def test_reset_context_drops_the_chat_but_keeps_the_persona():
    from modules.ai.module import AIModule
    ai = AIModule()
    ai.context.add_user_turn("my sound isn't working")
    ai.reset_context()
    assert len(ai.context) == 0
    assert ai.context.format_messages()[0]["content"] == knowledge.persona("")


# --------------------------------------------------------------------------- short, lasting memories
@pytest.mark.parametrize("text, transient", [
    ("My sound isn't working", True), ("I have no sound", True), ("Discord keeps crashing", True),
    ("I can't hear anything", True), ("I work as a nurse", False), ("I love working on cars", False),
    ("My sister's name is Mia", False)])
def test_passing_problems_are_not_facts(text, transient):
    from modules.memory.service import is_transient
    assert is_transient(text) is transient


def test_the_learner_never_stores_a_problem_as_a_fact():
    from modules.memory.learner import parse_facts
    raw = json.dumps({"facts": [{"statement": "My sound isn't working", "category": "fact", "confidence": 0.9},
                                {"statement": "I work night shifts", "category": "routine", "confidence": 0.9}]})
    assert [f["content"] for f in parse_facts(raw)] == ["I work night shifts"]


def test_core_facts_skip_problems(monkeypatch):
    from modules.memory import service
    from modules.memory.service import memory_service

    class E:
        def __init__(self, content, cat):
            self.content, self.confidence, self.updated_at = content, 0.9, 0
            self.metadata = {"category": cat}
    monkeypatch.setattr(memory_service, "all", lambda category=None: [E("My sound isn't working", "fact"),
                                                                     E("My name is Sam", "identity")])
    assert service.memory_service.core_facts() == ["My name is Sam"]


# --------------------------------------------------------------------------- Claude (Haiku) chat
def test_argv_has_no_prompt_and_no_tools():
    argv = claude_chat.build_argv("SYS", "claude-haiku-5-5", exe="claude")
    assert argv[:2] == ["claude", "-p"] and "--model" in argv and "claude-haiku-5-5" in argv
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--system-prompt") + 1] == "SYS"
    assert claude_chat.build_argv("S")[claude_chat.build_argv("S").index("--model") + 1] == "haiku"


def test_messages_become_a_system_prompt_and_a_short_transcript():
    system, prompt = claude_chat.split([
        {"role": "system", "content": "persona"}, {"role": "system", "content": "facts"},
        {"role": "user", "content": "hi"}, {"role": "assistant", "content": "Hey!"},
        {"role": "user", "content": "how much RAM do I have?"}])
    assert system == "persona\n\nfacts"
    assert prompt.startswith("Earlier in this conversation:\nUser: hi\nSAINT: Hey!")
    assert prompt.endswith("The user now says: how much RAM do I have?")
    assert claude_chat.split([{"role": "user", "content": "hello"}]) == ("", "hello")


class _Proc:
    def __init__(self, lines, code=0):
        self.stdin = io.StringIO()
        self.stdin.close = lambda: setattr(self, "sent", self.stdin.getvalue())
        self.stdout = iter(lines)
        self.stderr = io.StringIO("")
        self.returncode = code
        self.done = threading.Event()

    def poll(self):
        return self.returncode if self.done.is_set() else None

    def wait(self):
        self.done.set()
        return self.returncode

    def kill(self):
        self.done.set()


def _delta(text):
    return json.dumps({"type": "stream_event", "event": {"type": "content_block_delta",
                                                         "delta": {"type": "text_delta", "text": text}}}) + "\n"


def test_stream_sends_the_prompt_on_stdin_and_streams_words():
    procs, got = [], []

    def popen(argv, **kw):
        assert kw["stdin"] is not None and "how are you?" not in argv
        procs.append(_Proc([json.dumps({"type": "system", "subtype": "init"}) + "\n", _delta("I'm "),
                            _delta("great!"), json.dumps({"type": "result", "subtype": "success",
                                                          "result": "I'm great!"}) + "\n"]))
        return procs[-1]
    out = claude_chat.stream([{"role": "user", "content": "how are you?"}], got.append, popen=popen, exe="claude")
    assert out == "I'm great!" and got == ["I'm ", "great!"]
    assert procs[0].sent == "how are you?"


def test_not_signed_in_raises_so_the_local_model_answers(monkeypatch):
    monkeypatch.setattr(claude_chat, "_state", {"at": 0.0, "ok": True})
    lines = [json.dumps({"type": "result", "subtype": "success", "is_error": True,
                         "result": "Not logged in · Please run /login"}) + "\n"]
    with pytest.raises(claude_chat.ChatUnavailable):
        claude_chat.stream([{"role": "user", "content": "hi"}], lambda t: None,
                           popen=lambda argv, **kw: _Proc(lines, 1), exe="claude")
    assert claude_chat._state["ok"] is False and claude_chat._state["at"] > 0


def test_a_silent_claude_is_cut_off(monkeypatch):
    class Hang(_Proc):
        def __init__(self):
            super().__init__([])
            self.stdout = self._lines()

        def _lines(self):
            self.done.wait(5)
            return iter(())
            yield

    with pytest.raises(claude_chat.ChatUnavailable, match="no reply"):
        claude_chat.stream([{"role": "user", "content": "hi"}], lambda t: None, first_token_sec=0.2,
                           popen=lambda argv, **kw: Hang(), exe="claude")


def test_availability_is_checked_once_and_needs_a_sign_in(monkeypatch):
    monkeypatch.setattr(claude_chat, "_state", {"at": 0.0, "ok": False})
    checks = []
    signed = lambda exe: checks.append(exe) or True
    assert claude_chat.available(now=100.0, which=lambda n: "/usr/bin/claude", signed=signed)
    assert claude_chat.available(now=200.0, which=lambda n: None, signed=signed)          # cached
    assert checks == ["/usr/bin/claude"]
    monkeypatch.setattr(claude_chat, "_state", {"at": 0.0, "ok": False})
    assert not claude_chat.available(now=100.0, which=lambda n: None, signed=signed)


def test_ai_module_uses_claude_for_chat_only_off_the_mock_and_api_providers(monkeypatch):
    from core.config import config
    from modules.ai.module import AIModule
    ai = AIModule()
    monkeypatch.setattr(claude_chat, "available", lambda: True)
    monkeypatch.setattr(claude_chat, "stream", lambda messages, on_token, cancel_flag=None: on_token("Hi!") or "Hi!")
    got = []
    assert ai._claude_chat([{"role": "user", "content": "hi"}], got.append) is False       # tests run on "mock"
    monkeypatch.setattr(config, "get", lambda k, d=None: "ollama" if k == "ai.provider" else d)
    assert ai._claude_chat([{"role": "user", "content": "hi"}], got.append) is True and got == ["Hi!"]

    def down(messages, on_token, cancel_flag=None):
        raise claude_chat.ChatUnavailable("offline")
    monkeypatch.setattr(claude_chat, "stream", down)
    assert ai._claude_chat([{"role": "user", "content": "hi"}], got.append) is False
