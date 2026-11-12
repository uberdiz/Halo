---
name: halos-ai-shell
description: Use when working on SAINT agent mode, the OS action registry, trust levels, visual multi-step plans, parallel task tiling, background (focus-free) automation, Claude Code headless integration, AIDE integration, or camera presence.
---
# Rules
- The LLM picks actions; a typed action registry (`core/actions/`) validates and executes them. The GUI and SAINT call the same registry.
- Every action declares its category, risk (safe/risky/destructive), undo function, and preview text. Trust levels are per category; risky actions always preview first.
- Claude Code backend: `claude -p --output-format stream-json`, using the user's subscription and no API key. Stream steps to the UI. Cache and summarise context so earlier work isn't re-sent.
- Parallel tasks get their own windows tiled with KWin scripting. Input automation runs in a headless or nested session, never on the user's focused seat.
- Camera presence is opt-in and processes frames locally only, with a visible indicator and one switch to turn it off.
- AIDE 2.0 lives at `C:\SAINTxAIDE\AIDEv2.0`. It's VSCodium 1.107 plus `extensions/aide-core`. Build it for linux-x64 and ship it as the HalOS "Code" app; share the agent backend, history and skills with SAINT. Reuse its code and don't reimplement it. Record integration decisions in DECISIONS.md.
- Tests: unit-test the registry and trust gating with mocks; run the runtime check in the VM recipe.
