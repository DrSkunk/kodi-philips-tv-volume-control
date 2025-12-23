#!/usr/bin/env python3
"""
Lightweight console harness to exercise the add-on modules without Kodi.

Usage:
  python local_tester.py [args...]

Examples:
  python local_tester.py VolumeUp
  python local_tester.py power_hdmi1
  python local_tester.py pair 192.168.1.100
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


PROFILE_DIR = Path(__file__).parent / "local_profile"
PROFILE_DIR.mkdir(parents=True, exist_ok=True)


# ----- stub xbmc / xbmcaddon / xbmcgui / xbmcvfs -----

class _FakeAddon:
    def getAddonInfo(self, key: str) -> str:
        if key == "name":
            return "Philips TV Volume Control (local tester)"
        if key == "profile":
            return str(PROFILE_DIR)
        return ""


class _FakeDialog:
    def input(self, heading: str, defaultt: str = "", type=None):  # noqa: ANN001
        prompt = f"{heading}"
        if defaultt:
            prompt += f" [{defaultt}]"
        prompt += ": "
        value = input(prompt).strip()
        return value or defaultt

    def select(self, heading: str, options):  # noqa: ANN001
        print(f"{heading}")
        for idx, opt in enumerate(options):
            print(f"  {idx}) {opt}")
        try:
            choice = int(input("Select number (or blank to cancel): ").strip() or "-1")
        except ValueError:
            choice = -1
        return choice

    def yesno(self, heading: str, line1: str, line2: str = "", line3: str = "") -> bool:
        print(f"{heading}: {line1} {line2} {line3}".strip())
        return input("Proceed? [y/N]: ").strip().lower() in {"y", "yes"}

    def notification(self, title: str, message: str, *_, **__):  # noqa: ANN001
        print(f"[NOTIFY] {title}: {message}")


def _fake_log(message: str, level: int = 0) -> None:  # noqa: ARG001
    print(f"[LOG] {message}")


class _FakeVfs:
    @staticmethod
    def mkdirs(path: str) -> None:
        Path(path).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def translatePath(path: str) -> str:
        return path


# Inject stubs before importing default.py.
sys.modules.setdefault("xbmc", type("xbmc", (), {"log": _fake_log, "LOGINFO": 0}))
sys.modules.setdefault("xbmcaddon", type("xbmcaddon", (), {"Addon": _FakeAddon}))
sys.modules.setdefault(
    "xbmcgui",
    type(
        "xbmcgui",
        (),
        {
            "Dialog": _FakeDialog,
            "NOTIFICATION_INFO": 0,
            "NOTIFICATION_ERROR": 1,
            "INPUT_NUMERIC": 0,
        },
    ),
)
sys.modules.setdefault("xbmcvfs", _FakeVfs)

# Keep add-on data separate from working tree.
os.environ.setdefault("PHILIPS_TV_BASE_DIR", str(PROFILE_DIR))


def main() -> None:
    from default import handle_args  # type: ignore

    args = sys.argv[1:]
    handle_args(args)


if __name__ == "__main__":
    main()
