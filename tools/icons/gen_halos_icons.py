"""
tools/icons/gen_halos_icons.py

Writes the HalOS icon theme (packaging/linux/rootfs/usr/share/icons/HalOS): one consistent style for every icon
HalOS itself draws, places, folders, file types, devices, system apps and actions. A soft rounded tile (or folder
shape) in a two-tone gradient per category, with a white monoline glyph on a 24 px grid. App makers' own logos
(Firefox, Steam, Spotify...) are not redrawn: anything not here falls through to Breeze (Inherits=).

    python tools/icons/gen_halos_icons.py
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "packaging/linux/rootfs/usr/share/icons/HalOS"

# 24 px monoline glyphs (drawn here for HalOS; stroke 2, round caps)
G = {
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z"/>',
    "doc": '<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M9 13h7M9 17h5"/>',
    "down": '<path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/>',
    "image": '<rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="10" r="2"/><path d="m21 16-5-5-8 8"/>',
    "music": '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "video": '<rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/>',
    "desktop": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "trash": '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/>',
    "trashfull": '<path d="M4 7h16"/><path d="M9 7V4h6v3"/><path d="M6 7l1 13h10l1-13"/><path d="M10 11v6M14 11v6"/>',
    "drive": '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M5 13 7.5 5h9L19 13"/><path d="M7 16.5h.01M11 16.5h.01"/>',
    "usb": '<path d="M12 3v14"/><path d="m9 6 3-3 3 3"/><path d="M8 11v2l4 3 4-3v-3"/><circle cx="12" cy="19" r="2"/>',
    "network": '<circle cx="12" cy="5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 7v5M5 17l7-5 7 5"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3M12 15h5"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18"/><path d="M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m13 7 4 4"/>',
    "code": '<path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    "game": '<rect x="2" y="7" width="20" height="11" rx="5"/><path d="M7 11v3M5.5 12.5h3"/><circle cx="16" cy="11.5" r="1"/><circle cx="18" cy="14" r="1"/>',
    "package": '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5 12 12l8-4.5M12 12v9"/>',
    "archive": '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/><path d="M10 13h4"/>',
    "pdf": '<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5"/><path d="M8.5 16.5c2-4 3.5-7 3.5-4.5s-3 4.5-4 4.5 3-2 7-1.5"/>',
    "sheet": '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M4 9h16M4 15h16M10 3v18"/>',
    "slides": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M12 16v4M8 20h8M8 12V9M12 12V7M16 12v-2"/>',
    "exec": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 9h18"/><path d="m10 13 4 2.5-4 2.5z"/>',
    "text": '<path d="M5 6h14M5 10h14M5 14h10M5 18h7"/>',
    "font": '<path d="M5 20 11 4h2l6 16"/><path d="M8 14h8"/>',
    "monitor": '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
    "phone": '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
    "headphones": '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3" y="14" width="4" height="7" rx="1.5"/><rect x="17" y="14" width="4" height="7" rx="1.5"/>',
    "printer": '<path d="M7 9V3h10v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "camera": '<path d="M4 7h3l2-3h6l2 3h3a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="4"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "power": '<path d="M12 3v9"/><path d="M6.3 6.3a8 8 0 1 0 11.4 0"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/>',
    "bell": '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 21h4"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "calc": '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0"/><path d="M5.5 12.5a10 10 0 0 1 13 0"/><path d="M9 16a5 5 0 0 1 6 0"/><path d="M12 19.5h.01"/>',
    "bluetooth": '<path d="m7 7 10 10-5 4V3l5 4L7 17"/>',
    "volume": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "store": '<path d="M5 8h14l-1 12H6z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "files": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><circle cx="12" cy="13.5" r="2.5"/><path d="m14 15.5 2 2"/>',
    "help": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6v.6M12 17h.01"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "cloud": '<path d="M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9.5a4.3 4.3 0 0 1-.5 8.5z"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7"/><path d="M20 4v7h-7"/>',
    "x": '<path d="m6 6 12 12M18 6 6 18"/>',
}

# category -> gradient (top, bottom)
C = {"place": ("#feaa34", "#d9771a"), "system": ("#5a6170", "#2c313a"), "net": ("#3fa7ff", "#1b5fbf"),
     "media": ("#ff6b8b", "#c4325c"), "doc": ("#5c9dff", "#2f5fd0"), "code": ("#35c48d", "#1b8a5e"),
     "warn": ("#ff9f43", "#e0582b"), "device": ("#8b7cff", "#5340d6"), "game": ("#b46bff", "#7a2fd6"),
     "util": ("#2fc6d6", "#178a9a")}

TILE = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>
  <rect x="4" y="4" width="56" height="56" rx="14" fill="url(#g)"/>
  <rect x="4" y="4" width="56" height="28" rx="14" fill="#ffffff" opacity=".08"/>
  <g transform="translate(14 14) scale(1.5)" fill="none" stroke="#ffffff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">{glyph}</g>
</svg>
'''
FOLDER = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient></defs>
  <path d="M6 16a5 5 0 0 1 5-5h13l5 5h24a5 5 0 0 1 5 5v28a5 5 0 0 1-5 5H11a5 5 0 0 1-5-5z" fill="{b}"/>
  <path d="M6 23a5 5 0 0 1 5-5h42a5 5 0 0 1 5 5v26a5 5 0 0 1-5 5H11a5 5 0 0 1-5-5z" fill="url(#g)"/>
  <g transform="translate(23 26) scale(.75)" fill="none" stroke="#ffffff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" opacity="{o}">{glyph}</g>
</svg>
'''

# (context, icon name, glyph, category, shape)
ICONS = [
    ("places", "folder", "", "place", "folder"),
    ("places", "user-home", "home", "place", "folder"),
    ("places", "folder-documents", "doc", "place", "folder"),
    ("places", "folder-download", "down", "place", "folder"),
    ("places", "folder-downloads", "down", "place", "folder"),
    ("places", "folder-pictures", "image", "place", "folder"),
    ("places", "folder-images", "image", "place", "folder"),
    ("places", "folder-music", "music", "place", "folder"),
    ("places", "folder-videos", "video", "place", "folder"),
    ("places", "user-desktop", "desktop", "place", "folder"),
    ("places", "folder-cloud", "cloud", "place", "folder"),
    ("places", "folder-code", "code", "place", "folder"),
    ("places", "folder-games", "game", "place", "folder"),
    ("places", "folder-favorites", "star", "place", "folder"),
    ("places", "folder-network", "network", "net", "folder"),
    ("places", "network-workgroup", "network", "net", "tile"),
    ("places", "user-trash", "trash", "system", "tile"),
    ("places", "user-trash-full", "trashfull", "system", "tile"),
    ("devices", "drive-harddisk", "drive", "device", "tile"),
    ("devices", "drive-removable-media", "usb", "device", "tile"),
    ("devices", "drive-removable-media-usb", "usb", "device", "tile"),
    ("devices", "computer", "monitor", "device", "tile"),
    ("devices", "video-display", "monitor", "device", "tile"),
    ("devices", "phone", "phone", "device", "tile"),
    ("devices", "audio-headphones", "headphones", "device", "tile"),
    ("devices", "printer", "printer", "device", "tile"),
    ("devices", "camera-web", "camera", "device", "tile"),
    ("mimetypes", "text-plain", "text", "doc", "tile"),
    ("mimetypes", "text-x-generic", "text", "doc", "tile"),
    ("mimetypes", "application-pdf", "pdf", "warn", "tile"),
    ("mimetypes", "x-office-document", "doc", "doc", "tile"),
    ("mimetypes", "x-office-spreadsheet", "sheet", "code", "tile"),
    ("mimetypes", "x-office-presentation", "slides", "warn", "tile"),
    ("mimetypes", "image-x-generic", "image", "media", "tile"),
    ("mimetypes", "video-x-generic", "video", "media", "tile"),
    ("mimetypes", "audio-x-generic", "music", "media", "tile"),
    ("mimetypes", "package-x-generic", "package", "system", "tile"),
    ("mimetypes", "application-x-archive", "archive", "system", "tile"),
    ("mimetypes", "application-x-executable", "exec", "system", "tile"),
    ("mimetypes", "text-x-script", "code", "code", "tile"),
    ("mimetypes", "text-x-python", "code", "code", "tile"),
    ("mimetypes", "font-x-generic", "font", "doc", "tile"),
    ("apps", "system-file-manager", "files", "place", "tile"),
    ("apps", "halos-files", "files", "place", "tile"),
    ("apps", "utilities-terminal", "terminal", "system", "tile"),
    ("apps", "org.kde.konsole", "terminal", "system", "tile"),
    ("apps", "preferences-system", "settings", "system", "tile"),
    ("apps", "systemsettings", "settings", "system", "tile"),
    ("apps", "internet-web-browser", "globe", "net", "tile"),
    ("apps", "accessories-text-editor", "edit", "doc", "tile"),
    ("apps", "org.kde.kate", "edit", "doc", "tile"),
    ("apps", "accessories-calculator", "calc", "util", "tile"),
    ("apps", "org.kde.kcalc", "calc", "util", "tile"),
    ("apps", "accessories-screenshot", "camera", "util", "tile"),
    ("apps", "org.kde.spectacle", "camera", "util", "tile"),
    ("apps", "multimedia-video-player", "video", "media", "tile"),
    ("apps", "multimedia-audio-player", "music", "media", "tile"),
    ("apps", "applications-games", "game", "game", "tile"),
    ("apps", "system-software-install", "store", "code", "tile"),
    ("apps", "help-browser", "help", "net", "tile"),
    ("apps", "preferences-desktop-notification", "bell", "warn", "tile"),
    ("apps", "office-calendar", "calendar", "warn", "tile"),
    ("apps", "preferences-system-time", "clock", "util", "tile"),
    ("apps", "mail-client", "mail", "net", "tile"),
    ("apps", "system-lock-screen", "lock", "system", "tile"),
    ("apps", "system-shutdown", "power", "warn", "tile"),
    ("apps", "system-search", "search", "util", "tile"),
    ("apps", "preferences-system-network", "wifi", "net", "tile"),
    ("apps", "preferences-system-bluetooth", "bluetooth", "net", "tile"),
    ("apps", "preferences-desktop-sound", "volume", "media", "tile"),
    ("apps", "preferences-desktop-font", "font", "doc", "tile"),
    ("apps", "user-identity", "user", "place", "tile"),
    ("apps", "system-users", "user", "place", "tile"),
    ("apps", "applications-development", "code", "code", "tile"),
    ("apps", "applications-utilities", "settings", "util", "tile"),
    ("apps", "applications-internet", "globe", "net", "tile"),
    ("apps", "applications-multimedia", "music", "media", "tile"),
    ("apps", "applications-office", "doc", "doc", "tile"),
    ("apps", "applications-system", "settings", "system", "tile"),
]

INDEX = """[Icon Theme]
Name=HalOS
Comment=HalOS icons: one style for places, folders, files, devices and system apps. App logos come from their makers.
Inherits=breeze-dark,breeze,hicolor
Example=folder
DisplayDepth=32
Directories={dirs}

