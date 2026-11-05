"""
core/evolve.py

Evolve (Halo): change the OS with Claude or another AI agent — "make window animations slower", "a widget
with my GPU temperature", "when my headphones connect, pause Spotify".

    1. new_change(request)  a workspace ~/.local/share/saint/evolve/<id>/ (a git repository) with
                            AGENTS.md/CLAUDE.md: what may change, where, and how it takes effect
    2. run_agent(...)       the agent writes there and nowhere else: home/ (files under your home
                            folder), system/ (files under /), packages.txt, apply.json
    3. review(ws)           exactly what changed (git), whether it touches the system, and anything refused
    4. apply(ws)            home files copied (old ones backed up); system files and packages only with
                            your password, between two snapper snapshots; then the reloads it asked for
                            (from a fixed list) or "after a restart"
    5. undo(ws)             home files restored from the backup; system changes reversed with
                            snapper undochange <before>..<after>

The agent is trusted with nothing: SAINT checks every path against the extension points below,
refuses links, oversized files and anything outside them, and runs only its own fixed commands.

The second half of this file is the OS Expansion Agent: changes to SAINT/Halo's own source, made by Claude
Code (the user's own account) in an isolated git worktree, plan -> approve -> snapshot -> apply -> test ->
keep or roll back. See the section banner below.
"""

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional

ROOT = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "saint" / "evolve"
MAX_FILE = 512 * 1024

# Where an agent's files may go. home/ is relative to your home folder, system/ to /.
HOME_ALLOWED = (".local/share/kwin/scripts/", ".local/share/kwin/effects/", ".local/share/plasma/plasmoids/",
                ".local/share/plasma/wallpapers/", ".local/share/plasma/look-and-feel/", ".local/share/color-schemes/",
                ".local/share/sounds/", ".local/share/icons/", ".local/share/applications/", ".local/share/saint/extensions/",
                ".config/autostart/", ".config/kwinrulesrc", ".config/kglobalshortcutsrc", ".config/kdeglobals",
                ".config/kwinrc", ".config/plasmarc", ".config/systemd/user/")
SYSTEM_ALLOWED = ("etc/udev/rules.d/", "etc/sysctl.d/", "etc/modprobe.d/", "etc/systemd/system/", "etc/xdg/",
                  "etc/environment.d/", "etc/fonts/conf.d/", "usr/local/bin/", "usr/local/share/")
SYSTEM_NEVER = ("etc/sudoers", "etc/passwd", "etc/shadow", "etc/group", "etc/pam.d/", "etc/polkit-1/",
                "etc/ssh/", "etc/pacman")
RELOADS: Dict[str, List[str]] = {
    "kwin": ["qdbus6", "org.kde.KWin", "/KWin", "reconfigure"],
    "plasma": ["systemctl", "--user", "restart", "plasma-plasmashell.service"],
    "menu": ["kbuildsycoca6"],
    "systemd-user": ["systemctl", "--user", "daemon-reload"],
    "saint": ["saint", "--quit"],             # SAINT starts again from its pin / the next "Hey SAINT"
}
_PKG = re.compile(r"^[a-z0-9@_+][a-z0-9@._+-]{0,127}$")

AGENT_GUIDE = """# Evolve workspace (SAINT, Halo)

The user asked for this change to their Halo desktop (Arch Linux, KDE Plasma 6 on Wayland):

> {request}

Make it by writing files **in this folder only**:

- `home/<path>`: files to put under the user's home folder. Allowed places:
{home}
- `system/<path>`: files to put under `/` (applied with the user's password, after a snapshot). Allowed places:
{system}
- `packages.txt`: Arch packages to install, one per line (optional).
- `apply.json`: how the change takes effect, e.g. `{{"live": ["kwin"], "restart": false, "summary": "..."}}`.
  `live` may only list: {reloads}. Set `"restart": true` when it only works after a restart.

Rules: no symbolic links; files under 512 KB; don't touch anything else. KWin scripts and effects are
JavaScript packages with metadata.json; Plasma widgets are QML packages (Plasma 6). Prefer small, readable
changes, and say in apply.json's summary what you changed, in one or two sentences.
"""


def agents(which: Callable = shutil.which) -> Dict[str, Optional[List[str]]]:
    """The agents that can run here -> the argv prefix SAINT runs with the prompt appended."""
    found = {}
    if which("claude"):
        found["Claude Code"] = ["claude", "-p", "--permission-mode", "acceptEdits",
                                "--allowedTools", "Read,Write,Edit,Glob,Grep"]
    if which("codex"):
        found["Codex"] = ["codex", "exec", "--sandbox", "workspace-write"]
    if which("gemini"):
        found["Gemini CLI"] = ["gemini", "--sandbox", "-p"]
    found["Local model (Ollama)"] = None          # SAINT writes the files from the model's JSON answer
    return found


