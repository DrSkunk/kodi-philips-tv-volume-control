#!/usr/bin/env python3
"""
Philips JointSpace API v6 - Pairing + Volume

Usage:
  python philips_tv.py pair        <TV_IP> [port=1926]
  python philips_tv.py volume      <volume> [port=1926]
  python philips_tv.py get_volume  [port=1926]
  python philips_tv.py volume_up   [steps=1] [port=1926]
  python philips_tv.py volume_down [steps=1] [port=1926]
  python philips_tv.py hdmi        <n> [port=1926]
  python philips_tv.py key         <KeyName> [count=1] [port=1926]

Designed to run on OpenELEC/Linux with only the Python standard library.
"""

import base64
import hashlib
import hmac
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Self-signed cert on TV
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Philips pairing secret (API v6)
SECRET_KEY_B64 = (
    "ZmVay1EQVFOaZhwQ4Kv81ypLAZNczV9sG4KkseXWn1NEk6cXmPKO/MCa9sryslvLCFMnNe4Z4CPXzToowvhHvA=="
)

# Allow overriding the storage location (useful when run as a Kodi add-on).
BASE_DIR = os.environ.get(
    "PHILIPS_TV_BASE_DIR", os.path.dirname(os.path.abspath(__file__))
)
SETTINGS_FILE = os.path.join(BASE_DIR, "philips_tv_settings.json")
AUTH_FILE = os.path.join(BASE_DIR, "philips_tv_auth.json")
VERBOSE: bool = False


# ---------- helpers ----------

def usage() -> None:
    print(
        "\nUsage:\n"
        "  python philips_tv.py pair        <TV_IP> [port=1926]\n"
        "  python philips_tv.py volume      <volume> [port=1926]\n"
        "  python philips_tv.py get_volume  [port=1926]\n"
        "  python philips_tv.py volume_up   [steps=1] [port=1926]\n"
        "  python philips_tv.py volume_down [steps=1] [port=1926]\n"
        "  python philips_tv.py hdmi        <n> [port=1926]\n"
        "  python philips_tv.py key         <KeyName> [count=1] [port=1926]\n"
    )
    sys.exit(1)


def auth_file() -> str:
    return AUTH_FILE


def set_verbose(enabled: bool) -> None:
    global VERBOSE
    VERBOSE = bool(enabled)


def verbose_log(message: str) -> None:
    if VERBOSE:
        print(message)


def load_settings() -> Tuple[str, int, bool]:
    if not os.path.exists(SETTINGS_FILE):
        raise RuntimeError("Settings not found. Pair first.")
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    verbose = bool(data.get("verbose", False))
    set_verbose(verbose)
    return data["ip"], int(data.get("port", 1926)), verbose


def save_settings(ip: str, port: int, verbose: Optional[bool] = None) -> None:
    current_verbose = False
    if verbose is None and os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, encoding="utf-8") as f:
                existing = json.load(f)
                current_verbose = bool(existing.get("verbose", False))
        except Exception:  # noqa: BLE001
            current_verbose = False

    final_verbose = current_verbose if verbose is None else bool(verbose)
    set_verbose(final_verbose)

    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"ip": ip, "port": port, "verbose": final_verbose}, f, indent=2)


def random_id(length: int = 16) -> str:
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    rng = random.SystemRandom()
    return "".join(rng.choice(chars) for _ in range(length))


def read_pin(prompt: str = "Enter PIN shown on TV: ") -> str:
    return input(prompt).strip()


def auth_signature(timestamp: str, pin: str) -> str:
    key = base64.b64decode(SECRET_KEY_B64)
    msg = f"{timestamp}{pin}".encode("utf-8")
    hmac_hex = hmac.new(key, msg, hashlib.sha1).hexdigest()
    return base64.b64encode(hmac_hex.encode("utf-8")).decode("ascii")