"""


def render(glyph: str, cat: str, shape: str) -> str:
    a, b = C[cat]
    if shape == "folder":
        return FOLDER.format(a=a, b=b, glyph=G.get(glyph, ""), o=".95" if glyph else "0")
    return TILE.format(a=a, b=b, glyph=G[glyph])


def main() -> int:
    contexts = sorted({c for c, *_ in ICONS})
    dirs = [f"scalable/{c}" for c in contexts]
    for d in dirs:
        (OUT / d).mkdir(parents=True, exist_ok=True)
    for context, name, glyph, cat, shape in ICONS:
        (OUT / "scalable" / context / f"{name}.svg").write_text(render(glyph, cat, shape), encoding="utf-8", newline="\n")
    ctx_name = {"apps": "Applications", "devices": "Devices", "mimetypes": "MimeTypes", "places": "Places"}
    body = INDEX.format(dirs=",".join(dirs))
    for c in contexts:
        body += f"[scalable/{c}]\nSize=64\nMinSize=16\nMaxSize=512\nType=Scalable\nContext={ctx_name[c]}\n\n"
    (OUT / "index.theme").write_text(body, encoding="utf-8", newline="\n")
    # HalOS-light: the same icons (the package links its scalable/ to HalOS's), falling back to light Breeze.
    light = OUT.parent / "HalOS-light"
    light.mkdir(exist_ok=True)
    (light / "index.theme").write_text(body.replace("Name=HalOS", "Name=HalOS (light)")
                                       .replace("Inherits=breeze-dark,breeze,hicolor", "Inherits=breeze,hicolor"),
                                       encoding="utf-8", newline="\n")
    print(f"{len(ICONS)} icons -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
