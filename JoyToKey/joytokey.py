#!/usr/bin/env python3
"""Linux replacement for JoyToKey: maps joystick buttons/axes to keyboard and mouse events.

Reads joysticks via evdev WITHOUT grabbing them (games still see the real devices) and emits
keyboard / mouse events through a uinput virtual device named 'joytokey'.

What gets mapped is defined by a TOML profile (see profiles/vkb-gladiator-nxt.toml):
which devices to read, an optional stick that moves the mouse, and button -> key/wheel actions.
"""
import argparse, asyncio, glob, os, sys, tomllib
from evdev import InputDevice, UInput, ecodes as e, list_devices

HERE = os.path.dirname(os.path.realpath(__file__))
USER_CONFIG = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "joytokey", "config.toml")
DEFAULT_PROFILE = os.path.join(HERE, "profiles", "vkb-gladiator-nxt.toml")


def die(msg):
    sys.exit(f"joytokey: {msg}")


def code(name, prefixes):
    """Resolve an evdev name like 'KEY_R', 'ABS_RX' or 'BTN_LEFT' to its numeric code."""
    if not any(name.startswith(p) for p in prefixes):
        die(f"'{name}' must start with one of {', '.join(prefixes)}")
    c = getattr(e, name, None)
    if not isinstance(c, int):
        die(f"unknown evdev name '{name}'")
    return c


def find_config(path):
    for p in (path, os.environ.get("JOYTOKEY_CONFIG"), USER_CONFIG, DEFAULT_PROFILE):
        if p and os.path.isfile(p):
            return p
    die("no profile found (use --config FILE)")


def load_config(path):
    try:
        with open(path, "rb") as f:
            cfg = tomllib.load(f)
    except (OSError, tomllib.TOMLDecodeError) as ex:
        die(f"cannot read {path}: {ex}")
    roles = cfg.get("devices") or die(f"{path}: missing [devices]")
    for b in cfg.get("button", []):
        if b.get("device") not in roles:
            die(f"{path}: button {b.get('number')} uses unknown device role '{b.get('device')}'")
        if "number" not in b or not ("keys" in b or "wheel" in b):
            die(f"{path}: each [[button]] needs 'number' and 'keys' and/or 'wheel'")
    m = cfg.get("mouse")
    if m and m.get("device") not in roles:
        die(f"{path}: [mouse] uses unknown device role '{m.get('device')}'")
    return cfg


def open_device(spec, role):
    if spec.startswith("name:"):
        want = spec[5:].lower()
        matches = [p for p in list_devices() if want in InputDevice(p).name.lower()]
    elif spec.startswith("/"):
        matches = [spec] if os.path.exists(spec) else []
    else:
        matches = sorted(glob.glob(f"/dev/input/by-id/{spec}"))
    if not matches:
        die(f"device for role '{role}' ({spec}) not found; run with --list-devices")
    return InputDevice(matches[0])


def button_index_map(dev):
    """evdev button code -> 1-based button number (Nth button in sorted code order)."""
    codes = sorted(dev.capabilities().get(e.EV_KEY, []))
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


