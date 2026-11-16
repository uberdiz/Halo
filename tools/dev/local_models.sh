#!/usr/bin/bash
# Build Evolve's local models (core/claude_agent.py LOCAL_DEFAULTS) on top of the pulled base models.
# Claude Code's system prompt + tools is ~20k tokens, so Ollama's small default context would truncate it.
#   evolve-coder   main agent (opus/sonnet aliases)   qwen3-coder:30b, 48k context
#   evolve-fast    sub-agents, quick jobs (haiku)     qwen3:8b,        32k context
#   evolve-vision  ui-checker screenshots             qwen3-vl:8b,     16k context
# Tune CODER_CTX down (32768) if replies get slow; up (65536) if long tasks lose track.
set -euo pipefail
CODER_CTX=${CODER_CTX:-49152}
mk() {  # name base ctx temp
  ollama pull "$2" >/dev/null 2>&1
  local mf; mf=$(mktemp)
  printf 'FROM %s\nPARAMETER num_ctx %s\nPARAMETER temperature %s\nPARAMETER top_p 0.8\nPARAMETER repeat_penalty 1.05\n' \
    "$2" "$3" "$4" > "$mf"
  ollama create "$1" -f "$mf" >/dev/null 2>&1; rm -f "$mf"
  echo "built $1 <- $2 (ctx $3)"
}
mk evolve-coder  qwen3-coder:30b "$CODER_CTX" 0.3
mk evolve-fast   qwen3:8b        32768        0.3
mk evolve-vision qwen3-vl:8b     16384        0.2
