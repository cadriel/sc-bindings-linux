Bindings for VKB Gladiator NXT, plus `joytokey`, a Linux (evdev/uinput) replacement for JoyToKey.

Converted JoyToKey into a Linux .py script.

For SC Alpha 4.10

## Linux: joytokey
A small evdev/uinput daemon that replaces JoyToKey on Linux. It reads joysticks without grabbing them (games still see the real devices) and emits keyboard/mouse events. It works with any joystick: behaviour comes from a TOML profile.

Needs `python-evdev` (`sudo pacman -S python-evdev`), Python 3.11+, and access to `/dev/input/event*` and `/dev/uinput`.

    ./install.sh              # copies to ~/.local/share/joytokey, links ~/.local/bin/with-joytokey
    ./install.sh --uninstall

Run a game (or any command) with the daemon active only while it runs:

    with-joytokey [--config FILE] [--mirrored] <command> [args...]

### Using other joysticks
1. `python3 ~/.local/share/joytokey/joytokey.py --list-devices` shows connected devices and their `/dev/input/by-id` names.
2. Copy `~/.local/share/joytokey/profiles/vkb-gladiator-nxt.toml` to `~/.config/joytokey/config.toml` and edit it: device matches, the optional stick that moves the mouse, and `[[button]]` entries (keys and/or mouse wheel).
3. `joytokey.py --monitor` prints axis names and button numbers as you press things, so you can fill in the profile.

Profile lookup: `--config FILE`, `$JOYTOKEY_CONFIG`, `~/.config/joytokey/config.toml`, then the bundled VKB profile. `--mirrored` swaps the first two `[devices]` roles.

## Recommended In Game Curves

Pitch/Yaw = 1.3
Roll = 2.0 or higher

Strafe Up/Down, Left/Right, & Forward/Back = 3.0