async def run(args):
    cfgpath = find_config(args.config)
    cfg = load_config(cfgpath)
    roles = dict(cfg["devices"])
    if args.mirrored:
        names = list(roles)[:2]
        if len(names) < 2:
            die("--mirrored needs two roles in [devices]")
        roles[names[0]], roles[names[1]] = roles[names[1]], roles[names[0]]
    devs = {}
    def dev(role):
        if role not in devs:
            devs[role] = open_device(roles[role], role)
        return devs[role]

    mcfg = cfg.get("mouse")
    wcfg = cfg.get("wheel", {})
    buttons = cfg.get("button", [])

    keys = {code(k, ("KEY_", "BTN_")) for b in buttons for k in b.get("keys", [])}
    caps = {e.EV_KEY: sorted(keys)} if keys else {}
    rel = []
    if mcfg:
        rel += [e.REL_X, e.REL_Y]
    if any("wheel" in b for b in buttons):
        rel.append(e.REL_WHEEL)
    if rel:
        caps[e.EV_REL] = rel
    ui = UInput(caps, name="joytokey")

    tasks = []
    state = {"x": 0.0, "y": 0.0}
    held_wheel = set()

    if mcfg:
        mdev = dev(mcfg["device"])
        ax = code(mcfg.get("x_axis", "ABS_RX"), ("ABS_",))
        ay = code(mcfg.get("y_axis", "ABS_RY"), ("ABS_",))
        dz = float(mcfg.get("deadzone", 0.2))
        speed = float(mcfg.get("speed", 600))
        hz = float(mcfg.get("hz", 100))
        sx = -1 if mcfg.get("invert_x", False) else 1
        sy = -1 if mcfg.get("invert_y", False) else 1
        info = {ax: mdev.absinfo(ax), ay: mdev.absinfo(ay)}

        def norm(ai, v):
            mid = (ai.min + ai.max) / 2
            n = (v - mid) / ((ai.max - ai.min) / 2)
            if abs(n) < dz:
                return 0.0
            return (abs(n) - dz) / (1 - dz) * (1 if n > 0 else -1)

        async def watch_axes():
            async for ev in mdev.async_read_loop():
                if ev.type != e.EV_ABS:
                    continue
                if ev.code == ax:
                    state["x"] = norm(info[ax], ev.value)
                elif ev.code == ay:
                    state["y"] = norm(info[ay], ev.value)
                if args.monitor:
                    print(mcfg["device"], e.ABS.get(ev.code), ev.value)

        async def mouse_loop():
            rx = ry = 0.0
            while True:
                await asyncio.sleep(1 / hz)
                rx += sx * state["x"] * speed / hz
                ry += sy * state["y"] * speed / hz
                ix, iy = int(rx), int(ry)
                rx -= ix; ry -= iy
                if ix: ui.write(e.EV_REL, e.REL_X, ix)
                if iy: ui.write(e.EV_REL, e.REL_Y, iy)
                if ix or iy: ui.syn()

        tasks += [watch_axes(), mouse_loop()]

    # group button actions per device role
    by_role = {}
    for b in buttons:
        by_role.setdefault(b["device"], {})[int(b["number"])] = b
    if args.monitor:   # in monitor mode also watch every configured role so button numbers can be discovered
        for r in roles:
            by_role.setdefault(r, {})

    def watch_buttons(role, actions):
        d = dev(role)
        idx = button_index_map(d)
        async def _watch():
            async for ev in d.async_read_loop():
                if ev.type != e.EV_KEY or ev.value == 2:
                    continue
                n = idx.get(ev.code)
                if args.monitor:
                    print(role, "button", n, "down" if ev.value else "up")
                b = actions.get(n)
                if not b:
                    continue
                ks = [code(k, ("KEY_", "BTN_")) for k in b.get("keys", [])]
                for k in (ks if ev.value else reversed(ks)):
                    ui.write(e.EV_KEY, k, ev.value)
                if ks:
                    ui.syn()
                if "wheel" in b:
                    (held_wheel.add if ev.value else held_wheel.discard)(int(b["wheel"]))
        return _watch()

    for role, actions in by_role.items():
        tasks.append(watch_buttons(role, actions))

    if any("wheel" in b for b in buttons):
        whz = float(wcfg.get("hz", 10))
        async def wheel_loop():
            while True:
                await asyncio.sleep(1 / whz)
                for d in list(held_wheel):
                    ui.write(e.EV_REL, e.REL_WHEEL, d); ui.syn()
        tasks.append(wheel_loop())

    print(f"profile: {cfgpath}", flush=True)
    for r in sorted(set(devs) | set(by_role)):
        d = dev(r)
        print(f"{r}: {d.name.strip()} ({d.path})", flush=True)
    if not tasks:
        die("profile defines no [mouse] or [[button]] actions")
    await asyncio.gather(*tasks)


def main():
    ap = argparse.ArgumentParser(
        description="Linux replacement for JoyToKey. Reads joysticks via evdev (without grabbing them) and "
                    "emits keyboard/mouse events through a uinput device named 'joytokey'. "
                    "Behaviour comes from a TOML profile.",
        epilog="Profile lookup: --config FILE, $JOYTOKEY_CONFIG, ~/.config/joytokey/config.toml, then the bundled "
               "profiles/vkb-gladiator-nxt.toml. "
               "Normally run via with-joytokey [--config FILE] [--mirrored] <command>, which stops the daemon "
               "when the command exits.")
    ap.add_argument("--config", metavar="FILE", help="profile to use (TOML)")
    ap.add_argument("--mirrored", action="store_true", help="swap the first two [devices] roles (left <-> right)")
    ap.add_argument("--monitor", action="store_true", help="print raw axis/button events (for finding button numbers and axis names)")
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