@dataclass
class Review:
    home: List[str] = field(default_factory=list)
    system: List[str] = field(default_factory=list)
    packages: List[str] = field(default_factory=list)
    refused: List[str] = field(default_factory=list)
    live: List[str] = field(default_factory=list)
    restart: bool = False
    summary: str = ""
    diff: str = ""

    @property
    def touches_system(self) -> bool:
        return bool(self.system or self.packages)


def _git(ws: Path, *args, check=True) -> str:
    env = {**os.environ, "GIT_AUTHOR_NAME": "SAINT Evolve", "GIT_AUTHOR_EMAIL": "evolve@saint.local",
           "GIT_COMMITTER_NAME": "SAINT Evolve", "GIT_COMMITTER_EMAIL": "evolve@saint.local"}
    res = subprocess.run(["git", "-C", str(ws), *args], capture_output=True, text=True, env=env)
    if check and res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {res.stderr.strip()}")
    return res.stdout


def new_change(request: str, root: Path = ROOT) -> Path:
    request = " ".join(request.split())[:2000]
    if not request:
        raise ValueError("Say what you'd like to change.")
    ws = root / time.strftime("%Y%m%d-%H%M%S")
    (ws / "home").mkdir(parents=True)
    (ws / "system").mkdir()
    guide = AGENT_GUIDE.format(request=request,
                               home="\n".join(f"  - `home/{p}`" for p in HOME_ALLOWED),
                               system="\n".join(f"  - `system/{p}`" for p in SYSTEM_ALLOWED),
                               reloads=", ".join(RELOADS))
    for name in ("AGENTS.md", "CLAUDE.md"):
        (ws / name).write_text(guide, encoding="utf-8")
    (ws / "request.txt").write_text(request + "\n", encoding="utf-8")
    (ws / ".gitignore").write_text("backup/\nstate.json\n", encoding="utf-8")
    _git(ws, "init", "-q")
    _git(ws, "add", "-A")
    _git(ws, "commit", "-q", "-m", "request")
    return ws


