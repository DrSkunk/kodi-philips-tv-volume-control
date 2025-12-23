#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KEY="$1"
if [ -z "$KEY" ]; then
  echo "Usage: $0 <KeyName> [count] [port]" >&2
  exit 1
fi
shift
exec /usr/bin/python3 "$SCRIPT_DIR/philips_tv.py" key "$KEY" "$@"
