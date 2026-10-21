# Dual JoyToKey replacement: status notes

Goal: run original JoyToKey `.cfg` files (e.g. `DualVKB/JoyToKey Dual VKB 4.10.cfg`) on Linux, without JoyToKey and without converting them.
Scope: keyboard buttons, wheel buttons and axis->mouse (what the Dual VKB cfgs use). Other cfg features are skipped with a warning.
The earlier TOML-profile version (hand-written port of the Dual VKB cfg) is kept in `JoyToKey/legacy/` along with the original notes.

## Approach
`joytokey.py` reads both sticks via evdev WITHOUT grabbing them, so Star Citizen still sees
the real VKB devices (the in-game XML identifies them by name). It emits keyboard/mouse events
through a uinput virtual device named `joytokey`. input-remapper was rejected because it
grabs devices and renames them.

Access: `/dev/input/event*` and `/dev/uinput` are accessible to user `craig` via ACLs, so no root needed.

## What the .cfg does (non-mirrored: Joystick 1 = L stick, Joystick 2 = R stick)
The daemon now derives all of this from the cfg; the table is just what the Dual VKB cfg contains.
| JoyToKey | Linux |
|---|---|
| L axes 5/6 -> mouse move (Axis5n=-X, 5p=+X, 6n=+Y, 6p=-Y; threshold 20%) | L mini-stick -> REL_X/REL_Y |
| R Button03 -> `R` | KEY_R |
| R Button05 -> `RCtrl+F4` (VK 0xA3 + 0x73) | KEY_RIGHTCTRL + KEY_F4 |
| R Button16 / Button18 -> wheel +24 / -24 | REL_WHEEL +1 / -1, repeats ~10/s while held |

For the mirrored layout pass `JoyToKey Dual VKB Mirrored 4.10.cfg` (the old `--mirrored` flag was removed).

Cfg decoding: `Button=1,<VK>:<VK>...` keyboard (hex virtual-key codes -> KEY_*); `Button=2,x,y,wheel` wheel (sign only); `AxisNn/Np=2,x,y` mouse move (percent of full speed, 6 px/s per percent, so 100 = 600 px/s as before); `Threshold`/`Threshold2` -> deadzone for Joystick 1 / others.
Joystick N -> physical device comes from `joysticks` in `~/.config/joytokey/config.toml`, or `--joysticks`.

## Files
- `JoyToKey/joytokey.py`: the daemon. `--config FILE.cfg` picks the JoyToKey cfg, `--joysticks A,B` overrides the device list, `--monitor` prints raw axis/button events (with button/axis numbers), `--list-devices` lists joysticks.
- `JoyToKey/joytokey_cfg.py`: pure-Python JoyToKey cfg reader (VK table, buttons, axes, thresholds). Tests: `python3 JoyToKey/__tests__/joytokey_cfg.spec.py`.
- `JoyToKey/profiles/vkb-gladiator-nxt.toml`: settings only now (`joysticks` list, optional `cfg`).
- `JoyToKey/with-joytokey`: wrapper that starts the daemon, runs a command, and stops the daemon when it exits (log: `~/.local/state/joytokey.log`). Takes `--config` / `--joysticks`. No system service.
- `JoyToKey/legacy/`: backup of the previous TOML-profile script, profile and notes.
- `JoyToKey/joytokey.service`: unused systemd user unit (not in the repo); superseded by the wrapper.

## Status
- Cfg-reader rewrite (2026-10-22): parser unit-tested against both Dual VKB cfgs; the daemon itself is NOT yet run on hardware (written without the sticks on hand).
  To verify: (1) axis numbering: `Axis5`/`Axis6` are mapped as the 5th/6th axis in sorted evdev code order; confirm `--monitor` shows the left mini-stick as axes 5/6 (ABS_RX/RY), else adjust `axis_index_map`; (2) mouse speed/direction unchanged; (3) buttons 3/5/16/18 on Joystick 2 as before.
  The findings below were verified with the legacy TOML version.
- Script starts, finds both sticks (L: event21, R: event9 at time of writing).
- User ran it and saw axis output from the left stick and button output from the right stick.
- Verified by user (2026-10-19): mini-stick axes are `ABS_RX`/`ABS_RY` (mouse moves with the left mini-stick); R button numbering is right (physical 3 -> "button 3", 5 -> "button 5").
  Button 3 types `r` and button 5 sends RCtrl+F4 (the terminal echoed `^[[1;5S`), so the key output works.
  Held-key "repeats" seen in the terminal come from the compositor's keyboard autorepeat on the virtual keyboard (the script never emits value=2 events). Not a bug; a game reads the held state. Inconsistent repeat on button 5 is likely the compositor repeat state (last-pressed key). Ignore unless it shows up in-game.
  Note: with `--monitor` the keys are also typed into the focused window, so test in a scratch window.
- Also verified (2026-10-19): mouse direction and speed are OK; buttons 16/18 print correctly and scroll the window up/down.
  In-game these wheel buttons are Tractor Beam increase/decrease distance (XML shows bare `js2_ ` wheel inputs). 16 and 18 also natively trigger Radar Ping and Look Behind.
- Key repeat: fixed on the Hyprland side with a per-device override for `joytokey` (`repeat_rate = 0` via `hl.device` in `~/.config/hypr/config/inputs.lua`, in the dotfiles repo). Required on this setup so held buttons don't send repeated key-downs.
- STILL to verify: in-game test under Wine (R, RCtrl+F4, virtual mouse, tractor beam wheel direction).

## Next steps
1. Finish the verification above (including the cfg-reader checks); deadzone/speed now come from the cfg (`Threshold`, axis speed values).
2. Test in Star Citizen under Wine (confirm RCtrl+F4 and R register, and that the virtual mouse is picked up).
3. Hook into the launcher: in `/mnt/disk2/star-citizen/sc-launch.sh` (LUG Helper script, may be overwritten by helper updates), change the final launch line to
   `with-joytokey --config "/path/to/JoyToKey Dual VKB 4.10.cfg" game-performance "$wine_path"/wine "C:\Program Files\Roberts Space Industries\RSI Launcher\RSI Launcher.exe" > "$launch_log" 2>&1`
   (run `./install.sh` once, then plain `with-joytokey` works from `~/.local/bin`).
4. Decide whether to commit these files to the repo (nothing committed yet).
