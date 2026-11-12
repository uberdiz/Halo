# The OS action registry (`core/actions`)

Everything SAINT, HalOS Settings and HalOS Files can do to the system is an **action**: a typed, validated,
logged and (where possible) undoable operation. The LLM or a button only picks an action id and parameters;
deterministic code runs it.

```python
from core.actions import execute, Plan, undo_last

execute("settings.sound.volume", {"percent": 40}, source="gui", confirm=ask)   # -> ActionResult, never raises
Plan("Movie mode").add("settings.appearance.theme", {"mode": "dark"}).add("settings.sound.volume", {"percent": 60}).run()
undo_last()
```

`source` is `"gui"` (the user's own click), `"saint"` (voice/chat) or `"agent"` (an autonomous run).

## Trust

Trust is set per category (the first part of the id) in config `actions.trust`:

| Level | Safe | Risky | Destructive |
|---|---|---|---|
| `ask` | asks | asks | asks |
| `ask_risky` (default) | runs | asks | asks |
| `trusted` | runs | runs | **asks** |

Destructive actions always show their preview and ask. Overrides in Settings > Permissions still apply (a
"deny" blocks, a "confirm" always asks), and in the "safe" automation mode SAINT and agents can only run safe
actions. With no `confirm` callback, `execute` returns `code == "CONFIRM_REQUIRED"` and the preview; call it
again with `confirmed=True` after the user says yes.

## Actions

| Category | Ids |
|---|---|
| settings | `display.scale`, `display.resolution`, `display.night_light`, `display.brightness`, `appearance.theme`, `appearance.wallpaper_color`, `appearance.text_size`, `sound.volume`, `sound.mute`, `sound.output`, `apps.default`, `power.profile`, `power.sleep_timeout`, `power.lock_timeout`, `input.pointer_speed`, `input.keyboard_layout`, `system.timezone`, `notifications.dnd` |
| network | `wifi.power`, `wifi.connect`, `bluetooth.power` |
| files | `move`, `copy`, `rename`, `new_folder`, `trash`, `restore` (never deletes for good, never overwrites) |
| packages | `install`, `remove` (through the SAINT Store backend) |
| services | `user.control` (allow-list in `actions.user_services`) |
| power | `lock`, `sleep`, `restart`, `shutdown` (the last two are destructive) |
| windows | `focus`, `arrange` (maximise, minimise, snap left/right), `close` |
| shell | `run` (risky; destructive when the command matches the danger list; preview is the exact command) |

## Events (for a UI)

Subscribe on `core.events.event_bus`. Payloads carry `action`, `title`, `category`, `source`, `risk`, and
`plan`/`step` inside a plan.

| Event | When | Extra fields |
|---|---|---|
| `action.requested` | validated, before the trust decision is applied | `params`, `preview`, `decision` |
| `action.confirm.required` | waiting for a yes | `params`, `preview` |
| `action.denied` | blocked or declined | `error`, `code` |
| `action.started` / `action.progress` | running | `text`, `percent` |
| `action.done` / `action.failed` | finished | `message` or `error`, `entry_id`, `can_undo`, `duration_ms` |
| `action.undone` | an undo ran | `entry_id`, `ok`, `message` |
| `plan.started` / `plan.step` / `plan.done` | a multi-step plan | the step list with `status` per step |

## Log and undo

`actions/log.jsonl` in the app data folder: one line per action (secrets redacted), append-only. `undo(entry_id)`
and `undo_last(source=None)` call the action's `undo` with the token its `run` returned.

## SAINT

`core/actions/saint.py` adds three tools to SAINT's tool registry: `os.find_action` (words to matching actions,
no LLM needed), `os.run_action` and `os.undo`. A risky action is parked with SAINT's normal spoken yes/no
confirmation, using the preview as the question.

## Adding an action

In a module under `core/actions/sets/`, write `run(params)` (return an `ActionResult` with an `undo` token
holding the previous value) and an `undo(token)`, then register it:

```python
Action("settings.thing.verb", "Short title", run, {"value": P("integer", minimum=0, maximum=10)},
       risk=RISKY, undo=undo, platforms=("linux",), keywords="other words people say",
       preview=lambda p: f"Set the thing to {p['value']}.")
```

Run external tools only through `core/actions/proc.run` (argument lists, timeout, clean errors). Tests mock
`proc.run`, and **must patch `platform_name` in every action module** so nothing takes a real path on the test
machine (see the fixture in `tests/test_actions_sets.py`).
