#!/usr/bin/env python3
"""Ask the local vision model about the screen or an image: the ui-checker agent's eyes.

    python3 tools/dev/look.py "Is the new Backend dropdown visible and aligned with Model?"
    python3 tools/dev/look.py --image shot.png "..."      # an existing screenshot
    python3 tools/dev/look.py --window "..."              # only the active window

Prints the model's answer; exits 1 if the model isn't reachable. Model: $SAINT_VISION_MODEL (evolve-vision).
"""
import argparse, base64, json, os, subprocess, sys, tempfile, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("question")
ap.add_argument("--image")
ap.add_argument("--window", action="store_true")
a = ap.parse_args()
img = a.image
if not img:
    img = tempfile.mktemp(suffix=".png")
    subprocess.run(["spectacle", "-b", "-n", "-a" if a.window else "-f", "-o", img], check=True, timeout=20)
base = os.environ.get("SAINT_OLLAMA", "http://127.0.0.1:11434")
body = {"model": os.environ.get("SAINT_VISION_MODEL", "evolve-vision"), "stream": False,
        "messages": [{"role": "system", "content": "You check desktop UI screenshots for a developer. Answer the "
                      "question concretely: what you see, anything misaligned, cut off, overlapping, unreadable or "
                      "missing. End with a line 'VERDICT: OK' or 'VERDICT: PROBLEM: <one line>'."},
                     {"role": "user", "content": a.question,
                      "images": [base64.b64encode(open(img, "rb").read()).decode()]}]}
try:
    req = urllib.request.Request(base + "/api/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    print(json.load(urllib.request.urlopen(req, timeout=300))["message"]["content"].strip())
    print(f"(screenshot: {img})")
except Exception as e:
    print(f"vision model unreachable at {base}: {e}", file=sys.stderr)
    sys.exit(1)