def http_json(
    url: str,
    payload=None,
    username: str = None,
    password: str = None,
    method: str = "POST",
    retries: int = 2,
    retry_delay: float = 0.5,
    timeout: int = 20,
) -> dict:
    verbose_log(f"→ HTTP {method} {url} (payload={bool(payload)})")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    if username and password:
        password_mgr.add_password(None, url, username, password)

    auth_handler = urllib.request.HTTPDigestAuthHandler(password_mgr)
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=SSL_CONTEXT), auth_handler
    )

    attempts = retries + 1
    for attempt in range(attempts):
        try:
            verbose_log(f"  attempt {attempt + 1}/{attempts}")
            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                verbose_log("  ✓ HTTP ok")
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"{e.code} {e.reason}: {body}") from None
        except urllib.error.URLError as e:
            if attempt < attempts - 1:
                verbose_log(f"  retrying after URLError: {e.reason}")
                time.sleep(retry_delay)
                continue
            raise RuntimeError(f"Request failed: {e.reason}") from None


# ---------- commands ----------

def pair(ip: str, port: int = 1926, pin_reader=read_pin) -> None:
    base = f"https://{ip}:{port}/6"

    device_id = random_id()
    device = {
        "device_name": "python",
        "device_os": f"python {sys.version.split()[0]}",
        "app_id": "python.jointspace",
        "app_name": "Python JointSpace",
        "type": "native",
        "id": device_id,
    }

    print("→ Pair request")
    req = http_json(
        f"{base}/pair/request",
        payload={"scope": ["read", "write", "control"], "device": device},
    )

    print("PIN should now be visible on TV")
    pin = pin_reader()

    grant_payload = {
        "auth": {
            "pin": pin,
            "auth_timestamp": req["timestamp"],
            "auth_signature": auth_signature(str(req["timestamp"]), pin),
            "auth_AppId": 1,
        },
        "device": device,
    }

    print("→ Pair grant")
    http_json(
        f"{base}/pair/grant",
        payload=grant_payload,
        username=device_id,
        password=req["auth_key"],
    )

    save_settings(ip, port)

    with open(auth_file(), "w", encoding="utf-8") as f:
        json.dump(
            {
                "username": device_id,
                "password": req["auth_key"],
                "pairedAt": datetime.now(timezone.utc).isoformat(),
            },
            f,
            indent=2,
        )

    print("✓ Paired successfully")


def load_auth() -> Dict[str, str]:
    path = auth_file()
    if not os.path.exists(path):
        raise RuntimeError("Not paired. Run pairing first.")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def set_volume(volume: str, port_override: int = None) -> None:
    auth = load_auth()
    ip, port_settings, _verbose = load_settings()
    port = port_override if port_override is not None else port_settings
    print(f"Setting volume to {volume} on {ip}:{port}")

    base = f"https://{ip}:{port}/6"
    payload = {"current": int(volume), "muted": False}

    http_json(
        f"{base}/audio/volume",
        payload=payload,
        username=auth["username"],
        password=auth["password"],
    )
    print(f"✓ Volume set to {volume}")


def send_key(key: str, port_override: int = None) -> None:
    """Send a virtual remote keypress to the TV."""
    auth = load_auth()
    ip, port_settings, _verbose = load_settings()
    port = port_override if port_override is not None else port_settings

    base = f"https://{ip}:{port}/6"
    payload = {"key": key}

    print(f"Sending key {key} to {ip}:{port}")
    http_json(
        f"{base}/input/key",
        payload=payload,
        username=auth["username"],
        password=auth["password"],
    )


def send_key_times(key: str, count: int, port_override: int = None) -> None:
    presses = max(0, int(count))
    if presses == 0:
        print(f"Skipping key {key}: 0 presses requested")
        return
    for _ in range(presses):
        send_key(key, port_override)


