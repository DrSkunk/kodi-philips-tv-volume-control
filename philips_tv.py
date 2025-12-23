#!/usr/bin/env python3
"""
Philips JointSpace API v6 - Pairing + Volume

Usage:
  python philips_tv.py serve                           # start queue worker
  python philips_tv.py pair        <TV_IP> [port=1926]
  python philips_tv.py volume      <volume> [port=1926]
  python philips_tv.py volume_up   [port=1926]
  python philips_tv.py volume_down [port=1926]

Designed to run on OpenELEC/Linux with only the Python standard library.
"""

import base64
import errno
import hashlib
import hmac
import json
import os
import random
import shlex
import ssl
import stat
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Dict, List, Tuple

# Self-signed cert on TV
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE

# Philips pairing secret (API v6)
SECRET_KEY_B64 = (
    "ZmVay1EQVFOaZhwQ4Kv81ypLAZNczV9sG4KkseXWn1NEk6cXmPKO/MCa9sryslvLCFMnNe4Z4CPXzToowvhHvA=="
)

QUEUE_FIFO = "/tmp/philips_tv_commands.fifo"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(BASE_DIR, "philips_tv_settings.json")
AUTH_FILE = os.path.join(BASE_DIR, "philips_tv_auth.json")


# ---------- helpers ----------

def usage() -> None:
    print(
        "\nUsage:\n"
        "  python philips_tv.py serve                           # start queue worker\n"
        "  python philips_tv.py pair        <TV_IP> [port=1926]\n"
        "  python philips_tv.py volume      <volume> [port=1926]\n"
        "  python philips_tv.py volume_up   [port=1926]\n"
        "  python philips_tv.py volume_down [port=1926]\n"
    )
    sys.exit(1)


def auth_file() -> str:
    return AUTH_FILE


def load_settings() -> Tuple[str, int]:
    if not os.path.exists(SETTINGS_FILE):
        raise RuntimeError("Settings not found. Pair first.")
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["ip"], int(data.get("port", 1926))


def save_settings(ip: str, port: int) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump({"ip": ip, "port": port}, f, indent=2)


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


def ensure_fifo() -> None:
    if os.path.exists(QUEUE_FIFO):
        mode = os.stat(QUEUE_FIFO).st_mode
        if not stat.S_ISFIFO(mode):
            raise RuntimeError(f"{QUEUE_FIFO} exists and is not a FIFO")
    else:
        os.mkfifo(QUEUE_FIFO, 0o600)


def maybe_enqueue(args: List[str]) -> bool:
    if not os.path.exists(QUEUE_FIFO):
        return False
    try:
        fd = os.open(QUEUE_FIFO, os.O_WRONLY | os.O_NONBLOCK)
    except OSError as exc:  # noqa: PERF203
        if exc.errno == errno.ENXIO:
            # FIFO exists but no reader; assume stale
            os.unlink(QUEUE_FIFO)
            return False
        raise

    with os.fdopen(fd, "w") as fifo:
        fifo.write(" ".join(shlex.quote(a) for a in args) + "\n")
    print("✓ Queued command for worker")
    return True


def serve() -> None:
    ensure_fifo()
    print(f"Queue worker listening on {QUEUE_FIFO} (Ctrl+C to exit)")
    while True:
        with open(QUEUE_FIFO, "r") as fifo:
            for line in fifo:
                line = line.strip()
                if not line:
                    continue
                try:
                    handle_command(shlex.split(line), allow_queue=False)
                except Exception as exc:  # noqa: BLE001
                    print(f"Worker error on '{line}': {exc}")


def http_json(
    url: str,
    payload=None,
    username: str = None,
    password: str = None,
    method: str = "POST",
) -> dict:
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

    try:
        with opener.open(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"{e.code} {e.reason}: {body}") from None
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed: {e.reason}") from None


# ---------- commands ----------

def pair(ip: str, port: int = 1926) -> None:
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
    pin = read_pin()

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
    ip, port_settings = load_settings()
    port = port_override if port_override is not None else port_settings

    base = f"https://{ip}:{port}/6"
    payload = {"current": int(volume), "muted": False}

    http_json(
        f"{base}/audio/volume",
        payload=payload,
        username=auth["username"],
        password=auth["password"],
    )

    print(f"✓ Volume set to {volume}")


def get_volume(port_override: int = None) -> dict:
    auth = load_auth()
    ip, port_settings = load_settings()
    port = port_override if port_override is not None else port_settings

    base = f"https://{ip}:{port}/6"
    return http_json(
        f"{base}/audio/volume",
        payload=None,
        username=auth["username"],
        password=auth["password"],
        method="GET",
    )


def adjust_volume(delta: int, port_override: int = None) -> None:
    info = get_volume(port_override)
    current = int(info.get("current", 0))
    max_vol = int(info.get("max", 60))
    new_volume = max(0, min(max_vol, current + delta))
    set_volume(str(new_volume), port_override)


# ---------- command dispatcher ----------


def handle_command(args: List[str], allow_queue: bool = True) -> None:
    if not args:
        usage()

    cmd = args[0]
    rest = args[1:]

    if allow_queue and cmd != "serve" and maybe_enqueue(args):
        return

    if cmd == "serve":
        serve()
    elif cmd == "pair":
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
    elif cmd in ("volume_up", "volume-up", "volup", "up"):
        port = int(rest[0]) if len(rest) >= 1 else None
        adjust_volume(1, port)
    elif cmd in ("volume_down", "volume-down", "voldown", "down"):
        port = int(rest[0]) if len(rest) >= 1 else None
        adjust_volume(-1, port)
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
