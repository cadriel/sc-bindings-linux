#!/usr/bin/env python3
"""Linux replacement for JoyToKey: runs original JoyToKey .cfg files.

Reads joysticks via evdev WITHOUT grabbing them (games still see the real devices) and emits
keyboard / mouse events through a uinput virtual device named 'joytokey'.

The .cfg says what to do ("Joystick 1", "Joystick 2", ...); a small TOML settings file says which
physical device each joystick number is (see profiles/vkb-gladiator-nxt.toml).
"""
import argparse, asyncio, glob, os, sys, tomllib
from evdev import InputDevice, UInput, ecodes as e, list_devices
from joytokey_cfg import parse

HERE = os.path.dirname(os.path.realpath(__file__))
USER_SETTINGS = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "joytokey", "config.toml")
DEFAULT_SETTINGS = os.path.join(HERE, "profiles", "vkb-gladiator-nxt.toml")
MOUSE_PX_PER_SEC_PER_PERCENT = 6    # a JoyToKey mouse speed of 100 moves 600 px/s
MOUSE_HZ = 100
WHEEL_HZ = 10                       # wheel notches/second while a wheel button is held


def die(msg):
    sys.exit(f"joytokey: {msg}")


def key_code(name):
    c = getattr(e, name, None)
    if not isinstance(c, int):
        die(f"unknown evdev key '{name}'")
    return c


def load_settings():
    for p in (os.environ.get("JOYTOKEY_CONFIG"), USER_SETTINGS, DEFAULT_SETTINGS):
        if p and os.path.isfile(p):
            break
    else:
        die("no settings file found (copy profiles/vkb-gladiator-nxt.toml to ~/.config/joytokey/config.toml)")
    try:
        with open(p, "rb") as f:
            return tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as ex:
        die(f"cannot read {p}: {ex}")


def open_device(spec, joy):
    if spec.startswith("name:"):
        want = spec[5:].lower()
        matches = [p for p in list_devices() if want in InputDevice(p).name.lower()]
    elif spec.startswith("/"):
        matches = [spec] if os.path.exists(spec) else []
    else:
        matches = sorted(glob.glob(f"/dev/input/by-id/{spec}"))
    if not matches:
        die(f"device for Joystick {joy} ({spec}) not found; run with --list-devices")
    return InputDevice(matches[0])


def button_index_map(dev):
    """evdev button code -> 1-based button number (Nth button in sorted code order)."""
    codes = sorted(dev.capabilities().get(e.EV_KEY, []))
    return {c: i + 1 for i, c in enumerate(codes)}


def axis_index_map(dev):
    """evdev axis code -> 1-based axis number (Nth axis in sorted code order)."""
    codes = sorted(c for c, _ in dev.capabilities().get(e.EV_ABS, []))
    return {c: i + 1 for i, c in enumerate(codes)}


def list_devices_cmd():
    byid = {os.path.realpath(p): os.path.basename(p) for p in glob.glob("/dev/input/by-id/*-event-*")}
    for p in sorted(list_devices()):
        d = InputDevice(p)
        caps = d.capabilities()
        if e.EV_ABS not in caps and e.EV_KEY not in caps:
            continue
        nbtn = len(caps.get(e.EV_KEY, []))
        axes = ", ".join(e.ABS.get(a[0] if isinstance(a, tuple) else a, "?") for a in caps.get(e.EV_ABS, []))
        print(f"{p}  {d.name.strip()}\n    by-id: {byid.get(os.path.realpath(p), '-')}\n    buttons: {nbtn}  axes: {axes or '-'}")


def normalise(ai, value, deadzone):
    """Axis value -> -1..1 with the deadzone removed."""
    mid = (ai.min + ai.max) / 2
    n = (value - mid) / ((ai.max - ai.min) / 2)
    if abs(n) < deadzone:
        return 0.0
    return (abs(n) - deadzone) / (1 - deadzone) * (1 if n > 0 else -1)


