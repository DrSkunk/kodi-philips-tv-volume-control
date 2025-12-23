# Philips TV Volume Bridge for Kodi

Small stdlib-only Python helper that proxies Kodi’s volume keys directly to a Philips JointSpace v6 TV.

## Files
- `philips_tv.py` – main script (pairing and volume/key commands).
- `philips_tv_settings.json` / `philips_tv_auth.json` – saved host/port and digest auth, written alongside the script after pairing; optional `verbose` flag for extra logging (default `false`).
- `kodi-key.sh` – generic wrapper for Kodi keymaps/buttons.

## Install on LibreELEC/OpenELEC via SSH
1) Copy the repo to the box (e.g. `/storage/kodi-philips-tv-volume-control`):
```bash
scp -r kodi-philips-tv-volume-control root@<box-ip>:/storage/
```
If you hit “Too many authentication failures”, rerun `scp`/`ssh` with `-o IdentitiesOnly=yes` to force a single key, e.g. `scp -o IdentitiesOnly=yes -r kodi-philips-tv-volume-control root@<box-ip>:/storage/`.

2) Pair once to create settings/auth files:
```bash
ssh root@<box-ip>
cd /storage/kodi-philips-tv-volume-control
python3 philips_tv.py pair <TV_IP> [port=1926]
```
Enter the PIN shown on the TV. This writes `philips_tv_settings.json` and `philips_tv_auth.json` in the same folder.

## Kodi keymap to send media keys
Map keyboard/media keys to the wrapper scripts so Kodi sends volume to the TV instead of local audio. Create or edit `/storage/.kodi/userdata/keymaps/keyboard.xml` (or a custom keymap) with entries like:

```xml
<keymap>
  <global>
    <keyboard>
      <volumeplus>RunScript(/storage/kodi-philips-tv-volume-control/kodi-key.sh VolumeUp)</volumeplus>
      <volumeminus>RunScript(/storage/kodi-philips-tv-volume-control/kodi-key.sh VolumeDown)</volumeminus>
    </keyboard>
  </global>
</keymap>
```

Restart Kodi (or `systemctl restart kodi` if applicable) to apply the keymap. The wrapper runs the Python script directly on each keypress.

## Manual usage (debug/CLI)
Volume up/down (sends remote keypresses, optional repeat count):
```bash
python3 philips_tv.py volume_up [steps]
python3 philips_tv.py volume_down [steps]
python3 philips_tv.py get_volume
```

Set absolute volume:
```bash
python3 philips_tv.py volume <n>
```

Switch HDMI input (any number, default API expects `hdmiN`):
```bash
python3 philips_tv.py hdmi <n>
```

Send any remote key (optional repeat count):
```bash
python3 philips_tv.py key VolumeUp [count] [port]
./kodi-key.sh VolumeDown 3         # example wrapper
```

## Verbose logging
Set `"verbose": true` in `philips_tv_settings.json` to print HTTP attempts and command dispatch details. Default is `false`.
