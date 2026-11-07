"""The "Drives & OS" settings page: every drive, and restarting into another OS."""

from ui.components.drives_panel import DrivesPanel, OsSwitchCard
from ui.widgets import Page

TITLE = "Drives & OS"
ICON = "drive"
ORDER = 40


def build():
    page = Page(TITLE, "Open any drive on this PC, and restart into another operating system.", scroll=True)
    drives_card, switch = DrivesPanel(), OsSwitchCard()
    page.root.addWidget(switch)
    page.root.addWidget(drives_card)
    page.root.addStretch(1)
    switch.refresh()
    drives_card.refresh()
    return page
