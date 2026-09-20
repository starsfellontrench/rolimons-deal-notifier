from __future__ import annotations

from winotify import Notification


def send_desktop_notification(title: str, message: str, icon_path: str = "") -> None:
    toast = Notification(
        app_id="Roblox Deal Tracker",
        title=title,
        msg=message,
        icon=icon_path,
    )
    toast.show()
