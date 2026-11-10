# Halo OS test results

Only tests that actually ran are listed. "Not run" is said explicitly.

## 2026-11-08 — build #12 ISO (commit 1b78dc6): Windows stays the default

| Test | Result |
|---|---|
| ISO build (warm download cache) | built in 21 min, first attempt; **ALL CHECKS PASSED**; 4.30 GB; SHA-256 `93be857e…ec47c22`, copy verified |
| Boot test UEFI | **PASS** — DESKTOP-OK 144 s, SAINT-OK 214 s |
| Live session | SAINT widget shows "Microphone off" (was "SAINT isn't running") |
| Free-space install with a "Windows Boot Manager" firmware entry present (made with efibootmgr on a PC-like layout) | chooser says Windows stays the default; install done; afterwards BootOrder `0003 Windows Boot Manager, 0004 HalOS, …`; sda1/sda2 untouched, new HALOS_EFI + HalOS partitions |
| `restart_into_halos.ps1` | parse-checked only; not run (needs the installed HalOS entry on the real PC) |
| HALOLIVE flash on the real PC | not done: the Administrator prompt was cancelled |

## 2026-11-07 — build #11 ISO (commit 287eb18) and a clean install from it, VirtualBox on the Windows host

| Test | Result |
|---|---|
| ISO build (VirtualBox build VM, `packaging/windows-host/vbox-build`) | built on the first attempt in 158 min (package cache was empty); 4.30 GB; `airootfs.sfs` 4.13 GB (FAT32 limit 4.29 GB) |
| `validate_iso.sh` | **ALL CHECKS PASSED** |
| Copy to Windows (`scp` → `.part`, SHA-256) | OK — `b6285a92…6421c` |
| Boot test UEFI / legacy BIOS | **PASS / PASS** — DESKTOP-OK 144 s, SAINT-OK 215 / 214 s |
| Install chooser (unpatched image, disk laid out like the PC: 2 GB "Windows", 6 GB HALOLIVE, 32 GB free) | offers the 34 GB free space, lists both partitions as untouched; icon shown; text wraps |
| Calamares free-space install | all jobs done, "All done."; result: sda1 Windows and sda2 HALOLIVE untouched, new sda3 HALOS_EFI 512 MB + sda4 Btrfs 31.5 GB; firmware entry "HalOS" → `\EFI\Halo\shimx64.efi` on sda3 |
| First boot from disk (ISO detached) | straight to the greeter — no GRUB "sparse file" error and no "press any key"; greeter shows the account made in the installer; its password logs in |
| First login | one "Welcome to HalOS" window; window icons have no green pixels (pixel scan of the title bar) |
| Found and fixed (fa6daa0, ae9804f) | 1) SAINT widget said "SAINT isn't running" on a PC without a microphone (SAINT was running; its offline state means "Microphone off") — the state socket now sends SAINT's label, verified in the VM. 2) the live session started downloading llama3.1:8b into RAM on every boot — automatic pull is now off in the live session. 3) only one pacman mirror was configured; when it stalled, every sync failed on the installed system — two fallback mirrors added |
| Found and fixed (9d1e529) | `prepare_disk_boot.ps1 -Refresh` could never find HALOLIVE on the real PC: Windows shows no label for an ESP-typed partition. Detection by type/size/position, label verified after mounting and before formatting (dry-run on the PC: exactly 1 candidate, partition 3, 6 GB) |
| Not verified in the VM | model answer and Store install on the installed system (the VM's network timed out on every mirror this time; both worked in the earlier install test from the patched build-10 image: llama3.2:1b + whisper tiny.en downloaded, kcalc installed from the Store), animations/Supernova (no GPU in VirtualBox), CUDA/NVIDIA, real Windows/NTFS/BitLocker migration |

## 2026-11-05 — build #9 ISO (branch `halo/roadmap-2026-11`, commit a5df39c), built in a VirtualBox Arch VM on the Windows host

| Test | Result |
|---|---|
| ISO build (`build_iso.sh --mode test` in an arch-chroot on the VM's virtual disk; 12 vCPU, 16 GB) | built in ~45 min incl. Calamares, paru-bin, shim-signed-bin, claude-code 2.1.318 from the AUR; `Halo-x86_64.iso` **4.28 GB** (target < 3 GB: missed — nvidia-open + the bundled Python/voice runtime) |
| `validate_iso.sh` | **ALL CHECKS PASSED** (Halo OS names, NVIDIA packages + GPU unit, multilib, Ollama config, Spotify/VS Code, `claude --version`, Kokoro, Alt+`) |
| Copy to Windows (`scp` → `.part`, SHA-256 compared) | OK — `7da2d11dad2858ea506db6226aa6122fef1d4db0ada8af1b0c9ceb017375d9b7` |
| Boot test UEFI (`packaging/windows-host/boot_test.ps1`) | **PASS** — BOOT-OK + DESKTOP-OK (Wayland, liveuser) at 134 s, SAINT-OK at 214 s |
| Boot test legacy BIOS | **PASS** — same markers, 214 s |
| Lean targets (`SAINTOS-METRIC`, live session in VirtualBox) | desktop 127.7 s (target < 20 s), idle RAM 2429 MB (target < 1.5 GB): **both missed** in the VM; to measure on hardware |
| Screenshot check | "Welcome to Halo OS" page shown; Halo/Firefox/Dolphin/Konsole/SAINT/VS Code pins present. Found and fixed afterwards: welcome text still said "small default model"; Spotify placeholder pin had no icon (`multimedia-audio-player` not in the theme → `audio-x-generic`). **Open:** SAINT's status bar shows "Error" in the live VM (cause not captured — VM deleted after the test; check the SAINT log on the next boot) |
| Not run | install to disk with Calamares (incl. a 100 MB ESP), Secure Boot/MOK, Ollama pull + inference, Store/VM install matrix, Evolve, remote host on Plasma |

## 2026-11-04 — health model, model pull progress, dependency manager (Windows dev host)

| Test | Result |
|---|---|
| `tests/test_health.py` (24, new) + `tests/test_deps.py` (13, new) | passed — every state per subsystem with mocked commands/files, timeouts, pull-progress summing, default-model rule, service/script/config consistency, confirm-before-install, pkexec for admin steps |
| Touched areas: `test_halos_repairs`, `test_saintos_center`, `test_log_regressions`, `test_saintos_apps`, `test_evolve`, `test_ui_smoke`, `test_v04_ui`, `test_sysinfo` | 155 passed |
| Full suite | 1699 passed, 6 skipped, 1 failed: `test_session_0930b::test_one_day_or_a_rare_pair_is_not_a_habit` (depends on the time of day — run at 22:23 −05:00, i.e. after UTC midnight; it doesn't touch the changed files). The 4 known failures passed in this run |
| `python -m core.health --full` on this PC (real) | Ollama `llama3.1:latest` answered in 9.4 s; Kokoro 2.6 s of speech in 1.75 s; Whisper transcribed the Kokoro clip exactly; network, GPU (RTX 5060 Ti, nvidia 610.88), storage Working; Flatpak/pacman Not tested (Windows) |
| `bash -n` on `usr/libexec/saintos/ollama-model` | syntax OK; **not run** on Arch — the auto model choice, the service and SAINT following the pull need the VM |

## 2026-11-04 — Priority 2: Store metadata, filters, installation assistant (Windows dev host)

| Test | Result |
|---|---|
| `tests/test_install_assistant.py` (new, 29): file kinds and refusals, GitHub release asset choice + digest / SHA256SUMS, checksum formats, Flathub links/ids, local file hashing, plans per kind (pacman, AppImage + fuse2, .flatpakref installs exactly what was read, .deb via debtap, Wine with the Linux version preferred, anti-cheat refused), no-checksum → high risk + unverified download, launch check (process appears / exits with error / still running), desktop-entry and Wine-menu verification, history merge/events, Store entries share identities, uninstall rebuilt from validated ids (unsafe ones refused), repair reinstalls, AppImage/Wine helpers (no desktop-entry injection, only SAINT prefixes removed), Store compatibility/type/installed filters, Flathub categories, Wine name blocks and unverified fetch | passed (all fetches, commands and process lists mocked) |
| `tests/test_store_art.py` (+2): multi-screenshot/licence/homepage parsing, local AppStream XML + `appstreamcli dump` (mocked), offline / not-on-Flathub fallback | passed |
| `tests/test_store_ui_assistant.py` (new, offscreen Qt): search filters (compat / installed), details view of a won't-work app, assistant plan → queue → failed install recorded with its reason → history list | passed |
| `tests/test_store_and_winapps.py`, `test_saintos_apps.py`, `test_ui_smoke.py`, `test_v04_ui.py`, `test_phone_and_app_tools.py` | passed (77 with the new files) |
| Full suite | 1695 passed, 5 skipped, 1 failed: `test_session_0930b::test_one_day_or_a_rare_pair_is_not_a_habit` (agent habit detection, untouched by this change; fails on its own too, looks date-dependent). The 4 usual failures passed this run |

### Installation assistant VM matrix — Not run (needs the Halo VM)

For each row: Store → "From a file or link" (or the Store search for the Store rows), check the plan (kind, source,
checksum, risk, steps), Install, keep "Open it afterwards" on → the app window opens and the history says
"installed" → "Installed by SAINT" → Repair (reinstalls) → Uninstall (gone from the menu and `pacman -Q`/`flatpak list`).
Run once in the live session and once installed.

| # | Source | Input | Expect | Result |
|---|---|---|---|---|
| 1 | Flathub (Store) | search "Heroic" → Heroic Games Launcher | installs `com.heroicgameslauncher.hgl`, launches; live session no "No space left" | Not run |
| 2 | Flathub (assistant) | `https://flathub.org/apps/com.heroicgameslauncher.hgl` | risk low, Flathub signature | Not run |
| 3 | GitHub release | `https://github.com/Heroic-Games-Launcher/HeroicGamesLauncher` | picks the `.pkg.tar.zst` (else AppImage), GitHub digest shown, pacman -U | Not run |
| 4 | Arch repos (Store) | search "kate" | native, details show KDE / licence / screenshots from local AppStream | Not run |
| 5 | AUR (Store) | search "visual-studio-code-bin" | AUR confirmation with votes, paru builds as the user | Not run |
| 6 | .flatpakref | a `.flatpakref` link from flathub.org | `flatpak install --from`, risk low | Not run |
| 7 | AppImage | an AppImage release (e.g. Obsidian) | fuse2 step if missing, `~/Applications`, start-menu entry, launches | Not run |
| 8 | .pkg.tar.zst file | a downloaded package file | risk high (outside repos), pacman -U, desktop entry found | Not run |
| 9 | .deb | a `.deb` (e.g. a Debian-only tool) | Store version offered first if any; debtap installs from AUR, converts, pacman -U | Not run |
| 10 | Windows .exe | Notepad++ installer `.exe` | Wine installed once, installer window, menu entry under `wine/`, launches | Not run |
| 11 | Won't work | a Valorant installer | refused before anything runs (kernel anti-cheat) | Not run |
| 12 | Filters | search "steam" | Native / Flatpak / Won't work / Installed filters each show the right subset | Not run |

## 2026-11-02 — Windows dev host, `halo/arch-rebase`

| Test | Result |
|---|---|
| Full pytest suite (`.venv`, Windows 11) | 1579 passed, 5 skipped, **4 failed** — the same 4 that failed before this session (`test_history_stats::test_daily_summary_survives_trimming`, `test_tts_fallback` ×2, `test_v04_selftest::test_quick_checks_pass_from_source`); not caused by these changes, still open |
| `tests/test_halos_repairs.py` (new, 17 tests) | passed — failure reasons, run_plan per-app errors, Linux filesystem dedupe, unallocated space, Halo edge geometry, image defaults |
| `tests/test_ui_smoke.py`, `tests/test_v04_ui.py` (offscreen Qt) | passed |
| Halo frame render (offscreen Qt, 800×800) | centre pixel alpha 0, top edge alpha 128 — paints edges only |
| Kokoro model download from upstream | 2 files, SHA-256 recorded in the PKGBUILD |

## 2026-11-02 — build 7 features (Windows dev host)

| Test | Result |
|---|---|
| `tests/test_sysinfo.py` (9) + new packaging tests in `test_halos_repairs.py` | passed |
| Full suite | 1596 passed, 5 skipped, same 4 pre-existing failures |
| Task Manager offscreen on this PC's real data | 159/348 processes listed, CPU/memory/disk/network graphs, RTX A1000 found via nvidia-smi (42 °C), dark and light palettes rendered |
| Halo + Music widget QML | parses (`qmlformat`); **not run** — needs Plasma (VM) |
| Halo Dark/Light colour schemes | generated from `ui/theme.py`; test checks the shipped files match; **not seen in Plasma yet** |

## Halo VM / ISO

| Test | Result |
|---|---|
| Build #8 ISO (commit 22b5052, includes Workstream B) | built and validated (ALL CHECKS PASSED, incl. Halo Remote host installed and off, GStreamer webrtc/pipewire/x264/vpx plugins); Kokoro synthesis in the package build 6.3 s for 2.6 s of speech; copied to `dist/halo/build8/` over SSH, SHA-256 OK; **not boot-tested** |
| Build #7 ISO | built and validated (ALL CHECKS PASSED: Task Manager shortcut, Halo/Music widgets, Halo Dark/Light, Alt+`, Kokoro); first copy to Windows failed mid-way (`Invalid cross-device link`, file opened on the Windows side) and left a truncated ISO — the cause of the failed USB write; recopied over SSH via a `.part` file |
| Merge of Workstream B into `halo/arch-rebase` | 1647 Python tests pass (same 4 old failures), 19 browser-client tests pass; pushed to `origin/halo/arch-rebase` |
| Build #6 ISO | built and validated (ALL CHECKS PASSED, incl. Secure Boot step and Kokoro in image); copied to `dist/halo/build6/`, SHA-256 OK; **not boot-tested** (skipped at user's request, build #7 next) |
| Build #6 `saint` package: Kokoro synthesis from the packaged files | **passed** — "2.6s of speech in 14.51s" (first run in a VM container, includes ONNX warm-up; speed on real hardware still to measure) |

| Test | Result |
|---|---|
| ISO build from this branch | see below once the build finishes |
| UEFI boot to desktop | Not run on this branch (last Halo ISO, 2026-10-30, stopped at systemd-firstboot) |
| BIOS boot | Not run |
| Kokoro speaks / Whisper transcribes on Halo | Not run |
| Ollama service + inference | Not run |
| Heroic install from Flathub (live + installed) | Not run |
| Alt+` toggles overlay, Halo at screen edges, notices at bottom | Not run (needs a Wayland session) |

## Not testable on this host
- Swift / iOS (needs macOS — GitHub Actions `mobile-ios.yml`)
- Physical hardware: Secure Boot/MOK, dual boot with Windows + BitLocker, real GPUs

## Workstream B — Halo Remote (branch `saint-mobile`, 2026-11-02, Windows 11 dev host)

What ran, on this Windows machine (Python 3.13 `.venv` + aiohttp 3.11.18, Node 24.20, the Claude app's Chromium):

| Test | Result |
|---|---|
| `pytest tests/test_remote_protocol.py` — schemas, canonical JSON, MACs vs `remote_vectors.json`, tampered/forged/reflected/stale/replayed refused, relay proof, pairing MAC, **unpaired, not-allowed and revoked keys refused** against the real Link `PeerStore` | 19 passed |
| `pytest tests/test_relay.py` — relay on localhost, real WebSockets: login, wrong-key login refused, presence, signed routing untouched, unauthorised device gets no presence/route, revocation drops the route, pairing, pair rate limit, no client↔client, TURN REST credentials | 8 passed |
| `pytest tests/test_remote_host.py` — ask/allow/deny/busy/replace, timeouts, revoked mid-session, answer/ICE only for the live session, input → portal calls with stuck-key release, keysyms, file receive (size/hash/name), one-time pairing codes, device key never created, pipeline + webrtcbin ICE URIs, unit file | 25 passed |
| `node --test "web/remote/test/*.test.mjs"` — JS protocol vs the same vectors (byte-identical canonical JSON and MACs), input/gesture logic, **browser client against the real relay** (pairing, presence, signed request/accept/offer/answer, ICE, forged end ignored, revoke) | 19 passed |
| Browser client, real WebRTC, Chromium: relay serving `web/remote`, `test/fake_host.html` as the PC (canvas video + data channels) | pairing by link (code removed from the URL), video 640×360 @ ~30 fps, click/right-click/scroll with letterbox-correct coordinates, keys as evdev codes, Ctrl+A (found and fixed: modifiers now synced from event flags), PC→client clipboard, 300 KB file with SHA-256 confirmed, stats, Disconnect → signed `session.end`, reconnect after reload, phone-width layout |
| Full `pytest` on `saint-mobile` | 1631 passed, 4 failed — the same tests fail on the base commit 1452e3a (`test_tts_fallback` ×2, `test_v04_selftest`, and a Windows "Access is denied" race in `test_history_stats`); none touch Halo Remote |

Second round (same day) — the desktop app as a client, relay address over Link, codec choice:

| Test | Result |
|---|---|
| `pytest tests/test_remote_desktop_client.py` — relay address from the PC over Link and remembered for when it's offline, PC claiming another account refused, "not set up" message, loopback-only static server (JS MIME, no listing, no `..`) | 5 passed |
| `pytest tests/test_remote_host.py` (+2) — codec from `want.codecs` (H.264 preferred, VP8 fallback, VP8 pipeline), `remote.info` answer and refusal for friends / denied devices | 27 passed |
| `node --test` (+1) — an identity that lends `sharedSecret` (the desktop app) signs exactly like one holding the key | 20 passed |
| **SAINT desktop window, real run on Windows** (PySide6 6.12 Qt WebEngine) ↔ local relay ↔ `test/fake_host.html` in Chromium | connected, live video 640×360 @ 30 fps "direct"; one click and one key arrived at the host; the client offered `codecs: [H264, VP8]` (this Qt WebEngine build does decode H.264). Found and fixed: the window pushed the computer's existing clipboard on connect — it now only sends what is copied while connected |
| Browser page after moving its viewer into `viewer.js` | pairing link + connect + live video + stats still work |
| GitHub Actions `Halo Remote` (ubuntu: pytest, node, relay Docker image build) on 40f2409 | success |
| Full `pytest` | 1638 passed, the same 4 pre-existing failures |

Third round (2026-11-04, Windows 11 dev host; Python 3.12 `.venv`, aiohttp 3.11.18 from a scratch `--target` dir
because the venv has no pip yet; Node 24) — multi-monitor, reconnect policy, relay self-hosting:

| Test | Result |
|---|---|
| `pytest tests/test_remote_protocol.py tests/test_relay.py tests/test_remote_host.py tests/test_remote_desktop_client.py tests/test_mobile_shared.py` — +3 new: screens from the portal answer (sorted, malformed skipped), `monitors`/`monitor.select` schemas, pointer follows the selected screen, held button released / held key kept on switch, input-selector pipeline with one encoder, relay systemd unit (paths, env names that exist in `relay.py`) | 62 passed |
| `node --test "web/remote/test/*.test.mjs"` (with `HALO_PYTHON` → relay integration runs) — +2 new: `shouldRetry`/`retryDelayMs`, `screenChoices` | 22 passed |
| Browser client, real WebRTC in the Claude app's Chromium: local relay on 127.0.0.1:8765, `test/fake_host.html` as the PC with two pretend screens | paired by link, connected (video 640 px wide, stats "direct"); picker shows "Screen 1 (1920×1080)" / "Screen 2 (2560×1440)"; choosing Screen 2 sent one `monitor.select {index: 1}` and the host switched; `dropConnection()` on the host → client showed "Connection unstable…" → "The connection dropped. Reconnecting (1/5)…" → video back, and the client re-selected Screen 2 by itself (the fresh host session started on Screen 1) |
| Swift (`SaintCore/Remote/RemoteScreens.swift` + 2 XCTests, `SaintMobile/Remote` model/view changes) | **not compiled** — no Swift toolchain here; checked by reading only |
| `media.py` changes (portal `multiple: true`, input-selector switch, relay keepalive) | `py_compile` only; **not run** (needs Plasma Wayland) |

Not run (and why):

- **Host media path** (`modules/remote_desktop/media.py`: xdg-desktop-portal RemoteDesktop/ScreenCast, PipeWire, GStreamer
  `webrtcbin`, libsoup, wl-clipboard, kdialog): implemented, **untested** — needs a Plasma Wayland session (Halo VM). Next:
  enable it on the VM, connect from the browser, then from a phone on cellular through TURN.
- **Swift** (`SaintCore/Remote` + XCTests, `SaintMobile/Remote` with WebRTC): written, **not compiled** — no Swift toolchain
  here. CI (`mobile-ios.yml`: `swift test` + unsigned `.ipa`) will be the first compile.
- **Relay Docker image / compose with coturn and Caddy**: not built (no Docker here); `.github/workflows/halo-remote.yml`
  builds the image.
- **Safari on iPad/iPhone, Chrome on a Chromebook, real touch**: not tried (no devices); gestures are unit-tested only.
- **TURN across networks** (phone on cellular ↔ PC behind NAT): needs a VPS running the relay + coturn.

## Build 13 — Secure Boot in VirtualBox (2026-11-09, commit 0f6fe70)

Real Secure Boot (Microsoft keys enrolled in the VM's NVRAM), `dist/halo/build13/Halo-x86_64.iso`, SHA-256 `5008d375…0a9821`.

| Check | Result |
|---|---|
| Build 12 install, only `HALO-MOK.cer` enrolled | reproduces 0x1A from the real PC |
| Build 12, MokManager's 10-second prompt missed | queued key lost, only Enroll key from disk left |
| Recovery from live: `mokutil --import` of the installed key | queues the right key |
| Build 13 live boot, Secure Boot on | PASS |
| Build 13 install with Secure Boot on | MokNew and MokTimeout set; prompt waits |
| Enroll MOK, password `halo`, reboot | PASS: GRUB, kernel, login, desktop; `SecureBoot enabled`, lockdown none |
| Boot order after install | Windows first, then HalOS |
| Not tested | NVIDIA driver under Secure Boot (no GPU in the VM); the real PC's firmware |

## Build 15 — boot with the live key, one-click repair (2026-11-10)

Build 14 (commit a8e32ac) with the root image repacked offline (internet down) to add 9de60ee (repair prompt on the
session's display) and f86be3e (live mirror list); same 258,012 entries. `dist/halo/build15`, SHA-256 `cb0038cd…7e9ab`.
Secure Boot VM with only HALO-MOK.cer enrolled, like the real PC:

| Check | Result |
|---|---|
| Build 14 fresh install, first start | PASS: GRUB, kernel, login; no key screen |
| Install signed with its own key (as from build 12) | 0x1A / "bad shim loader signature" |
| Build 15 live: repair prompt at login, Yes | PASS: "Fixed", then GRUB, kernel and login with Secure Boot on |
| Kernel-update guard with the PC key not approved | stops, queues the key, explains |
| HALOLIVE flashed with build 15 | every file matches the ISO |
| Not tested | the real PC's firmware; the prompt with a mouse (VM used keyboard focus) |

## Build 16 — GRUB SBAT generation (2026-11-10)

Real PC after the build 15 repair: still 0x1A. Cause: Windows Update wrote SbatLevel `sbat,1,2025051000` (shim,4,
grub,5, …) into the firmware (registry `HKLM\SYSTEM\CurrentControlSet\Control\SecureBoot\SBAT`); our GRUB said grub,4.
The VM had shim's default level (grub,4), which is why it passed. Build 16 = build 15 with GRUB rebuilt at grub,6
(GRUB 2.16's own build-time level), repacked offline. SHA-256 `6cf140ba…821c3c`.

| Check (VM with the PC's exact SbatLevel) | Result |
|---|---|
| Build 15-repaired install | 0x1A, as on the PC |
| Build 16 live, repair prompt, Yes | PASS: GRUB, kernel, desktop |
| HALOLIVE flashed with build 16 | every file matches the ISO |
