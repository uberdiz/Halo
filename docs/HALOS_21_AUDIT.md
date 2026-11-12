# HalOS 2.1 audit (2026-11-12)

Checked against source on `halo/roadmap-2026-11` @ 96b619f, not against older docs. Test run on the Windows dev PC:
2,330 passed, 8 skipped, 5 failed (pre-existing, see §5).

## 1. Works (exercised by tests or a run on the dev PC)
- OS action registry (45 actions, trust levels, undo, log) — `core/actions/`
- Plain-phrase intents → deterministic tools — `modules/agent/*_intents.py`, `router.py`
- Plan panel, window outline, Halo progress line — `ui/plan_panel.py`, `ui/act_highlight.py`
- Agent mode on Claude Code (faked CLI in tests) — `core/claude_agent.py`
- Task Manager data: processes, CPU, RAM, disks, battery, services, basic GPU — `core/sysinfo.py`, `ui/taskmanager.py`
- **New (this audit):** NVIDIA detail via NVML/nvidia-smi (VRAM, load, enc/dec, temp, power/limit, clocks, fan,
  PCIe, throttle, CUDA) + per-process VRAM, tool `system.gpu`, and deterministic answers to "what's using my GPU",
  "is Ollama on my GPU", "is it throttling". Verified live on the dev PC's RTX 5060 Ti.
- Reminders with natural-language time — `modules/automation/` (scheduler, timeparse)
- Hardware-matched model catalog, `ollama pull` with progress — `core/agent_catalog.py`, `core/model_pull.py`
- Store (repos, Flathub, AUR, Wine) — `core/store*.py`, `ui/store_app.py`
- HalOS-Setup.exe self-test, plan and dry run on Windows

## 2. Implemented, never run inside HalOS
Everything marked 🔧 in `HALOS_STATUS.md`: end-to-end install, dual boot, Secure Boot/shim/MOK, NVIDIA open driver,
KWin placement/tiling, living wallpaper, pacman queue, migration on a real disk, voice stack on Linux, SAINT Link,
KRdp. **No v2 ISO has been booted or installed.** This is the #1 public-release blocker.

## 3. Partial
| Area | Exists | Missing |
|---|---|---|
| System Overview | `ui/pages/overview.py`, Task Manager | per-core, history ranges (5m/1h/24h/7d), SMART detail (`disk_health` only), network throughput history, failed-units view, GPU panel using `nvidia_detail` |
| Window control | `modules/workspace/` (save/restore/list/forget named workspaces, by voice), `core/tiling.py` task tiling, monitor-aware move/snap/place-beside in `modules/desktop/controller.py`, gaming workspace preset | more built-in presets (Development, Research, Diagnostics); multi-monitor run on HalOS |
| Model management | pull + catalog | pause/resume, inference smoke test after pull, GPU-actually-used check (now possible via `gpu_processes`) |
| Homepage | `ui/pages/halo_os.py` | reminders/tasks/system widgets, quick actions |
| Release docs | README, GUIDE, TESTING_V2 | hardware guide, troubleshooting, recovery, privacy, known issues, CONTRIBUTING, issue templates, checksums |

## 4. Missing entirely
- SAINT avatar (no VRM/glTF loader, no viseme/lip-sync, no states) — needs `ui/avatar/` + a renderer decision
  (QtQuick3D can load glTF; VRM needs an extension parser). Reference image exists: `SAINT.png`.
- Visual Shop (no catalog, manifest, integrity or license fields).
- `.github/ISSUE_TEMPLATE/`.

## 5. Broken
- 5 failing tests, unrelated to this work: `test_link_node::test_identity_persists…`,
  `test_saintos_center` (2× secret store), `test_settings_ai::test_key_goes_to_the_secret_store_only`,
  `test_v04_selftest::test_quick_checks_pass_from_source`. Likely the Windows secret store on this PC; needs a look.

## 6. Before a public beta (in order)
1. Build ISO, boot + install in VM (UEFI, Secure Boot), then real-PC dual boot (`docs/TESTING_V2.md`).
2. Fix the 5 failing tests.
3. Release docs + issue templates + SHA256 for ISO parts.
4. Only claim features that passed step 1.

## 7. Where each requested feature goes
| Feature | Extend |
|---|---|
| GPU / system intelligence | `core/sysinfo.py` (done for NVIDIA), `modules/desktop/taskmgr.py` tools, `taskmgr_intents.py` |
| System Overview | `ui/taskmanager.py`, `ui/pages/overview.py` |
| Workspaces | `core/tiling.py`, `modules/agent/winctl_intents.py`, KWin `saint-shell` script |
| Reminders on Home | `modules/automation/scheduler.py` → `ui/pages/halo_os.py` |
| Model install | `core/model_pull.py`, `core/agent_catalog.py` |
| Avatar | new `ui/avatar/`, state from `core/assistant_state.py`, audio from voice TTS |
| Visual Shop | new `core/visual_shop.py` reusing `core/downloads.py` + Store UI patterns |

## 8. Risks
- NVTOP: GPL-3; not vendored. We read the same NVML data through `nvidia-smi` (already in `nvidia-utils`), so no new
  dependency. Direct NVML (`nvidia-ml-py`) only if polling cost of `nvidia-smi` (~50–100 ms/call) matters.
- Avatar/shop imports are untrusted: glTF/VRM must be parsed as data only, size-capped, no scripts; shop packages
  need SHA256 + license field, and no executable content.
- Avatar rendering GPU cost competes with local LLM VRAM; needs a reduced-motion/off mode by default on low VRAM.
- GPU process list on Windows WDDM often lacks names/memory (shown as pid → psutil name).
