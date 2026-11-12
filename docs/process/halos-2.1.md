# HalOS 2.1 — how it was built (2026-11-12)

A record of the 2.1 work for later inspection: what was asked, what was decided, what was built in which order,
what went wrong and how it was found, and what was actually verified. Commit hashes are on branch
`halo/roadmap-2026-11`. One-line entries per item are also in [PROGRESS.md](../PROGRESS.md).

## 1. The brief and the decisions

The brief (a long "HalOS 2.1" master prompt) asked for a public beta: release infrastructure and docs, an animated
SAINT avatar with customization and imports, a Visual Shop, a hardware intelligence dashboard with NVIDIA/nvtop-level
GPU data, a typed system API for SAINT, a multi-window AI workspace, a homepage with reminders and tasks, better
Ollama model handling, and a final release candidate.

Questions asked up front and the answers given:

| Question | Answer |
|---|---|
| Source of the 3D SAINT model | First: "you make it in VRoid". Later the user supplied `Model/SAINT.vrm` (VRoid, VRM 1.0), which became the default. |
| What the Visual Shop may contain | HalOS-made + CC0 items only, each with licence and SHA-256. No fake products, no payments. |
| How to release | GitHub pre-release `v2.1.0-beta.1`. |
| Parallel agents | "As many as useful but not too many" — three worktree agents at once (an earlier run of five had burned the usage limit). |
| Hologram look | Asked for (a reference image of a glowing bust on a projector), then made an option: realistic is the default. |
| Full-body animation | Asked for mid-way: "screen animations of the avatar's full body, doing tasks, interesting and customizable". |

## 2. Audit first

[`docs/HALOS_21_AUDIT.md`](../HALOS_21_AUDIT.md) was written against the source, not the older docs. Findings that
shaped the work:

- Much already existed: reminders (`modules/automation`), workspaces save/restore (`modules/workspace`), window
  control, task tiling, model pull with progress, a Task Manager with basic GPU data. These were **extended, not
  rebuilt**.
- Missing entirely: avatar, Visual Shop, issue templates, public install/recovery/privacy docs.
- The biggest public-release blocker was (and is) that no v2 ISO had been installed on real hardware.

## 3. Build order

