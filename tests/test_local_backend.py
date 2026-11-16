from core import claude_agent


def test_local_env_points_claude_code_at_local_models_only():
    env = claude_agent.local_env({"ANTHROPIC_API_KEY": "sk-real", "PATH": "/usr/bin"})
    assert env["ANTHROPIC_API_KEY"] == ""                      # a real key can never reach the local run
    assert env["ANTHROPIC_BASE_URL"].startswith("http://127.0.0.1")
    assert env["ANTHROPIC_DEFAULT_SONNET_MODEL"] == env["ANTHROPIC_MODEL"] == "evolve-coder"
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "evolve-fast"
    assert env["PATH"] == "/usr/bin"


class _R:
    def __init__(self, names):
        self.names = names

    def json(self):
        return {"models": [{"name": n} for n in self.names]}


def test_local_status():
    assert claude_agent.local_status(lambda *a, **k: _R(["evolve-coder:latest", "evolve-fast:latest"])) == ""
    assert "evolve-fast" in claude_agent.local_status(lambda *a, **k: _R(["evolve-coder:latest"]))

    def down(*a, **k):
        raise OSError("refused")
    assert "isn't answering" in claude_agent.local_status(down)
