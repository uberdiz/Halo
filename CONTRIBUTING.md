# Contributing to HalOS

- **Bugs / ideas:** use the issue templates. Include hardware, HalOS version (`cat /etc/halo/version`) and logs.
- **Code:** Python 3.12 + PySide6. Run `python -m pytest -q tests` before a PR. Keep deterministic actions in code; the LLM only picks intent. New OS actions go in `core/actions/` with a trust level.
- **Visual packs** (wallpapers, themes, avatars): a folder with `manifest.json` (id, name, category, creator, license, version, sha256 per file). Only images, video, `.vrm/.glb`, JSON, SVG and colour schemes — no scripts. License must allow redistribution.
- **Docs:** don't mark a feature working unless you ran it; say exactly what was tested.