| # | Item | Who | Commits |
|---|---|---|---|
| 1 | NVIDIA detail via NVML (`nvidia-smi`, the source nvtop uses; nvtop itself is GPL-3 and was not vendored), per-process VRAM, tool `system.gpu`, deterministic answers to GPU questions | main session | ce28cc8 |
| 2 | Public docs: install, troubleshooting, recovery, privacy, known issues, contributing, issue templates | main session | 912c760, 5ea79bb |
| 3 | Avatar core + 2D widget + settings page | agent 1 (worktree) | c55d502, 91adf04, fb655cb |
| 4 | Visual Shop core, catalog, window, launcher | agent 2 (worktree) | bb50a19, ad84e2d, e480298 |
| 5 | System Overview, Home widgets, model install checks | agent 3 (worktree) | 020c21e, 51d27d5, 4ca5d2b |
| 6 | Merges, test fixes, shop avatars go through the avatar validator | main session | 218783c, d87ab58, 62ab0b9, fabd9ad, 8b099ac |
| 7 | Real 3D rendering (QtQuick3D `RuntimeLoader`), `PySide6_Addons` shipped on HalOS | main session | a99e675 |
| 8 | MPFB/Blender digital human with 67 ARKit + viseme face keys (superseded by the user's model, kept as tooling) | main session | 68684d3 |
| 9 | Hologram style (optional) | main session | 9863f82 |
| 10 | The user's VRoid SAINT as default; face mapped onto VRoid `Fcl_*` shapes | main session | b349e52 |
| 11 | Full-body animation per activity + task props + settings | main session | f4aa8cb |
| 12 | Release notes, status, README, this record | main session | d8dbced, 22041b2, … |

## 4. How the avatar works (for whoever touches it next)

```
assistant state / plan events ──► core/avatar AvatarStateMachine ──► AvatarState
                                                         │
          core/avatar/face.py FaceDriver (blink, visemes, expressions; ARKit names → VRoid Fcl_* via to_vroid)
          core/avatar/body.py BodyDriver (pose per activity → bone quaternions in the parent frame)
                                                         │  every 33 ms (500 ms with reduce motion)
ui/avatar/__init__.py AvatarView ──setProperty──► ui/avatar/avatar3d.qml
      faceWeights {name: w}      → QML morph index (each mesh's MorphTargets by name)
      bodyRot {bone: [w,x,y,z]}  → bone.rotation = q × rest   (rest copied at load)
      activity, taskTitle/Steps  → HUD layer: code screen, plan cards, dots, rings, badges, caption
```

- The default SAINT is `data/avatars/saint/saint.vrm` plus `qml/Saint.qml`, produced by Qt's `balsam`
  (`pyside6-balsam -o qml saint.glb`; the VRM is copied to a `.glb` name first). Re-run that when the model changes,
  and rename the output to `Saint.qml`.
- Imported models load through `RuntimeLoader` (no face/body animation) after `core/avatar/library.py` validates
  them as data: GLB header, version, declared length, 200 MB cap, buffers/images present, no paths outside the
  model's folder, VRM 0.x/1.0 meta.
- Pure logic (`face.py`, `body.py`, settings clamping) has tests that run without a GPU: `tests/test_avatar_*.py`.

## 5. Things that went wrong, and how they were found

| Symptom | Real cause | Fix |
|---|---|---|
| "3D not possible, no QtQuick3D" (agent report) | The agent ran the system Python; the project `.venv` has QtQuick3D. | Checked in `.venv`; on Windows the AssetUtils QML plugin also needs `Qt6Quick3DAssetUtils.dll` preloaded. |
| HalOS would still have no 3D | The HalOS runtime lock shipped only `PySide6_Essentials`. | `PySide6_Addons==6.12.0` added to `saint-runtime.lock` (bigger ISO). |
| 5→22 failing tests reported by agents | System Python (missing `segno`/`zeroconf`), CRLF checkouts in worktrees, and one real test bug: the fallback keyring made a separate store per method. | Use `.venv`; conftest shares one store. 2,401 → 2,413 pass, 0 fail. |
| Face never moved | MorphTargets collected once from a scene the view rebuilt; later, PySide wrappers for Qt Quick 3D internals reported "already deleted". | The QML scene owns a morph index; Python sends a plain `{name: weight}` map. |
| Hologram shader drew nothing | Unshaded custom materials have no `VAR_WORLD_*` / `UV0`; then a custom vertex shader silently dropped skinning and morphs. | Shaded custom material with emission only; Qt keeps skinning and morphs. |
| Inside of the mouth showed through the hologram | The depth pre-pass variant of the shader failed to compile. | Opaque above the bust line with normal depth writes; teeth/tongue hidden. |
| Body tumbling more every frame | QML stored the rest rotation as a live value-type reference to the bone's rotation, so each frame compounded. | Store a copy: `Qt.quaternion(r.scalar, r.x, r.y, r.z)`. |
| Clothes vanished in hologram mode | VRoid meshes have one material per part; all were replaced by one. | One hologram material per original material. |
| Blender MCP "cannot connect" | The add-on only starts with *Allow Online Access* on; also a second Blender launch saw a different (unredirected) app-data folder without MPFB. | Preference set and saved; MPFB reinstalled per profile. Recorded in memory. |
| Docs claimed a GRUB recovery entry and MOK password `halos` | Wrong: recovery is disabled in GRUB (there is a Recovery page), the password is `halo`, the EFI folder is `Halo`. | Checked against packaging; fixed (5ea79bb). |
| Build VM refused SSH | The key was typed before the console prompt appeared. | Screenshot the console, retype at the prompt. |

## 6. Verification, honestly

| Area | Evidence | Not verified |
|---|---|---|
| Unit/integration tests | 2,413 passed, 6 skipped, 0 failed on the Windows host (`.venv`) | Linux-only tests run on the build VM only |
| NVIDIA data | Live on the dev PC's RTX 5060 Ti; Ollama answer checked | AMD/Intel GPUs; HalOS's NVIDIA driver |
| Model install checks | Live with `smollm2:360m`, reported CUDA | Large model pulls |
| Avatar 2D/3D, face, body, props, hologram | Rendered and animated on Windows; screenshots in `docs/screenshots/` | Rendering on HalOS (Qt Quick 3D on the VM's / real GPU), real TTS lip sync, multi-monitor placement |
| Visual Shop | Tests + window screenshot on Windows | Plasma apply commands on HalOS |
| ISO | Builds #19–#22 pass validation (132–133 checks; size warning only); #19 booted to desktop with SAINT in UEFI and BIOS VMs | Install to real hardware, dual boot, Secure Boot on a PC |

## 7. Left for later

- Install on real hardware and run [TESTING_V2.md](../TESTING_V2.md).
- A LICENSE file (the Visual Shop's HalOS-made items say "same terms as HalOS").
- Spring-bone (hair/cloth) physics for VRM; phoneme-accurate lip sync; face/body animation for imported models
  (would need the `balsam` step at import time).
- More workspace presets (Development, Research, Diagnostics) on top of `modules/workspace`.
- ISO size (≈4.4 GB vs a 2.5 GB target).
