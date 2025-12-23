# Philips TV Volume Bridge for Kodi

Small stdlib-only Python helper that proxies Kodi’s volume keys directly to a Philips JointSpace v6 TV.

## Files
- `philips_tv.py` – main script (pairing and volume/key commands).
- `philips_tv_settings.json` / `philips_tv_auth.json` – saved host/port and digest auth, written alongside the script after pairing; optional `verbose` flag for extra logging (default `false`).

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

## Kodi GUI add-on
Install the folder as a script add-on (local install from zip or source). Launch “Philips TV Volume Control” from Programs to:

- Pair with your TV (enter IP/port and PIN from the TV).
- Test buttons (Volume Up/Down, Mute, Power/Standby, Back).

Settings and auth are stored under the add-on data directory so pairing only has to be done once.

## Kodi keymap to send media keys
Use the add-on entrypoint directly from keymaps so Kodi sends volume to the TV instead of local audio. Create or edit `/storage/.kodi/userdata/keymaps/keyboard.xml` (or a custom keymap) with entries like:

```xml
<keymap>
  <global>

    <keyboard>
      <volume_up>RunScript(script.philips-tv-volume-control,VolumeUp)</volume_up>
      <volume_down>RunScript(script.philips-tv-volume-control,VolumeDown)</volume_down>
      <key id="0xf200">PlayPause</key>
      <menu>Back</menu>
      <power>RunScript(script.philips-tv-volume-control,power_hdmi1)</power>
    </keyboard>

    <remote>
      <volume_up>RunScript(script.philips-tv-volume-control,VolumeUp)</volume_up>
      <volume_down>RunScript(script.philips-tv-volume-control,VolumeDown)</volume_down>
      <play_pause>PlayPause</play_pause>
      <power>RunScript(script.philips-tv-volume-control,power_hdmi1)</power>
    </remote>

  </global>
</keymap>

The `power_hdmi1` helper switches the TV to HDMI 1; if it is already on HDMI 1, it sends standby to turn the TV off.

```

Restart Kodi (or `systemctl restart kodi` if applicable) to apply the keymap.

Any first argument passed to `RunScript(script.philips-tv-volume-control, ...)` is treated as a Philips key name (e.g. `Standby`, `Back`, `Mute`), so you can map additional buttons the same way.

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
If your TV returns a 404 for the default endpoint, the script falls back to `activities/launch` automatically.

Send any remote key (optional repeat count):
```bash
python3 philips_tv.py key VolumeUp [count] [port]
```

## Verbose logging
Set `"verbose": true` in `philips_tv_settings.json` to print HTTP attempts and command dispatch details. Default is `false`.
