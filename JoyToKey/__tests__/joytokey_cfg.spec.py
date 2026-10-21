import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from joytokey_cfg import parse  # noqa: E402

DUAL = os.path.join(HERE, "..", "..", "DualVKB")


def parse_text(text):
    with tempfile.NamedTemporaryFile("w", suffix=".cfg", delete=False, encoding="utf-8-sig", newline="") as f:
        f.write(text.replace("\n", "\r\n"))
    try:
        return parse(f.name)
    finally:
        os.unlink(f.name)


class ParseRealConfigs(unittest.TestCase):
    def test_dual_vkb(self):
        cfg = parse(os.path.join(DUAL, "JoyToKey Dual VKB 4.10.cfg"))
        self.assertEqual(cfg.warnings, [])
        self.assertEqual(cfg.deadzones, {1: 0.2, 2: 0.2})
        self.assertEqual(cfg.buttons[(2, 3)].keys, ["KEY_R"])
        self.assertEqual(cfg.buttons[(2, 5)].keys, ["KEY_RIGHTCTRL", "KEY_F4"])
        self.assertEqual(cfg.buttons[(2, 16)].wheel, 1)
        self.assertEqual(cfg.buttons[(2, 18)].wheel, -1)
        self.assertEqual(cfg.axes[(1, 5)], {"n": (-100, 0), "p": (100, 0)})
        self.assertEqual(cfg.axes[(1, 6)], {"n": (0, 100), "p": (0, -100)})

    def test_mirrored_swaps_joysticks(self):
        cfg = parse(os.path.join(DUAL, "JoyToKey Dual VKB Mirrored 4.10.cfg"))
        self.assertEqual({j for j, _ in cfg.buttons}, {1})
        self.assertEqual({j for j, _ in cfg.axes}, {2})


class ParseEdgeCases(unittest.TestCase):
    def test_unsupported_lines_warn_instead_of_failing(self):
        cfg = parse_text("[General]\n[Joystick 1]\nButton01=1, 00:00:00:00, 0\nButton02=1, FF:00:00:00, 0\n"
                         "Button03=3, 0, 0\nAxis1n=1, 41:00:00:00\nPOV1=1, 41:00:00:00\n")
        self.assertEqual(cfg.buttons, {})
        self.assertEqual(len(cfg.warnings), 4)

    def test_default_threshold_when_missing(self):
        self.assertEqual(parse_text("[Joystick 1]\n").deadzones, {1: 0.2})


if __name__ == "__main__":
    unittest.main()
