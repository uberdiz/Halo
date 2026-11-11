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
- AIDE: find it in `../AIDE` or on GitHub under uberdiz and reuse its code; don't reimplement it. Record what was merged in DECISIONS.md.
- Tests: unit-test the registry and trust gating with mocks; run the runtime check in the VM recipe.
