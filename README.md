Bindings for VKB Gladiator NXT, plus `joytokey`, a Linux (evdev/uinput) replacement for JoyToKey.

Converted JoyToKey into a Linux .py script.

For SC Alpha 4.10

## Linux: joytokey
A small evdev/uinput daemon that replaces JoyToKey on Linux. It runs original JoyToKey `.cfg` files directly (no conversion), reads joysticks without grabbing them (games still see the real devices) and emits keyboard/mouse events.

Supported in a `.cfg`: keyboard buttons, mouse-wheel buttons, and axes that move the mouse. Anything else (POV hats, axis-to-key, etc.) is skipped with a warning.

Needs `python-evdev` (`sudo pacman -S python-evdev`), Python 3.11+, and access to `/dev/input/event*` and `/dev/uinput`.

    ./install.sh              # copies to ~/.local/share/joytokey, links ~/.local/bin/with-joytokey
    ./install.sh --uninstall

Run a game (or any command) with the daemon active only while it runs:

    with-joytokey --config "DualVKB/JoyToKey Dual VKB 4.10.cfg" <command> [args...]

For the mirrored layout, use `JoyToKey Dual VKB Mirrored 4.10.cfg` instead.

### Choosing your joysticks
A `.cfg` only says "Joystick 1", "Joystick 2", ... so tell joytokey which device each one is.
1. `python3 ~/.local/share/joytokey/joytokey.py --list-devices` shows connected devices and their `/dev/input/by-id` names.
2. Copy `~/.local/share/joytokey/profiles/vkb-gladiator-nxt.toml` to `~/.config/joytokey/config.toml` and edit `joysticks` (in order: Joystick 1, 2, ...). Optionally set `cfg` there so `--config` isn't needed.
3. `joytokey.py --config FILE --monitor` prints button and axis numbers as you press things, to check they match your `.cfg`.

`--joysticks DEV,DEV` overrides the settings file. Settings lookup: `$JOYTOKEY_CONFIG`, `~/.config/joytokey/config.toml`, then the bundled VKB settings.

The previous TOML-profile version is kept in `JoyToKey/legacy/` as a backup.

## Recommended In Game Curves

Pitch/Yaw = 1.3
Roll = 2.0 or higher

Strafe Up/Down, Left/Right, & Forward/Back = 3.0
