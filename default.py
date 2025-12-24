#!/usr/bin/env python3
"""Kodi GUI wrapper for philips_tv.py."""

import os
import sys

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

addon = xbmcaddon.Addon()
ADDON_NAME = addon.getAddonInfo("name")
PROFILE_PATH = xbmcvfs.translatePath(addon.getAddonInfo("profile"))
xbmcvfs.mkdirs(PROFILE_PATH)

# Store settings/auth inside the Kodi profile for this add-on.
os.environ.setdefault("PHILIPS_TV_BASE_DIR", PROFILE_PATH)

import philips_tv


def log(message: str) -> None:
    xbmc.log(f"[{ADDON_NAME}] {message}", xbmc.LOGINFO)


def notify(message: str, error: bool = False) -> None:
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(ADDON_NAME, message, icon, 3000)


def pair_via_gui() -> None:
    dialog = xbmcgui.Dialog()
    ip = dialog.input("TV IP address", defaultt="")
    if not ip:
        return

    port_str = dialog.input("Port", defaultt="1926", type=xbmcgui.INPUT_NUMERIC)
    port = int(port_str) if port_str else 1926

    proceed = dialog.yesno(
        "Confirm pairing",
        f"Request pairing with {ip}:{port}?\nA PIN will appear on the TV next."
        "\nNote: If this box is connected to the same TV, the PIN overlay may cover this input dialog.\n You can input the PIN blindly and press enter.",
    )
    if not proceed:
        return

    def pin_reader(prompt: str = "Enter PIN shown on TV: ") -> str:
        # Explicit empty default to avoid reusing prior numeric inputs (e.g. 1926).
        return dialog.input("TV PIN", defaultt="", type=xbmcgui.INPUT_NUMERIC)

    try:
        philips_tv.pair(ip, port, pin_reader=pin_reader)
        notify("Paired with TV")
    except Exception as exc:  # noqa: BLE001
        log(f"Pair failed: {exc}")
        notify(f"Pair failed: {exc}", error=True)


def send_key_from_gui(key: str, count: int = 1) -> None:
    try:
        philips_tv.send_key_times(key, count)
        notify(f"Sent {key}")
    except Exception as exc:  # noqa: BLE001
        log(f"Key {key} failed: {exc}")
        notify(f"Failed to send {key}: {exc}", error=True)


def configure_adb_via_gui() -> None:
    dialog = xbmcgui.Dialog()
    ip = dialog.input("ADB TV IP address", defaultt="")
    if not ip:
        return

    port_str = dialog.input("ADB Port", defaultt="5555", type=xbmcgui.INPUT_NUMERIC)
    port = int(port_str) if port_str else 5555

    proceed = dialog.yesno(
        "Configure ADB",
        f"Configure ADB for {ip}:{port}?\nMake sure ADB debugging is enabled on the TV.",
    )
    if not proceed:
        return

    try:
        philips_tv.save_adb_settings(enabled=True, host=ip, port=port)
        notify("ADB configured")
    except Exception as exc:  # noqa: BLE001
        log(f"ADB setup failed: {exc}")
        notify(f"ADB setup failed: {exc}", error=True)


def toggle_adb_mode_via_gui() -> None:
    dialog = xbmcgui.Dialog()
    adb_settings = philips_tv.get_adb_settings()

    current_enabled = adb_settings.get("enabled", False)
    current_use_for_all = adb_settings.get("use_for_all", False)

    options = [
        f"Enable ADB: {'Yes' if current_enabled else 'No'}",
        f"Use ADB for all operations: {'Yes' if current_use_for_all else 'No'}",
        "Back",
    ]

    choice = dialog.select("ADB Settings", options)

    if choice == 0:
        new_enabled = not current_enabled
        philips_tv.save_adb_settings(enabled=new_enabled)
        notify(f"ADB {'enabled' if new_enabled else 'disabled'}")
    elif choice == 1:
        new_use_for_all = not current_use_for_all
        philips_tv.save_adb_settings(use_for_all=new_use_for_all)
        notify(f"ADB use_for_all set to {new_use_for_all}")


def check_adb_via_gui() -> None:
    try:
        available, message = philips_tv.check_adb_available()
        if available:
            notify(f"✓ {message}")
        else:
            dialog = xbmcgui.Dialog()
            full_message = (
                f"{message}\n\n"
                "Manually install Android SDK Platform Tools on LibreELEC.\n"
                "See README for installation instructions.\n\n"
                "Alternative: Run ADB from another computer on your network."
            )
            dialog.ok("ADB Not Available", full_message)
    except Exception as exc:  # noqa: BLE001
        log(f"ADB check failed: {exc}")
        notify(f"ADB check failed: {exc}", error=True)


def show_menu() -> None:
    dialog = xbmcgui.Dialog()
    options = [
        "Pair TV",
        "Configure ADB",
        "Check ADB Availability",
        "ADB Settings",
        "Test Volume Up",
        "Test Volume Down",
        "Test Mute",
        "Test Power (Standby)",
        "Test Back",
        "Exit",
    ]

    while True:
        choice = dialog.select("Philips TV Control", options)
        if choice in (-1, len(options) - 1):
            break
        if choice == 0:
            pair_via_gui()
        elif choice == 1:
            configure_adb_via_gui()
        elif choice == 2:
            check_adb_via_gui()
        elif choice == 3:
            toggle_adb_mode_via_gui()
        elif choice == 4:
            send_key_from_gui("VolumeUp")
        elif choice == 5:
            send_key_from_gui("VolumeDown")
        elif choice == 6:
            send_key_from_gui("Mute")
        elif choice == 7:
            send_key_from_gui("Standby")
        elif choice == 8:
            send_key_from_gui("Back")


def handle_args(args) -> None:
    if not args:
        show_menu()
        return

    cmd = args[0]
    cli_commands = {
        "pair",
        "volume",
        "get_volume",
        "volume_up",
        "volume_down",
        "hdmi",
        "key",
        "power_hdmi1",
    }

    try:
        if cmd in cli_commands:
            if cmd == "power_hdmi1":
                port = int(args[1]) if len(args) >= 2 else None
                philips_tv.toggle_hdmi1_or_standby(port)
            else:
                philips_tv.handle_command(args)
            return

        # Fallback: treat the first argument as a key name for keymap use.
        key_name = cmd
        count = int(args[1]) if len(args) >= 2 else 1
        port = int(args[2]) if len(args) >= 3 else None
        philips_tv.send_key_times(key_name, count, port)
    except Exception as exc:  # noqa: BLE001
        log(f"Run failed for args {args}: {exc}")
        notify(f"Error: {exc}", error=True)


def main() -> None:
    # Kodi passes arguments starting at index 1 for scripts invoked via RunScript.
    args = sys.argv[1:]
    handle_args(args)


if __name__ == "__main__":
    main()