async def run(args):
    settings = load_settings()
    cfgpath = args.config or settings.get("cfg") or die("no JoyToKey .cfg given (use --config FILE)")
    try:
        cfg = parse(cfgpath)
    except (OSError, ValueError) as ex:
        die(f"cannot read {cfgpath}: {ex}")
    specs = args.joysticks.split(",") if args.joysticks else settings.get("joysticks") or die("settings define no 'joysticks'")
    for w in cfg.warnings:
        print(f"warning: {w}", file=sys.stderr)

    devs = {}
    def dev(joy):
        if joy not in devs:
            if joy > len(specs):
                die(f"{cfgpath} uses Joystick {joy} but only {len(specs)} device(s) are configured")
            devs[joy] = open_device(specs[joy - 1], joy)
        return devs[joy]

    keys = {key_code(k) for b in cfg.buttons.values() for k in b.keys}
    wheel_used = any(b.wheel for b in cfg.buttons.values())
    caps = {e.EV_KEY: sorted(keys)} if keys else {}
    rel = ([e.REL_X, e.REL_Y] if cfg.axes else []) + ([e.REL_WHEEL] if wheel_used else [])
    if rel:
        caps[e.EV_REL] = rel
    ui = UInput(caps, name="joytokey")

    joys = {j for j, _ in cfg.buttons} | {j for j, _ in cfg.axes}
    if args.monitor:   # watch every configured device so button/axis numbers can be discovered
        joys |= set(range(1, len(specs) + 1))
    if not joys:
        die(f"{cfgpath} defines no button or axis actions")

    axis_value = {}    # (joystick, axis number) -> -1..1
    held_wheel = set()

    def watch(joy):
        d = dev(joy)
        buttons = button_index_map(d)
        axis_numbers = axis_index_map(d)
        infos = {c: d.absinfo(c) for c in axis_numbers}
        async def _watch():
            async for ev in d.async_read_loop():
                if ev.type == e.EV_ABS:
                    n = axis_numbers.get(ev.code)
                    if args.monitor:
                        print(f"Joystick {joy} axis {n} ({e.ABS.get(ev.code)}) {ev.value}")
                    if (joy, n) in cfg.axes:
                        axis_value[(joy, n)] = normalise(infos[ev.code], ev.value, cfg.deadzones[joy])
                elif ev.type == e.EV_KEY and ev.value != 2:
                    n = buttons.get(ev.code)
                    if args.monitor:
                        print(f"Joystick {joy} button {n} {'down' if ev.value else 'up'}")
                    press(cfg.buttons.get((joy, n)), ev.value)
        return _watch()

    def press(b, value):
        if not b:
            return
        ks = [key_code(k) for k in b.keys]
        for k in (ks if value else reversed(ks)):
            ui.write(e.EV_KEY, k, value)
        if ks:
            ui.syn()
        if b.wheel:
            (held_wheel.add if value else held_wheel.discard)(b.wheel)

    async def mouse_loop():
        rx = ry = 0.0
        while True:
            await asyncio.sleep(1 / MOUSE_HZ)
            dx = dy = 0.0
            for key, v in axis_value.items():
                vx, vy = cfg.axes[key].get("p" if v > 0 else "n", (0, 0))
                dx += vx * abs(v)
                dy += vy * abs(v)
            rx += dx * MOUSE_PX_PER_SEC_PER_PERCENT / MOUSE_HZ
            ry += dy * MOUSE_PX_PER_SEC_PER_PERCENT / MOUSE_HZ
            ix, iy = int(rx), int(ry)
            rx -= ix; ry -= iy
            if ix: ui.write(e.EV_REL, e.REL_X, ix)
            if iy: ui.write(e.EV_REL, e.REL_Y, iy)
            if ix or iy: ui.syn()

    async def wheel_loop():
        while True:
            await asyncio.sleep(1 / WHEEL_HZ)
            for d in list(held_wheel):
                ui.write(e.EV_REL, e.REL_WHEEL, d); ui.syn()

    tasks = [watch(j) for j in sorted(joys)]
    if cfg.axes:
        tasks.append(mouse_loop())
    if wheel_used:
        tasks.append(wheel_loop())

    print(f"config: {cfgpath}", flush=True)
    for j in sorted(joys):
        print(f"Joystick {j}: {dev(j).name.strip()} ({dev(j).path})", flush=True)
    await asyncio.gather(*tasks)


def main():
    ap = argparse.ArgumentParser(
        description="Linux replacement for JoyToKey. Runs an original JoyToKey .cfg: reads joysticks via evdev "
                    "(without grabbing them) and emits keyboard/mouse events through a uinput device named 'joytokey'.",
        epilog="Which device is 'Joystick N' comes from `joysticks` in ~/.config/joytokey/config.toml "
               "(or $JOYTOKEY_CONFIG, or the bundled profiles/vkb-gladiator-nxt.toml), or --joysticks. "
               "Normally run via with-joytokey --config FILE <command>, which stops the daemon when the command exits.")
    ap.add_argument("--config", metavar="FILE", help="JoyToKey .cfg to run (overrides `cfg` in the settings file)")
    ap.add_argument("--joysticks", metavar="DEV,DEV", help="devices for Joystick 1, 2, ... (overrides the settings file)")
    ap.add_argument("--monitor", action="store_true", help="print raw axis/button events (for finding button and axis numbers)")
    ap.add_argument("--list-devices", action="store_true", help="list joystick-like input devices and exit")
    args = ap.parse_args()
    if args.list_devices:
        return list_devices_cmd()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
