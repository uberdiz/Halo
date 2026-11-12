#!/bin/bash
# Export what HalOS's "Bring everything" wizard brings, from a Mac, to a USB drive.
#
#   bash export_for_halos.sh /Volumes/USB [--no-files]
#
# Reads only: nothing on the Mac is changed. Writes /Volumes/USB/HalOS-Export/, laid out like a Windows profile
# (Users/<you>/AppData/...), because that's what HalOS's wizard reads; each Mac location is copied to the place
# the same thing has on Windows (Chrome's bookmarks, Firefox's places.sqlite, fonts, ...). Close browsers first.
# Apple Passwords / iCloud Keychain: export them yourself (Passwords app > File > Export All Passwords) to a CSV,
# and import that CSV into your browser on HalOS. This script never reads passwords.
set -u
dest="${1:?usage: export_for_halos.sh <drive> [--no-files]}"
nofiles="${2:-}"
user="$(id -un)"
out="$dest/HalOS-Export"
me="$out/Users/$user"
AS="$HOME/Library/Application Support"
parts=()

copy() {   # copy <from> <to> <what>
  [ -e "$1" ] || return 0
  echo "  $3"
  mkdir -p "$(dirname "$2")"
  if [ -d "$1" ]; then rsync -a --exclude '.credentials.json' --exclude 'credentials.json' "$1/" "$2/"
  else cp -p "$1" "$2"; fi || echo "  (some of '$3' couldn't be copied)"
  parts+=("$3")
}

echo "Export for HalOS: $user -> $out"
mkdir -p "$out" || { echo "Can't write to $dest"; exit 1; }
if [ "$nofiles" != "--no-files" ]; then
  for f in Documents Desktop Pictures Music Movies Downloads; do
    to="$f"; [ "$f" = Movies ] && to=Videos
    copy "$HOME/$f" "$me/$to" "$f"
  done
fi
for p in "$AS/Google/Chrome"/Default "$AS/Google/Chrome"/Profile\ *; do
  [ -d "$p" ] && copy "$p/Bookmarks" "$me/AppData/Local/Google/Chrome/User Data/$(basename "$p")/Bookmarks" "Chrome bookmarks"
done
for p in "$AS/Microsoft Edge"/Default "$AS/Microsoft Edge"/Profile\ *; do
  [ -d "$p" ] && copy "$p/Bookmarks" "$me/AppData/Local/Microsoft/Edge/User Data/$(basename "$p")/Bookmarks" "Edge bookmarks"
done
for p in "$AS/BraveSoftware/Brave-Browser"/Default "$AS/BraveSoftware/Brave-Browser"/Profile\ *; do
  [ -d "$p" ] && copy "$p/Bookmarks" "$me/AppData/Local/BraveSoftware/Brave-Browser/User Data/$(basename "$p")/Bookmarks" "Brave bookmarks"
done
for p in "$AS/Firefox/Profiles"/*; do
  [ -d "$p" ] && copy "$p/places.sqlite" "$me/AppData/Roaming/Mozilla/Firefox/Profiles/$(basename "$p")/places.sqlite" "Firefox bookmarks"
done
copy "$HOME/.claude" "$me/.claude" "Claude Code history, settings and skills"
copy "$AS/Claude/claude_desktop_config.json" "$me/AppData/Roaming/Claude/claude_desktop_config.json" "Claude app MCP servers"
copy "$AS/Code/User" "$me/AppData/Roaming/Code/User" "VS Code settings"
copy "$HOME/.vscode/extensions" "$me/.vscode/extensions" "VS Code extensions"
copy "$HOME/Library/Fonts" "$me/AppData/Local/Microsoft/Windows/Fonts" "Fonts you installed"
copy "$HOME/.ollama/models" "$me/.ollama/models" "AI models (Ollama)"
wall="$(osascript -e 'tell application "System Events" to get picture of current desktop' 2>/dev/null)"
[ -n "$wall" ] && copy "$wall" "$me/AppData/Roaming/Microsoft/Windows/Themes/TranscodedWallpaper" "Wallpaper"

echo "  Installed apps list"
{
  echo "["
  first=1
  for app in /Applications/*.app "$HOME/Applications"/*.app; do
    [ -d "$app" ] || continue
    name="$(basename "$app" .app | sed 's/"/\\"/g')"
    [ $first = 1 ] || echo ","
    printf '  {"name": "%s", "publisher": ""}' "$name"
    first=0
  done
  echo; echo "]"
} > "$out/apps.json"
parts+=("Installed apps list")

{
  printf '{\n  "version": 1, "user": "%s", "computer": "%s", "created": "%s", "macos": "%s",\n  "parts": [' \
    "$user" "$(scutil --get ComputerName 2>/dev/null || hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(sw_vers -productVersion 2>/dev/null)"
  sep=""; for p in "${parts[@]}"; do printf '%s"%s"' "$sep" "$p"; sep=", "; done
  printf ']\n}\n'
} > "$out/HALOS-EXPORT.json"
echo
echo "Done. In HalOS, open Settings > Migrate from Windows; it finds $out on the drive."
