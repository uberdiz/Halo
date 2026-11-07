"""
modules/ai/providers.py

Abstract AI provider interface. Extended with Ollama model discovery,
connection testing, and robust error handling.
"""

import json
import time
import threading
from typing import Callable, List, Dict, Optional, Any

import requests


class ProviderError(Exception):
    pass


class ModelNotFoundError(ProviderError):
    pass


class ConnectionError(ProviderError):
    pass


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class AIProvider:
    def send(self, messages, model, api_key, base_url, temperature, timeout) -> str:
        raise NotImplementedError

    def stream_send(
        self,
        messages: List[Dict],
        model: str,
        api_key: str,
        base_url: str,
        temperature: float,
        timeout: float,
        on_token: Callable[[str], None],
        cancel_flag,           # threading.Event — set to abort
    ) -> str:
        """Stream tokens via on_token(); return full accumulated text."""
        raise NotImplementedError

    def test_connection(self, base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Test connection to the provider. Override in subclasses."""
        raise NotImplementedError

    def list_models(self, base_url: str, timeout: float = 10.0) -> List[Dict[str, Any]]:
        """List available models. Override in subclasses."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Mock
# ---------------------------------------------------------------------------
MOCK_RESPONSES = {
    "python": "Python is a high-level, interpreted programming language known for its clean syntax and vast ecosystem.",
    "lua": "Lua is a lightweight, embeddable scripting language popular in game development and embedded systems.",
    "chrome": "Chrome it is.",
    "firefox": "Right — Firefox it is.",
    "default": "I understand. Let me help you with that.",
}


def _pick_mock_response(messages: List[Dict]) -> str:
    last_user = ""
    for m in reversed(messages):
        if m["role"] == "user":
            last_user = m["content"].lower()
            break
    has_interruption = any("[interrupted]" in m.get("content", "") for m in messages)

    if "lua" in last_user:
        return "Sure, Lua is a lightweight scripting language widely used in game engines and embedded systems. It's fast, minimal, and easy to embed."
    if "python" in last_user:
        return "Python is a high-level programming language celebrated for its readability and massive ecosystem of libraries."
    if "firefox" in last_user:
        prefix = "Right — " if has_interruption else ""
        return prefix + "Firefox it is."
    if "chrome" in last_user:
        return "Chrome it is."
    return MOCK_RESPONSES["default"]


class MockProvider(AIProvider):
    """Simulates streaming by emitting words with small delays. No network required."""

    WORD_DELAY = 0.04

    def send(self, messages, model, api_key, base_url, temperature, timeout) -> str:
        time.sleep(0.3)
        return _pick_mock_response(messages)

    def stream_send(self, messages, model, api_key, base_url, temperature, timeout,
                    on_token, cancel_flag) -> str:
        text = _pick_mock_response(messages)
        accumulated = []
        words = text.split()
        for i, word in enumerate(words):
            if cancel_flag and cancel_flag.is_set():
                break
            token = (word + " ") if i < len(words) - 1 else word
            on_token(token)
            accumulated.append(token)
            time.sleep(self.WORD_DELAY)
        return "".join(accumulated)

    def test_connection(self, base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        return {"connected": True, "provider": "mock", "latency_ms": 0}

    def list_models(self, base_url: str, timeout: float = 10.0, force_refresh: bool = False) -> List[Dict[str, Any]]:
        return [
            {"name": "mock-model", "size": 0, "modified_at": "", "digest": ""}
        ]


# ---------------------------------------------------------------------------
# OpenAI-compatible (SSE streaming)
# ---------------------------------------------------------------------------
class OpenAICompatibleProvider(AIProvider):

    def send(self, messages, model, api_key, base_url, temperature, timeout) -> str:
        if not api_key:
            raise ProviderError("No API key configured for the OpenAI-compatible provider.")

        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {"model": model, "messages": messages, "temperature": temperature}
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=timeout)
        except requests.RequestException as e:
            raise ProviderError(f"Network error: {e}") from e

        if resp.status_code != 200:
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ProviderError(f"Unexpected response shape: {data}") from e

    def stream_send(self, messages, model, api_key, base_url, temperature, timeout,
                    on_token, cancel_flag) -> str:
        if not api_key:
            raise ProviderError("No API key configured.")

        url = base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        accumulated = []
        try:
            with requests.post(url, headers=headers, json=body,
                               timeout=timeout, stream=True) as resp:
                if resp.status_code != 200:
                    raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
                for line in resp.iter_lines():
                    if cancel_flag and cancel_flag.is_set():
                        break
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        decoded = decoded[6:]
                    if decoded == "[DONE]":
                        break
                    try:
                        chunk = json.loads(decoded)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            on_token(delta)
                            accumulated.append(delta)
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
        except requests.RequestException as e:
            raise ProviderError(f"Network error: {e}") from e

        return "".join(accumulated)

    def test_connection(self, base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Is an OpenAI-compatible server answering at ``base_url``? (GET /models, no key sent.)

        200 means reachable and open; 401/403 means reachable but it needs the API key, which is
        checked on the first real request. Anything else, or no answer, is "not connected".
        """
        if not base_url:
            return {"connected": False, "provider": "openai", "error": "no address configured"}
        url = base_url.rstrip("/") + "/models"
        t0 = time.perf_counter()
        try:
            resp = requests.get(url, timeout=timeout)
        except requests.RequestException as e:
            return {"connected": False, "provider": "openai", "error": f"no answer from {base_url}: {e}"}
        latency = round((time.perf_counter() - t0) * 1000)
        if resp.status_code == 200:
            return {"connected": True, "provider": "openai", "latency_ms": latency, "auth": "not required"}
        if resp.status_code in (401, 403):
            return {"connected": True, "provider": "openai", "latency_ms": latency, "auth": "required"}
        return {"connected": False, "provider": "openai", "error": f"HTTP {resp.status_code} from {url}"}

    def list_models(self, base_url: str, timeout: float = 10.0) -> List[Dict[str, Any]]:
        try:
            url = base_url.rstrip("/") + "/models"
            headers = {"Authorization": "Bearer test"}
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("data", [])
            return []
        except requests.RequestException:
            return []


# ---------------------------------------------------------------------------
# Ollama (NDJSON streaming — local GPU)
# ---------------------------------------------------------------------------
class OllamaProvider(AIProvider):

    _models_cache: List[Dict[str, Any]] = []
    _cache_time: float = 0
    _cache_lock = threading.Lock()
    _CACHE_TTL = 30.0  # seconds

    def _request(self, method: str, endpoint: str, base_url: str, timeout: float, **kwargs) -> requests.Response:
        base_url = base_url.replace("localhost", "127.0.0.1")
        url = base_url.rstrip("/") + endpoint
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            return resp
        except requests.RequestException as e:
            raise ConnectionError(f"Network error contacting Ollama: {e}") from e

    def _options(self, temperature: float) -> Dict[str, Any]:
        from core.config import config
        opts: Dict[str, Any] = {"temperature": temperature, "num_gpu": -1}
        cap = int(config.get("ai.max_tokens", 0) or 0)
        if cap > 0:
            opts["num_predict"] = cap
        return opts

    def send(self, messages, model, api_key, base_url, temperature, timeout) -> str:
        resp = self._request("POST", "/api/chat", base_url, timeout,
                            json={"model": model, "messages": messages, "stream": False,
                                  "keep_alive": -1, "options": self._options(temperature)})
        if resp.status_code != 200:
            if resp.status_code == 404:
                raise ModelNotFoundError(f"Model '{model}' not found. Run 'ollama pull {model}' first.")
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ProviderError(f"Unexpected response shape: {resp.text[:300]}") from e

    def stream_send(self, messages, model, api_key, base_url, temperature, timeout,
                    on_token, cancel_flag) -> str:
        resp = self._request("POST", "/api/chat", base_url, timeout,
                            json={"model": model, "messages": messages, "stream": True,
                                  "keep_alive": -1, "options": self._options(temperature)},
                            stream=True)
        if resp.status_code != 200:
            if resp.status_code == 404:
                raise ModelNotFoundError(f"Model '{model}' not found. Run 'ollama pull {model}' first.")
            raise ProviderError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        accumulated = []
        try:
            with resp:
                for line in resp.iter_lines():
                    if cancel_flag and cancel_flag.is_set():
                        break
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            on_token(token)
                            accumulated.append(token)
                        if chunk.get("done", False):
                            break
                    except (json.JSONDecodeError, KeyError):
                        continue
        except requests.RequestException as e:
            raise ProviderError(f"Network error: {e}") from e
        return "".join(accumulated)

    def test_connection(self, base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Test Ollama connection and return version info."""
        try:
            resp = self._request("GET", "/api/version", base_url, timeout)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "provider": "ollama",
                    "version": data.get("version", "unknown"),
                }
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
        except ConnectionError as e:
            return {"connected": False, "error": str(e)}
        except requests.RequestException as e:
            return {"connected": False, "error": str(e)}

    def list_models(self, base_url: str, timeout: float = 10.0, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """List available Ollama models with caching."""
        now = time.time()
        with self._cache_lock:
            if not force_refresh and self._models_cache and (now - self._cache_time) < self._CACHE_TTL:
                return self._models_cache
            
            try:
                resp = self._request("GET", "/api/tags", base_url, timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    models = data.get("models", [])
                    self._models_cache = models
                    self._cache_time = now
                    return models
                return []
            except requests.RequestException:
                return []

    def pull_model(self, base_url: str, model: str, timeout: float = 300.0) -> Dict[str, Any]:
        """Pull a model from Ollama registry."""
        try:
            resp = self._request("POST", "/api/pull", base_url, timeout,
                                json={"name": model, "stream": False})
            if resp.status_code == 200:
                return {"success": True, "status": resp.json().get("status", "done")}
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        except requests.RequestException as e:
            return {"success": False, "error": str(e)}

    def pull_model_stream(self, base_url: str, model: str, on_progress: Callable[[Dict[str, Any]], None],
                          cancel_flag: Optional[threading.Event] = None, timeout: float = 30.0) -> Dict[str, Any]:
        """Pull ``model`` with Ollama's streamed /api/pull, calling ``on_progress`` with
        {"status", "completed", "total", "percent"} summed over every layer. A pull already running (the
        saint-ollama-model service's) is joined: Ollama shares the download, so this shows its progress.
        ``timeout`` is per read, not for the whole download."""
        try:
            resp = self._request("POST", "/api/pull", base_url, timeout, json={"model": model, "name": model,
                                                                              "stream": True}, stream=True)
        except ConnectionError as e:
            return {"success": False, "error": str(e)}
        if resp.status_code != 200:
            return {"success": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}"}
        layers: Dict[str, List[int]] = {}
        status = ""
        try:
            with resp:
                for line in resp.iter_lines():
                    if cancel_flag is not None and cancel_flag.is_set():
                        return {"success": False, "error": "cancelled", "cancelled": True}
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("error"):
                        return {"success": False, "error": str(chunk["error"])[:300]}
                    status = chunk.get("status", status) or status
                    if chunk.get("digest") and chunk.get("total"):
                        layers[chunk["digest"]] = [int(chunk.get("completed") or 0), int(chunk["total"])]
                    done = sum(c for c, _ in layers.values())
                    total = sum(t for _, t in layers.values())
                    on_progress({"status": status, "completed": done, "total": total,
                                 "percent": round(100.0 * done / total, 1) if total else None})
                    if status == "success":
                        return {"success": True, "status": status, "total": total}
        except requests.RequestException as e:
            return {"success": False, "error": f"Network error: {e}"}
        return {"success": status == "success", "status": status,
                **({} if status == "success" else {"error": f"the download stopped ({status or 'no status'})"})}


# ---------------------------------------------------------------------------
# Anthropic (Claude): the Messages API over SSE, with requests like the providers above (no new dependency)
# ---------------------------------------------------------------------------
ANTHROPIC_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2026-10-21"
ANTHROPIC_DEFAULT_MODEL = "claude-sonnet-5-5"
ANTHROPIC_MODELS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"]
# On a safety decline the API continues on another model in the same request. These models take the "default" form.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_FALLBACK_MODELS = ("claude-sonnet-5-5", "claude-opus-5-5", "claude-opus-5", "claude-fable-5-1")


class AnthropicProvider(AIProvider):
    """Claude. The key comes from the secret store (``ai.anthropic_api_key``), so the shared ``ai.api_key`` of the
    OpenAI-compatible provider is never sent here. Temperature isn't sent: current Claude models reject it. Effort
    is low: this answers a voice assistant, and reasoning-heavy work goes through Evolve."""

    def _key(self, api_key: str = "") -> str:
        from core.config import config
        return config.get("ai.anthropic_api_key", "") or (api_key if str(api_key).startswith("sk-ant") else "")

    def _headers(self, key: str, model: str = "") -> Dict[str, str]:
        headers = {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION, "content-type": "application/json"}
        if model in _FALLBACK_MODELS:
            headers["anthropic-beta"] = _FALLBACK_BETA
        return headers

    @staticmethod
    def convert(messages: List[Dict]):
        """(system, messages) for the API from SAINT's list: system messages move to the top level; run_with_tools'
        Ollama-style assistant tool_calls and role "tool" results become tool_use and tool_result blocks. Assistant
        turns that came from Claude replay their blocks unchanged (thinking blocks must come back as they were)."""
        system, out = [], []
        for m in messages:
            role = m.get("role")
            if role == "system":
                system.append(str(m.get("content", "")))
            elif role == "tool" and not m.get("tool_call_id"):   # a call the model wrote as text: no tool_use to answer
                out.append({"role": "user", "content": f"Result of {m.get('tool_name', 'the tool')}: {m.get('content', '')}"})
            elif role == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": str(m.get("content", ""))}
                if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list):
                    out[-1]["content"].append(block)          # one user message per assistant turn's results
                else:
                    out.append({"role": "user", "content": [block]})
            elif role == "assistant" and m.get("anthropic_blocks"):
                out.append({"role": "assistant", "content": m["anthropic_blocks"]})
            elif m.get("content"):
                out.append({"role": role, "content": m["content"]})
        return "\n\n".join(s for s in system if s), out

    @staticmethod
    def tool_schema(schema: Dict) -> Dict:
        fn = schema.get("function", schema)
        return {"name": fn["name"], "description": fn.get("description", ""), "eager_input_streaming": True,
                "input_schema": fn.get("parameters") or {"type": "object", "properties": {}}}

    def _body(self, messages: List[Dict], model: str, stream: bool, tools: Optional[List[Dict]] = None) -> Dict:
        from core.config import config
        system, msgs = self.convert(messages)
        # Thinking shares this limit, so a voice reply cap (ai.max_tokens, e.g. 150) gets a floor.
        cap = int(config.get("ai.max_tokens", 0) or 0)
        body: Dict[str, Any] = {"model": model or ANTHROPIC_DEFAULT_MODEL, "messages": msgs,
                                "max_tokens": max(cap, 1024) if cap else 16000, "output_config": {"effort": "low"}}
        if system:
            body["system"] = system
        if stream:
            body["stream"] = True
        if tools:
            body["tools"] = [self.tool_schema(t) for t in tools]
        if body["model"] in _FALLBACK_MODELS:
            body["fallbacks"] = "default"
        return body

    def _raise_for_status(self, resp, model: str):
        if resp.status_code == 200:
            return
        try:
            message = resp.json()["error"]["message"]
        except (ValueError, KeyError, TypeError):
            message = (resp.text or "")[:200]
        if resp.status_code == 401:
            raise ProviderError("Anthropic rejected the API key (Settings > AI > Claude).")
        if resp.status_code == 404:
            raise ModelNotFoundError(f"Claude model '{model}' not found: {message}")
        raise ProviderError(f"Anthropic HTTP {resp.status_code}: {message}"[:300])

    def _post(self, body: Dict, key: str, timeout: float, stream: bool):
        if not key:
            raise ProviderError("No Claude API key. Add one in Settings > AI > Claude.")
        try:
            return requests.post(f"{ANTHROPIC_URL}/messages", headers=self._headers(key, body["model"]), json=body,
                                 timeout=timeout, stream=stream)
        except requests.RequestException as e:
            raise ConnectionError(f"Network error contacting Anthropic: {type(e).__name__}") from e

    def send(self, messages, model, api_key, base_url, temperature, timeout) -> str:
        body = self._body(messages, model, stream=False)
        resp = self._post(body, self._key(api_key), timeout, stream=False)
        self._raise_for_status(resp, body["model"])
        data = resp.json()
        if data.get("stop_reason") == "refusal":
            raise ProviderError("Claude declined to answer that.")
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")

    def stream_send(self, messages, model, api_key, base_url, temperature, timeout, on_token, cancel_flag) -> str:
        return self.stream_turn(messages, model, api_key, timeout, on_token, cancel_flag)["text"]

    def stream_turn(self, messages, model, api_key, timeout, on_token, cancel_flag=None,
                    tools: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """One streamed model turn: text goes to ``on_token``. Returns {"text", "calls", "blocks", "stop_reason"}:
        ``calls`` in run_with_tools' shape, ``blocks`` the assistant content to replay on the next request."""
        body = self._body(messages, model, stream=True, tools=tools)
        resp = self._post(body, self._key(api_key), timeout, stream=True)
        self._raise_for_status(resp, body["model"])
        blocks: Dict[int, Dict] = {}
        tool_json: Dict[int, List[str]] = {}
        text: List[str] = []
        stop = ""
        try:
            with resp:
                for line in resp.iter_lines():
                    if cancel_flag is not None and cancel_flag.is_set():
                        break
                    if not line or not line.startswith(b"data:"):
                        continue
                    try:
                        ev = json.loads(line[5:].decode("utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    kind = ev.get("type")
                    if kind == "content_block_start":
                        blocks[ev["index"]] = dict(ev["content_block"])
                    elif kind == "content_block_delta":
                        delta, block = ev.get("delta", {}), blocks.get(ev.get("index"))
                        if block is None:
                            continue
                        dtype = delta.get("type")
                        if dtype == "text_delta":
                            block["text"] = block.get("text", "") + delta.get("text", "")
                            text.append(delta.get("text", ""))
                            on_token(delta.get("text", ""))
                        elif dtype == "input_json_delta":
                            tool_json.setdefault(ev["index"], []).append(delta.get("partial_json", ""))
                        elif dtype == "thinking_delta":
                            block["thinking"] = block.get("thinking", "") + delta.get("thinking", "")
                        elif dtype == "signature_delta":
                            block["signature"] = block.get("signature", "") + delta.get("signature", "")
                    elif kind == "message_delta":
                        stop = (ev.get("delta") or {}).get("stop_reason") or stop
                    elif kind == "error":
                        raise ProviderError(f"Anthropic: {(ev.get('error') or {}).get('message', 'stream error')}"[:300])
                    elif kind == "message_stop":
                        break
        except requests.RequestException as e:
            raise ConnectionError(f"Network error contacting Anthropic: {type(e).__name__}") from e
        if stop == "refusal" and not text:
            raise ProviderError("Claude declined to answer that.")
        calls = []
        for i, block in sorted(blocks.items()):
            if block.get("type") != "tool_use":
                continue
            # With eager streaming the API doesn't validate the input: unparsable means the tool gets nothing.
            try:
                args = json.loads("".join(tool_json.get(i, [])) or "{}")
            except json.JSONDecodeError:
                args = {}
            block["input"] = args if isinstance(args, dict) else {}
            calls.append({"id": block.get("id", ""), "function": {"name": block.get("name", ""), "arguments": block["input"]}})
        if stop == "max_tokens":
            calls = []                                 # a cut-off tool call must not run
            blocks = {i: b for i, b in blocks.items() if b.get("type") != "tool_use"}
        return {"text": "".join(text), "calls": calls, "stop_reason": stop,
                "blocks": [b for _, b in sorted(blocks.items()) if b.get("type") != "text" or b.get("text")]}

    def test_key(self, api_key: str = "", timeout: float = 10.0) -> Dict[str, Any]:
        """Does Anthropic accept this key? GET /v1/models: no tokens spent."""
        key = (api_key or "").strip() or self._key()
        if not key:
            return {"connected": False, "provider": "anthropic", "error": "no API key saved"}
        t0 = time.perf_counter()
        try:
            resp = requests.get(f"{ANTHROPIC_URL}/models", headers=self._headers(key), timeout=timeout)
        except requests.RequestException as e:
            return {"connected": False, "provider": "anthropic", "error": f"no answer from Anthropic ({type(e).__name__})"}
        if resp.status_code == 200:
            return {"connected": True, "provider": "anthropic", "version": "key accepted",
                    "latency_ms": round((time.perf_counter() - t0) * 1000)}
        error = "the key was rejected" if resp.status_code in (401, 403) else f"HTTP {resp.status_code}"
        return {"connected": False, "provider": "anthropic", "error": error}

    def test_connection(self, base_url: str = "", timeout: float = 5.0) -> Dict[str, Any]:
        return self.test_key(timeout=timeout)

    def list_models(self, base_url: str = "", timeout: float = 10.0, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """The models this key can use, current ones first; the known list without a key or a network."""
        names = list(ANTHROPIC_MODELS)
        key = self._key()
        if key:
            try:
                resp = requests.get(f"{ANTHROPIC_URL}/models", headers=self._headers(key), timeout=timeout)
                if resp.status_code == 200:
                    names += [m["id"] for m in resp.json().get("data", []) if m.get("id") not in names]
            except (requests.RequestException, ValueError, KeyError):
                pass
        return [{"name": n} for n in names]


# ---------------------------------------------------------------------------
# Provider Factory
# ---------------------------------------------------------------------------
_PROVIDER_CACHE: Dict[str, AIProvider] = {}
_PROVIDER_CACHE_LOCK = threading.Lock()


def get_provider(name: str) -> AIProvider:
    """Get provider instance with singleton caching."""
    with _PROVIDER_CACHE_LOCK:
        if name not in _PROVIDER_CACHE:
            _PROVIDER_CACHE[name] = {
                "mock": MockProvider,
                "openai": OpenAICompatibleProvider,
                "ollama": OllamaProvider,
                "anthropic": AnthropicProvider,
            }.get(name, MockProvider)()
        return _PROVIDER_CACHE[name]


def clear_provider_cache():
    """Clear the provider cache (useful for testing)."""
    with _PROVIDER_CACHE_LOCK:
        _PROVIDER_CACHE.clear()