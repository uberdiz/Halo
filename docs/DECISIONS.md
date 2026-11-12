# HalOS decisions

One line each: what was chosen and why.

- 2026-11-10 — Wave order follows the master prompt (bugs, action registry, installer core first): the user asked for the most efficient route and everything else builds on these.
- 2026-11-10 — Testing: VirtualBox VMs plus the Windows SAINT app on the dev PC; real disks and boot entries are never touched (user answer).
- 2026-11-10 — AIDE 2.0 gets its own public GitHub repo under uberdiz so the HalOS build can fetch it without credentials (user answer).
- 2026-11-10 — One PR per workstream, merged to main by the agent once tests and reviews pass; tag v2.0.0 at the end (user answer).
- 2026-11-10 — Parallel subagents don't edit HALOS_STATUS.md, DECISIONS.md or PROGRESS.md; the orchestrator records their results, to avoid merge conflicts.
- 2026-11-10 — The whole process is documented on GitHub in docs/process/ with real screenshots, one page per wave (user request).
- 2026-11-10 — uberdiz/AIDE already exists (AIDE 1.x, public), so AIDE 2.0 is pushed there as the new branch aide-2.0 instead of creating a second repo or overwriting main.
- 2026-11-11 — No ISO build or VM test until all waves are coded (user decision); Linux-only behaviour stays marked as needing a VM check until then.
