"""Reader for original JoyToKey .cfg files (the INI-style files JoyToKey saves).

Supports the subset used for keyboard/mouse output:
  ButtonNN = 1, <VK>:<VK>:<VK>:<VK>, ...   keys pressed together (hex Windows virtual-key codes)
  ButtonNN = 2, x, y, wheel, ...           mouse wheel (sign of `wheel` gives the direction)
  AxisNn / AxisNp = 2, x, y, ...           mouse movement (percent of full speed) for that axis direction
Anything else is skipped and reported in the returned warnings. This module is pure Python (no evdev).
"""
import configparser
import re
from dataclasses import dataclass, field

# Windows virtual-key code -> evdev key name
VK_KEYS = {
    0x08: "KEY_BACKSPACE", 0x09: "KEY_TAB", 0x0D: "KEY_ENTER", 0x13: "KEY_PAUSE", 0x14: "KEY_CAPSLOCK",
    0x1B: "KEY_ESC", 0x20: "KEY_SPACE", 0x21: "KEY_PAGEUP", 0x22: "KEY_PAGEDOWN", 0x23: "KEY_END",
    0x24: "KEY_HOME", 0x25: "KEY_LEFT", 0x26: "KEY_UP", 0x27: "KEY_RIGHT", 0x28: "KEY_DOWN",
    0x2C: "KEY_SYSRQ", 0x2D: "KEY_INSERT", 0x2E: "KEY_DELETE",
    0x5B: "KEY_LEFTMETA", 0x5C: "KEY_RIGHTMETA", 0x5D: "KEY_COMPOSE",
    0x6A: "KEY_KPASTERISK", 0x6B: "KEY_KPPLUS", 0x6D: "KEY_KPMINUS", 0x6E: "KEY_KPDOT", 0x6F: "KEY_KPSLASH",
    0x90: "KEY_NUMLOCK", 0x91: "KEY_SCROLLLOCK",
    0x10: "KEY_LEFTSHIFT", 0x11: "KEY_LEFTCTRL", 0x12: "KEY_LEFTALT",
    0xA0: "KEY_LEFTSHIFT", 0xA1: "KEY_RIGHTSHIFT", 0xA2: "KEY_LEFTCTRL", 0xA3: "KEY_RIGHTCTRL",
    0xA4: "KEY_LEFTALT", 0xA5: "KEY_RIGHTALT",
    0xBA: "KEY_SEMICOLON", 0xBB: "KEY_EQUAL", 0xBC: "KEY_COMMA", 0xBD: "KEY_MINUS", 0xBE: "KEY_DOT",
    0xBF: "KEY_SLASH", 0xC0: "KEY_GRAVE", 0xDB: "KEY_LEFTBRACE", 0xDC: "KEY_BACKSLASH",
    0xDD: "KEY_RIGHTBRACE", 0xDE: "KEY_APOSTROPHE",
}
VK_KEYS.update({0x30 + i: f"KEY_{i}" for i in range(10)})
VK_KEYS.update({0x41 + i: f"KEY_{chr(0x41 + i)}" for i in range(26)})
VK_KEYS.update({0x60 + i: f"KEY_KP{i}" for i in range(10)})
VK_KEYS.update({0x70 + i: f"KEY_F{i + 1}" for i in range(12)})

DEFAULT_THRESHOLD = 20


@dataclass
class Button:
    keys: list = field(default_factory=list)   # evdev key names pressed together
    wheel: int = 0                             # +1 up, -1 down, 0 none


@dataclass
class JoyToKeyConfig:
    buttons: dict = field(default_factory=dict)     # (joystick, button number) -> Button
    axes: dict = field(default_factory=dict)        # (joystick, axis number) -> {"n": (x, y), "p": (x, y)}
    deadzones: dict = field(default_factory=dict)   # joystick -> fraction of full deflection ignored
    warnings: list = field(default_factory=list)


def _fields(value):
    return [f.strip() for f in value.split(",")]


def _parse_button(num, value, cfg, joy, warn):
    f = _fields(value)
    kind = int(f[0])
    if kind == 0:
        return
    if kind == 1:
        vks = [int(v, 16) for v in f[1].split(":") if int(v, 16)]
        if not vks:
            return
        unknown = [f"{v:02X}" for v in vks if v not in VK_KEYS]
        if unknown:
            return warn(f"Joystick {joy} Button{num:02d}: unsupported virtual-key code(s) {', '.join(unknown)}")
        cfg.buttons[(joy, num)] = Button(keys=[VK_KEYS[v] for v in vks])
    elif kind == 2 and int(f[3]):
        cfg.buttons[(joy, num)] = Button(wheel=1 if int(f[3]) > 0 else -1)
    else:
        warn(f"Joystick {joy} Button{num:02d}: unsupported action type {kind}")


def _parse_axis(num, direction, value, cfg, joy, warn):
    f = _fields(value)
    if int(f[0]) != 2:
        return warn(f"Joystick {joy} Axis{num}{direction}: only mouse-move actions are supported")
    cfg.axes.setdefault((joy, num), {})[direction] = (int(f[1]), int(f[2]))


def parse(path):
    """Read a JoyToKey .cfg into a JoyToKeyConfig."""
    cp = configparser.RawConfigParser(strict=False, delimiters=("=",), interpolation=None)
    cp.optionxform = str
    with open(path, encoding="utf-8-sig") as fh:
        cp.read_file(fh)

    cfg = JoyToKeyConfig()
    warn = cfg.warnings.append
    general = cp["General"] if cp.has_section("General") else {}
    for section in cp.sections():
        m = re.fullmatch(r"Joystick (\d+)", section)
        if not m:
            continue
        joy = int(m.group(1))
        threshold = int(general.get("Threshold" if joy == 1 else "Threshold2", DEFAULT_THRESHOLD))
        cfg.deadzones[joy] = threshold / 100
        for name, value in cp[section].items():
            if b := re.fullmatch(r"Button(\d+)", name):
                _parse_button(int(b.group(1)), value, cfg, joy, warn)
            elif a := re.fullmatch(r"Axis(\d+)([np])", name):
                _parse_axis(int(a.group(1)), a.group(2), value, cfg, joy, warn)
            elif name.startswith("POV") and _fields(value)[0] != "0":
                warn(f"Joystick {joy} {name}: POV hats are not supported")
    return cfg
