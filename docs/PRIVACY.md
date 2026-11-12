# Privacy and security

- **Local by default.** Speech-to-text (Whisper), text-to-speech (Kokoro), wake word and the default AI model (Ollama) run on your PC. Hardware and system monitoring never leave the machine.
- **Cloud only when you choose it.** Agent mode uses Claude Code with *your* subscription sign-in. What you ask in agent mode is sent to Anthropic. No API key is stored by HalOS; other keys go to the system secret store, never `config.json`.
- **Permissions.** Every OS action has a trust level. Read-only diagnostics run freely; killing processes, changing services, drivers, partitions, boot or firewall always asks first. See *Settings → What SAINT may do* and [ACTIONS.md](ACTIONS.md). Actions are logged and most can be undone.
- **Imported avatars and Visual Shop packs** are treated as untrusted data: file-type allowlist, size limits, SHA256 checks, no scripts are executed.
- **Remote access** (SAINT Link, remote desktop) is off until you pair a device; SAINT Link uses Noise-protocol encryption with per-device keys.
- **Camera presence** is opt-in and processed locally.
- No telemetry is sent anywhere.