def run_agent(ws: Path, agent: str, on_line: Callable[[str], None] = print, ask_model: Optional[Callable] = None) -> int:
    """Run ``agent`` in the workspace. Its output streams to ``on_line``; returns its exit code."""
    request = (ws / "request.txt").read_text(encoding="utf-8").strip()
    argv = agents().get(agent)
    if argv is None:
        return _local_model(ws, request, on_line, ask_model)
    prompt = f"{request}\n\nFollow AGENTS.md in this folder exactly."
    proc = subprocess.Popen([*argv, prompt], cwd=str(ws), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    for line in proc.stdout:
        on_line(line.rstrip())
    return proc.wait()


def _local_model(ws: Path, request: str, on_line, ask_model=None) -> int:
    """A local model writes the files as JSON: {"files": [{"path", "content"}], "packages": [], "apply": {...}}."""
    ask_model = ask_model or _ask_ollama
    guide = (ws / "AGENTS.md").read_text(encoding="utf-8")
    on_line("Asking the local model…")
    answer = ask_model(guide + "\n\nAnswer with JSON only: {\"files\": [{\"path\": \"home/...\", \"content\": \"...\"}], "
                               "\"packages\": [], \"apply\": {\"live\": [], \"restart\": false, \"summary\": \"\"}}")
    try:
        data = json.loads(answer)
    except (TypeError, ValueError):
        on_line("The model didn't answer with JSON.")
        return 1
    for f in data.get("files", [])[:50]:
        rel = str(f.get("path", ""))
        if not (rel.startswith("home/") or rel.startswith("system/")) or ".." in Path(rel).parts:
            on_line(f"skipped {rel!r}")
            continue
        out = ws / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(str(f.get("content", ""))[:MAX_FILE], encoding="utf-8")
        on_line(f"wrote {rel}")
    if data.get("packages"):
        (ws / "packages.txt").write_text("\n".join(map(str, data["packages"])) + "\n", encoding="utf-8")
    (ws / "apply.json").write_text(json.dumps(data.get("apply") or {}), encoding="utf-8")
    return 0


def _ask_ollama(prompt: str) -> str:
    import requests
    from core.config import config
    r = requests.post(config.get("ai.base_url", "http://localhost:11434").rstrip("/") + "/api/generate",
                      json={"model": config.get("ai.model", "llama3.2:3b"), "prompt": prompt, "format": "json",
                            "stream": False}, timeout=600)
    r.raise_for_status()
    return r.json().get("response", "")


def _allowed(rel: str, allowed, never=()) -> bool:
    return any(rel == a.rstrip("/") or rel.startswith(a) for a in allowed) and not any(rel.startswith(n) for n in never)


def review(ws: Path) -> Review:
    """What the agent changed, sorted into what SAINT will apply and what it refuses."""
    rv = Review()
    _git(ws, "add", "-A")
    rv.diff = _git(ws, "diff", "--cached", "--stat") + "\n" + _git(ws, "diff", "--cached")
    changed = [l for l in _git(ws, "diff", "--cached", "--name-only").splitlines() if l]
    for rel in changed:
        p = ws / rel
        if rel in ("apply.json", "packages.txt") or not p.exists():
            continue
        if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FILE:
            rv.refused.append(f"{rel} (a link, not a file, or over 512 KB)")
        elif rel.startswith("home/") and _allowed(rel[5:], HOME_ALLOWED):
            rv.home.append(rel[5:])
        elif rel.startswith("system/") and _allowed(rel[7:], SYSTEM_ALLOWED, SYSTEM_NEVER):
            rv.system.append(rel[7:])
        elif rel not in ("AGENTS.md", "CLAUDE.md", "request.txt", ".gitignore"):
            rv.refused.append(f"{rel} (outside what Evolve may change)")
    pk = ws / "packages.txt"
    if pk.exists():
        for name in pk.read_text(encoding="utf-8").split():
            (rv.packages if _PKG.match(name) else rv.refused).append(name)
    try:
        plan = json.loads((ws / "apply.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        plan = {}
    rv.live = [r for r in plan.get("live", []) if r in RELOADS]
    rv.restart = bool(plan.get("restart")) or bool(rv.system)
    rv.summary = str(plan.get("summary", ""))[:500]
    return rv


def apply(ws: Path, rv: Review, home: Path = Path.home(), run: Callable = subprocess.run) -> List[str]:
    """Apply a reviewed change. Returns what was done, line by line. Raises if the system part fails."""
    done, state = [], {"home_new": [], "snapshots": None}
    backup = ws / "backup" / "home"
    for rel in rv.home:
        dest = home / rel
        if dest.exists():
            (backup / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dest, backup / rel)
        else:
            state["home_new"].append(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ws / "home" / rel, dest)
        done.append(f"~/{rel}")
    if rv.touches_system:
        pre = _snapshot(f"Evolve {ws.name}: before", run)
        cmds = []
        for rel in rv.system:
            cmds.append(["pkexec", "install", "-D", "-m", "0644", str(ws / "system" / rel), "/" + rel])
        if rv.packages:
            cmds.append(["pkexec", "pacman", "-Syu", "--needed", "--noconfirm", *rv.packages])
        for c in cmds:
            res = run(c, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"{' '.join(c[:3])}: {(res.stderr or '').strip()[:200]}")
        post = _snapshot(f"Evolve {ws.name}: after", run)
        state["snapshots"] = [pre, post]
        done += [f"/{r}" for r in rv.system] + ([f"packages: {' '.join(rv.packages)}"] if rv.packages else [])
    for r in rv.live:
        run(RELOADS[r], capture_output=True)
        done.append(f"reloaded {r}")
    (ws / "state.json").write_text(json.dumps(state), encoding="utf-8")
    _git(ws, "commit", "-q", "-m", f"applied: {rv.summary or ws.name}", check=False)
    return done


def undo(ws: Path, home: Path = Path.home(), run: Callable = subprocess.run) -> List[str]:
    rv_home = []
    state = json.loads((ws / "state.json").read_text(encoding="utf-8"))
    backup = ws / "backup" / "home"
    for f in (p for p in backup.rglob("*") if p.is_file()) if backup.exists() else []:
        rel = f.relative_to(backup).as_posix()
        shutil.copy2(f, home / rel)
        rv_home.append(f"restored ~/{rel}")
    for rel in state.get("home_new", []):
        (home / rel).unlink(missing_ok=True)
        rv_home.append(f"removed ~/{rel}")
    snaps = state.get("snapshots")
    if snaps and all(isinstance(n, int) for n in snaps):
        res = run(["pkexec", "snapper", "-c", "root", "undochange", f"{snaps[0]}..{snaps[1]}"],
                  capture_output=True, text=True)
        rv_home.append("system change reversed" if res.returncode == 0 else f"system undo failed: {res.stderr.strip()[:200]}")
    (ws / "state.json").write_text(json.dumps({**state, "undone": True}), encoding="utf-8")
    return rv_home


def history(root: Path = ROOT) -> List[Dict]:
    out = []
    for ws in sorted(root.glob("*/request.txt"), reverse=True):
        d = ws.parent
        try:
            state = json.loads((d / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = None
        out.append({"id": d.name, "path": str(d), "request": ws.read_text(encoding="utf-8").strip(),
                    "status": "not applied" if state is None else "undone" if state.get("undone") else "applied"})
    return out


def _snapshot(desc: str, run) -> Optional[int]:
    res = run(["pkexec", "snapper", "-c", "root", "create", "--print-number", "--description", desc[:80]],
              capture_output=True, text=True)
    try:
        return int(res.stdout.strip())
    except (TypeError, ValueError):
        return None


# ======================================================================================================
# OS Expansion Agent: changes to SAINT/Halo's own source code (Priority 6)
#
#   build_index(repo)          files, symbols and a one-line summary per file, cached by content hash, so the
#                              agent is handed the few relevant files instead of exploring the whole tree
#   skill_registry(ix)         what SAINT can already do (modules, learned skills, extensions), cached
#   claude_status()            is the `claude` CLI installed and signed in? If not: what to run to fix it
#   start_source_change()      an isolated git worktree on a new branch evolve/<id>; the checkout is untouched
#   plan_source_change()       Claude Code, read-only (plan mode), writes the plan          -> "planned"
#   approve()                  the user's yes                                                -> "approved"
#   apply_source_change()      Btrfs snapshot (password prompt), Claude edits the worktree,
#                              SAINT commits it                                               -> "applied"
#   test_source_change()       the matching tests run in the worktree                        -> "tested" / "failed"
#   keep() / rollback()        fast-forward the checkout onto the branch, or throw the worktree away and
#                              (with snapper) undo anything changed outside it               -> "kept" / "rolled back"
# ======================================================================================================

import ast
import hashlib
import sys

SRC_ROOT = ROOT / "source"
INDEX_DIR = ROOT / "index"
INDEX_VERSION = 1
INDEX_MAX_FILE = 256 * 1024
_TEXT_EXT = {".py", ".qml", ".js", ".ts", ".sh", ".ps1", ".md", ".json", ".toml", ".ini", ".txt", ".service",
             ".desktop", ".conf", ".swift", ".html", ".css", ".yml", ".yaml", ".in", ".cfg"}
_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "when", "make", "add", "should", "would",
         "please", "saint", "halo", "can", "you", "want", "new", "use", "able", "have", "more", "less"}
CLAUDE_PLAN_TOOLS = "Read,Glob,Grep"
CLAUDE_APPLY_TOOLS = ("Read,Edit,Write,Glob,Grep,Bash(git status:*),Bash(git diff:*),"
                      "Bash(python -m pytest:*),Bash(python3 -m pytest:*)")
CLAUDE_DENY_TOOLS = "WebFetch,WebSearch,Bash(git push:*),Bash(sudo:*),Bash(pkexec:*),Bash(rm -rf:*)"
CLAUDE_INSTALL_FIX = ("Install it from the Store (Claude Code), or in Konsole: "
                      "sudo pacman -S --needed nodejs npm && sudo npm install -g @anthropic-ai/claude-code")
CLAUDE_LOGIN_FIX = ("Open Konsole, run `claude` once and sign in with your own Anthropic account "
                    "(or run `claude auth login`), then try again.")


# ---------------- repository index ----------------

def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:20]


def _first_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip().strip("#/*\"'-! ").strip()
        if line and not line.startswith(("usr/bin", "-*-")) and "coding:" not in line:
            return line[:160]
    return ""


def describe_file(path: str, text: str):
    """(summary, symbols) for one file: deterministic, no model call."""
    ext = Path(path).suffix.lower()
    symbols: List[str] = []
    summary = ""
    if ext == ".py":
        try:
            tree = ast.parse(text)
            summary = _first_line(ast.get_docstring(tree) or "")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    symbols.append(node.name)
                    symbols += [f"{node.name}.{m.name}" for m in node.body
                                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and not m.name.startswith("__")]
        except (SyntaxError, ValueError):
            symbols = re.findall(r"^(?:async\s+)?(?:def|class)\s+(\w+)", text, re.M)
    elif ext in (".js", ".ts", ".qml"):
        symbols = re.findall(r"^\s*(?:export\s+)?(?:function|class)\s+(\w+)", text, re.M)
    elif ext == ".sh":
        symbols = re.findall(r"^\s*(?:function\s+)?([\w-]+)\s*\(\)\s*\{", text, re.M)
    elif ext == ".ps1":
        symbols = re.findall(r"^\s*function\s+([\w-]+)", text, re.M | re.I)
    elif ext == ".swift":
        symbols = re.findall(r"^\s*(?:public\s+|final\s+|private\s+)*(?:func|class|struct|enum)\s+(\w+)", text, re.M)
    elif ext == ".md":
        symbols = [h.strip() for h in re.findall(r"^#{1,3}\s+(.+)$", text, re.M)][:20]
    if ext == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                summary = "JSON: " + ", ".join(list(data)[:8])
        except ValueError:
            pass
    if not summary:
        summary = symbols[0] if ext == ".md" and symbols else _first_line(text)
    return summary, symbols[:60]


@dataclass
class RepoIndex:
    repo: Path
    files: Dict[str, Dict] = field(default_factory=dict)      # path -> {"hash", "summary", "symbols"}
    reused: int = 0
    computed: int = 0

    def search(self, query: str, n: int = 12) -> List[str]:
        words = {w for w in re.findall(r"[a-z0-9_]{3,}", query.lower()) if w not in _STOP}
        scored = []
        for path, e in self.files.items():
            p, syms, summ = path.lower(), " ".join(e.get("symbols", [])).lower(), e.get("summary", "").lower()
            s = sum(3 * (w in p) + 2 * (w in syms) + (w in summ) for w in words)
            if s:
                scored.append((-s, path))
        return [p for _, p in sorted(scored)[:n]]

    def context(self, query: str, n: int = 12) -> str:
        lines = []
        for path in self.search(query, n):
            e = self.files[path]
            syms = ", ".join(e.get("symbols", [])[:12])
            lines.append(f"- {path}: {e.get('summary') or '(no summary)'}" + (f" [{syms}]" if syms else ""))
        return "\n".join(lines)


def build_index(repo: Path, cache_dir: Path = INDEX_DIR) -> RepoIndex:
    """Index the tracked files of ``repo``. Unchanged files (same content hash) come from the cache."""
    repo = Path(repo).resolve()
    cache_file = Path(cache_dir) / (hashlib.sha1(str(repo).encode()).hexdigest()[:12] + ".json")
    try:
        cached = json.loads(cache_file.read_text(encoding="utf-8"))
        old = cached.get("files", {}) if cached.get("version") == INDEX_VERSION else {}
    except (OSError, ValueError):
        old = {}
    ix = RepoIndex(repo)
    for rel in [p for p in _git(repo, "ls-files", "-z").split("\0") if p]:
        f = repo / rel
        if Path(rel).suffix.lower() not in _TEXT_EXT or f.is_symlink() or not f.is_file():
            continue
        try:
            if f.stat().st_size > INDEX_MAX_FILE:
                continue
            data = f.read_bytes()
        except OSError:
            continue
        h = _hash(data)
        if old.get(rel, {}).get("hash") == h:
            ix.files[rel] = old[rel]
            ix.reused += 1
            continue
        summary, symbols = describe_file(rel, data.decode("utf-8", "replace"))
        ix.files[rel] = {"hash": h, "summary": summary, "symbols": symbols}
        ix.computed += 1
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps({"version": INDEX_VERSION, "repo": str(repo), "files": ix.files}), encoding="utf-8")
    return ix


# ---------------- skill registry ----------------

def _default_skills_file() -> Optional[Path]:
    try:
        from core.paths import data_path
        return Path(data_path("skills.json"))
    except Exception:
        return None


def skill_registry(ix: RepoIndex, skills_file: Optional[Path] = None, ext_dir: Optional[Path] = None,
                   cache: Path = ROOT / "skills-registry.json") -> List[Dict]:
    """What SAINT can already do, so the agent extends it instead of duplicating it. Cached until a module
    file, the learned skills or the extensions folder changes."""
    skills_file = skills_file if skills_file is not None else _default_skills_file()
    ext_dir = ext_dir if ext_dir is not None else ROOT.parent / "extensions"
    mods = {p: e for p, e in ix.files.items() if re.match(r"modules/[^/]+/(__init__|module)\.py$", p)}
    exts = sorted(d.name for d in ext_dir.iterdir() if d.is_dir()) if ext_dir.is_dir() else []
    sk_stat = ""
    if skills_file and skills_file.is_file():
        st = skills_file.stat()
        sk_stat = f"{st.st_size}:{st.st_mtime_ns}"
    fp = _hash(json.dumps([sorted((p, e["hash"]) for p, e in mods.items()), sk_stat, exts]).encode())
    try:
        old = json.loads(Path(cache).read_text(encoding="utf-8"))
        if old.get("fingerprint") == fp:
            return old["entries"]
    except (OSError, ValueError, KeyError):
        pass
    entries: Dict[str, Dict] = {}
    for p, e in sorted(mods.items()):
        name = p.split("/")[1]
        if name not in entries or e.get("summary"):
            entries[name] = {"kind": "module", "name": name, "path": f"modules/{name}/", "summary": e.get("summary", "")}
    out = list(entries.values())
    if sk_stat:
        try:
            for s in json.loads(skills_file.read_text(encoding="utf-8")) or []:
                if isinstance(s, dict) and s.get("phrase"):
                    out.append({"kind": "learned", "name": s["phrase"], "summary": f"{len(s.get('steps', []))} step(s)"})
        except (OSError, ValueError):
            pass
    out += [{"kind": "extension", "name": n, "path": str(ext_dir / n), "summary": ""} for n in exts]
    Path(cache).parent.mkdir(parents=True, exist_ok=True)
    Path(cache).write_text(json.dumps({"fingerprint": fp, "entries": out}), encoding="utf-8")
    return out


# ---------------- Claude Code (the user's own account) ----------------

@dataclass
class AgentStatus:
    ok: bool
    message: str
    fix: str = ""


def claude_status(which: Callable = shutil.which, run: Callable = subprocess.run, home: Optional[Path] = None,
                  env: Optional[Dict] = None) -> AgentStatus:
    """Whether Claude Code can run with the user's own account, and if not, exactly how to fix it."""
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    exe = which("claude")
    if not exe:
        return AgentStatus(False, "Claude Code (the `claude` command) isn't installed.", CLAUDE_INSTALL_FIX)
    try:
        ver = run([exe, "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired) as e:
        return AgentStatus(False, f"`claude` is installed but doesn't start ({e}).", CLAUDE_INSTALL_FIX)
    if ver.returncode != 0:
        return AgentStatus(False, f"`claude` is installed but doesn't start: {(ver.stderr or '').strip()[:200]}",
                           CLAUDE_INSTALL_FIX)
    out = (ver.stdout or "").strip()
    version = out.splitlines()[0] if out else "Claude Code"
    if env.get("ANTHROPIC_API_KEY") or env.get("CLAUDE_CODE_OAUTH_TOKEN") or (home / ".claude" / ".credentials.json").is_file():
        return AgentStatus(True, f"{version}: ready.")
    try:
        auth = run([exe, "auth", "status"], capture_output=True, text=True, timeout=20)
        text = (auth.stdout or "").lower()
        if auth.returncode == 0 and "not logged in" not in text and "not signed in" not in text:
            return AgentStatus(True, f"{version}: signed in.")
    except (OSError, subprocess.TimeoutExpired):
        pass
    return AgentStatus(False, f"{version} is installed but isn't signed in to your Anthropic account.", CLAUDE_LOGIN_FIX)


_NOT_LOGGED_IN = re.compile(r"invalid api key|please run /login|not logged in|authentication_error", re.I)


def claude_argv(prompt: str, tools: str, mode: str) -> List[str]:
    return ["claude", "-p", "--permission-mode", mode, "--allowedTools", tools,
            "--disallowedTools", CLAUDE_DENY_TOOLS, "--output-format", "text", prompt]


def run_claude(prompt: str, cwd: Path, tools: str, mode: str, on_line: Callable[[str], None] = print):
    """Claude Code, non-interactive, in ``cwd`` (the worktree) with only ``tools``. Returns (exit code, output)."""
    proc = subprocess.Popen(claude_argv(prompt, tools, mode), cwd=str(cwd), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, bufsize=1)
    out = []
    for line in proc.stdout:
        out.append(line.rstrip())
        on_line(line.rstrip())
    return proc.wait(), "\n".join(out)


def _check_claude_output(rc: int, text: str):
    if _NOT_LOGGED_IN.search(text or ""):
        raise RuntimeError("Claude Code isn't signed in. " + CLAUDE_LOGIN_FIX)
    if rc != 0:
        raise RuntimeError(f"Claude Code stopped (exit {rc}): {(text or '').strip()[-300:]}")


# ---------------- Btrfs snapshot (through the password prompt) ----------------

def snapshot(desc: str, run: Callable = subprocess.run, which: Callable = shutil.which) -> Dict:
    """A snapshot of / before a change, via pkexec. snapper when present (it can undo later), otherwise a
    read-only `btrfs subvolume snapshot`. When / isn't Btrfs it says so; git still protects the source."""
    try:
        fs = run(["findmnt", "-no", "FSTYPE", "/"], capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired, AttributeError):
        fs = ""
    if fs != "btrfs":
        return {"kind": None, "reason": f"/ is not Btrfs ({fs or 'unknown'}); only git protects this change"}
    if which("snapper"):
        n = _snapshot(desc, run)
        return {"kind": "snapper", "number": n} if n is not None else {"kind": None, "reason": "snapper failed"}
    target = ("/.snapshots/" if Path("/.snapshots").is_dir() else "/") + "evolve-" + time.strftime("%Y%m%d-%H%M%S")
    res = run(["pkexec", "btrfs", "subvolume", "snapshot", "-r", "/", target], capture_output=True, text=True)
    if res.returncode != 0:
        return {"kind": None, "reason": f"btrfs snapshot failed: {(res.stderr or '').strip()[:200]}"}
    return {"kind": "btrfs", "path": target}


# ---------------- one source change, as a small state machine ----------------

@dataclass
class SourceChange:
    id: str
    request: str
    repo: str
    worktree: str
    branch: str
    base: str
    root: str
    status: str = "new"            # new planned approved applied tested failed kept rolled back
    plan: str = ""
    snapshot: Optional[Dict] = None
    post_snapshot: Optional[Dict] = None
    tests: Optional[Dict] = None
    log: List[str] = field(default_factory=list)

    @property
    def meta(self) -> Path:
        return Path(self.root) / "meta" / self.id

    def save(self):
        self.meta.mkdir(parents=True, exist_ok=True)
        (self.meta / "change.json").write_text(json.dumps(self.__dict__, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "SourceChange":
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))

    def note(self, text: str):
        self.log.append(f"{time.strftime('%H:%M:%S')} {text}")
        self.save()


def default_repo() -> Optional[Path]:
    """The SAINT source checkout Evolve may change: config evolve.repo, else this app if it is a git checkout."""
    try:
        from core.config import config
        p = config.get("evolve.repo", "") or ""
    except Exception:
        p = ""
    for cand in ([Path(p).expanduser()] if p else []) + [Path(__file__).resolve().parents[1]]:
        if (cand / ".git").exists():
            return cand
    return None


def start_source_change(repo: Path, request: str, root: Path = SRC_ROOT) -> SourceChange:
    request = " ".join(request.split())[:2000]
    if not request:
        raise ValueError("Say what you'd like to change.")
    repo = Path(repo).resolve()
    base = _git(repo, "rev-parse", "HEAD").strip()
    cid = time.strftime("%Y%m%d-%H%M%S") + "-" + _hash(f"{request}{time.time()}".encode())[:4]
    wt = Path(root) / "worktrees" / cid
    wt.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", f"evolve/{cid}", str(wt), base)
    ch = SourceChange(cid, request, str(repo), str(wt), f"evolve/{cid}", base, str(root))
    ch.note(f"worktree {wt} on {ch.branch} from {base[:10]}")
    return ch


def _brief(ch: SourceChange, ix: Optional[RepoIndex], registry: Optional[List[Dict]]) -> str:
    parts = [f"Request from the Halo user (Arch Linux, KDE Plasma 6, SAINT assistant):\n> {ch.request}",
             "You are in an isolated git worktree of the SAINT/Halo repository (the current directory). Change "
             "files only inside it; don't commit or push (SAINT does that). Follow CLAUDE.md. Reuse existing "
             "modules and helpers and keep the change small."]
    ctx = ix.context(ch.request) if ix else ""
    if ctx:
        parts.append("Files most likely relevant (SAINT's index: path: summary [symbols]):\n" + ctx)
    if registry:
        parts.append("What SAINT can already do (extend these rather than duplicating them):\n" + "\n".join(
            f"- {e['kind']} {e['name']}" + (f": {e['summary']}" if e.get("summary") else "") for e in registry[:60]))
    return "\n\n".join(parts)


def plan_source_change(ch: SourceChange, ix: Optional[RepoIndex] = None, registry: Optional[List[Dict]] = None,
                       claude: Callable = run_claude, on_line: Callable[[str], None] = print) -> str:
    """Claude Code reads (plan mode, read-only tools) and writes a plan for the user to approve."""
    prompt = (_brief(ch, ix, registry) + "\n\nDo NOT edit anything yet. Reply with a short plan: the files you will "
              "change and why, the tests you will add or run, and the risks.")
    rc, text = claude(prompt, Path(ch.worktree), CLAUDE_PLAN_TOOLS, "plan", on_line)
    _check_claude_output(rc, text)
    ch.plan, ch.status = text.strip(), "planned"
    ch.note("plan written")
    return ch.plan


def approve(ch: SourceChange):
    if ch.status != "planned":
        raise RuntimeError(f"Only a planned change can be approved (this one is {ch.status}).")
    ch.status = "approved"
    ch.note("approved by the user")


def apply_source_change(ch: SourceChange, ix: Optional[RepoIndex] = None, registry: Optional[List[Dict]] = None,
                        claude: Callable = run_claude, run: Callable = subprocess.run, snap: Callable = snapshot,
                        on_line: Callable[[str], None] = print) -> str:
    """Snapshot, then Claude Code implements the approved plan in the worktree; SAINT commits it. Returns the diff."""
    if ch.status != "approved":
        raise RuntimeError("Approve the plan first.")
    ch.snapshot = snap(f"Evolve {ch.id}: before", run)
    ch.note(f"snapshot before: {ch.snapshot}")
    prompt = _brief(ch, ix, registry) + "\n\nThe user approved this plan; implement it now, with tests:\n\n" + ch.plan
    rc, text = claude(prompt, Path(ch.worktree), CLAUDE_APPLY_TOOLS, "acceptEdits", on_line)
    _check_claude_output(rc, text)
    wt = Path(ch.worktree)
    _git(wt, "add", "-A")
    if not _git(wt, "diff", "--cached", "--name-only").strip():
        ch.status = "failed"
        ch.note("Claude Code changed nothing")
        raise RuntimeError("Claude Code finished without changing anything.")
    _git(wt, "commit", "-q", "-m", f"Evolve: {ch.request[:72]}\n\n{ch.plan[:2000]}")
    if (ch.snapshot or {}).get("kind") == "snapper":
        ch.post_snapshot = snap(f"Evolve {ch.id}: after", run)
    ch.status = "applied"
    ch.note("applied in the worktree")
    return diff(ch)


def diff(ch: SourceChange) -> str:
    repo = Path(ch.repo)
    return _git(repo, "diff", "--stat", ch.base, ch.branch) + "\n" + _git(repo, "diff", ch.base, ch.branch)


def changed_files(ch: SourceChange) -> List[str]:
    return [l for l in _git(Path(ch.repo), "diff", "--name-only", ch.base, ch.branch).splitlines() if l]


def tests_for(changed: List[str], worktree: Path) -> List[str]:
    """The tests covering the changed files: changed tests, and tests/test_<name>.py per changed module."""
    out = set()
    for rel in changed:
        p = Path(rel)
        if p.parts[:1] == ("tests",) and p.name.startswith("test_") and p.suffix == ".py":
            out.add(p.as_posix())
        elif p.suffix == ".py":
            for cand in (f"tests/test_{p.stem}.py", f"tests/test_{p.parent.name}.py"):
                if (Path(worktree) / cand).is_file():
                    out.add(cand)
    return sorted(out)


def test_source_change(ch: SourceChange, run: Callable = subprocess.run, python: str = sys.executable,
                       timeout: int = 1800) -> Dict:
    """Run the tests in the worktree: the targeted ones when there are any, otherwise the whole suite."""
    if ch.status not in ("applied", "tested", "failed"):
        raise RuntimeError("Apply the change before testing it.")
    targets = tests_for(changed_files(ch), Path(ch.worktree)) or ["tests"]
    cmd = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *targets]
    try:
        res = run(cmd, cwd=ch.worktree, capture_output=True, text=True, timeout=timeout)
        passed, output = res.returncode == 0, (res.stdout or "") + (res.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        passed, output = False, f"tests didn't finish: {e}"
    ch.tests = {"passed": passed, "targets": targets, "output": output[-6000:]}
    ch.status = "tested" if passed else "failed"
    ch.note(f"tests {'passed' if passed else 'FAILED'}: {' '.join(targets)}")
    return ch.tests


def _remove_worktree(ch: SourceChange, delete_branch: bool):
    repo = Path(ch.repo)
    _git(repo, "worktree", "remove", "--force", ch.worktree, check=False)
    _git(repo, "worktree", "prune", check=False)
    if delete_branch:
        _git(repo, "branch", "-D", ch.branch, check=False)


def keep(ch: SourceChange) -> str:
    """Bring the tested change into the checkout (fast-forward only; never a surprise merge)."""
    if ch.status != "tested":
        raise RuntimeError("Only a change whose tests passed can be kept.")
    repo = Path(ch.repo)
    if _git(repo, "rev-parse", "HEAD").strip() != ch.base:
        ch.note("checkout moved on; branch kept for a manual merge")
        raise RuntimeError(f"The checkout changed since this started; the change is on branch {ch.branch} "
                           "for you to merge by hand.")
    _git(repo, "merge", "-q", "--ff-only", ch.branch)
    _remove_worktree(ch, delete_branch=False)
    ch.status = "kept"
    ch.note(f"kept: {repo} fast-forwarded to {ch.branch}")
    return f"Kept: {repo.name} now includes the change (branch {ch.branch}). Restart SAINT to use it."


def rollback(ch: SourceChange, run: Callable = subprocess.run) -> List[str]:
    """Throw the change away: the worktree and branch go; with snapper, anything changed outside the
    worktree between the two snapshots is reversed too."""
    if ch.status == "kept":
        raise RuntimeError("This change was kept; revert its commit with git instead.")
    _remove_worktree(ch, delete_branch=True)
    done = [f"removed the worktree and branch {ch.branch}"]
    pre, post = (ch.snapshot or {}).get("number"), (ch.post_snapshot or {}).get("number")
    if isinstance(pre, int) and isinstance(post, int):
        res = run(["pkexec", "snapper", "-c", "root", "undochange", f"{pre}..{post}"], capture_output=True, text=True)
        done.append("system files restored from the snapshot" if res.returncode == 0
                    else f"snapshot undo failed: {(res.stderr or '').strip()[:200]}")
    elif (ch.snapshot or {}).get("kind") == "btrfs":
        done.append(f"read-only snapshot {ch.snapshot['path']} kept (Recovery can boot it if needed)")
    ch.status = "rolled back"
    ch.note("rolled back: " + "; ".join(done))
    return done


def source_history(root: Path = SRC_ROOT) -> List[Dict]:
    out = []
    for f in sorted((Path(root) / "meta").glob("*/change.json"), reverse=True):
        try:
            ch = SourceChange.load(f)
        except (OSError, ValueError, TypeError):
            continue
        out.append({"id": ch.id, "request": ch.request, "status": ch.status, "branch": ch.branch, "path": str(f)})
    return out