def switch_source(source_id: str, port_override: int = None) -> None:
    auth = load_auth()
    ip, port_settings, _verbose = load_settings()
    port = port_override if port_override is not None else port_settings

    base = f"https://{ip}:{port}/6"
    payload = {"id": source_id}

    print(f"Switching source to {source_id} on {ip}:{port}")
    try:
        http_json(
            f"{base}/sources/current",
            payload=payload,
            username=auth["username"],
            password=auth["password"],
        )
    except RuntimeError as exc:
        # Some models return 404 for /sources/current; try activities/launch.
        if "404" not in str(exc):
            raise
        verbose_log("Falling back to /activities/launch for source switch")
        http_json(
            f"{base}/activities/launch",
            payload=payload,
            username=auth["username"],
            password=auth["password"],
        )
    print(f"✓ Switched source to {source_id}")


def switch_to_hdmi(input_number: int = 1, port_override: int = None) -> None:
    number = max(1, int(input_number))
    source_id = f"hdmi{number}"
    switch_source(source_id, port_override)


def get_volume(port_override: int = None) -> dict:
    auth = load_auth()
    ip, port_settings, _verbose = load_settings()
    port = port_override if port_override is not None else port_settings
    print(f"Fetching volume from {ip}:{port}")

    base = f"https://{ip}:{port}/6"
    return http_json(
        f"{base}/audio/volume",
        payload=None,
        username=auth["username"],
        password=auth["password"],
        method="GET",
    )


def print_volume(port_override: int = None) -> None:
    info = get_volume(port_override)
    current = info.get("current")
    maximum = info.get("max")
    muted = info.get("muted")
    print(f"Volume: {current} / {maximum} (muted={muted})")


def get_current_source(port_override: int = None) -> Optional[str]:
    """Return the current source id (e.g. hdmi1) if available."""
    auth = load_auth()
    ip, port_settings, _verbose = load_settings()
    port = port_override if port_override is not None else port_settings
    base = f"https://{ip}:{port}/6"
    try:
        info = http_json(
            f"{base}/sources/current",
            payload=None,
            username=auth["username"],
            password=auth["password"],
            method="GET",
        )
        return str(info.get("id")) if isinstance(info, dict) else None
    except Exception as exc:  # noqa: BLE001
        verbose_log(f"Could not read current source: {exc}")
        return None


def toggle_hdmi1_or_standby(port_override: int = None) -> None:
    """Switch to HDMI1 unless already there, then put TV in standby."""
    current = (get_current_source(port_override) or "").lower()
    if current == "hdmi1":
        send_key("Standby", port_override)
    else:
        switch_to_hdmi(1, port_override)


# ---------- command dispatcher ----------


def handle_command(args: List[str]) -> None:
    if not args:
        usage()

    cmd = args[0]
    rest = args[1:]
    verbose_log(f"Handling command: {cmd} {rest}")

    if cmd == "pair":
        if len(rest) < 1:
            usage()
        ip = rest[0]
        port = int(rest[1]) if len(rest) >= 2 else 1926
        pair(ip, port)
    elif cmd == "volume":
        if len(rest) < 1:
            usage()
        volume_val = rest[0]
        port = int(rest[1]) if len(rest) >= 2 else None
        set_volume(volume_val, port)
    elif cmd == "get_volume":
        port = int(rest[0]) if len(rest) >= 1 else None
        print_volume(port)
    elif cmd == "volume_up":
        steps = int(rest[0]) if len(rest) >= 1 else 1
        port = int(rest[1]) if len(rest) >= 2 else None
        send_key_times("VolumeUp", steps, port)
    elif cmd == "volume_down":
        steps = int(rest[0]) if len(rest) >= 1 else 1
        port = int(rest[1]) if len(rest) >= 2 else None
        send_key_times("VolumeDown", steps, port)
    elif cmd == "hdmi":
        if len(rest) < 1:
            usage()
        hdmi_number = rest[0]
        port = int(rest[1]) if len(rest) >= 2 else None
        switch_to_hdmi(hdmi_number, port)
    elif cmd == "key":
        if len(rest) < 1:
            usage()
        key_name = rest[0]
        count = int(rest[1]) if len(rest) >= 2 else 1
        port = int(rest[2]) if len(rest) >= 3 else None
        send_key_times(key_name, count, port)
    else:
        usage()


# ---------- main ----------


def main() -> None:
    args = sys.argv[1:]
    try:
        handle_command(args)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
