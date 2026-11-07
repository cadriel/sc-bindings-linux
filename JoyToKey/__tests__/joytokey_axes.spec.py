import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from evdev import ecodes as e  # noqa: E402
from joytokey import axis_numbers_for  # noqa: E402

# Axes reported by a VKB Gladiator NXT EVO (twist = Rz, ministick = Rx/Ry).
VKB_NXT = [e.ABS_X, e.ABS_Y, e.ABS_Z, e.ABS_RX, e.ABS_RY, e.ABS_RZ, e.ABS_HAT0X, e.ABS_HAT0Y]


class AxisNumbers(unittest.TestCase):
    def test_joytokey_order_x_y_z_r_u_v(self):
        n = axis_numbers_for(VKB_NXT)
        self.assertEqual([n[c] for c in (e.ABS_X, e.ABS_Y, e.ABS_Z, e.ABS_RZ, e.ABS_RX, e.ABS_RY)], [1, 2, 3, 4, 5, 6])

    def test_twist_is_not_axis_5_or_6(self):
        n = axis_numbers_for(VKB_NXT)
        self.assertEqual(n[e.ABS_RZ], 4)
        self.assertEqual((n[e.ABS_RX], n[e.ABS_RY]), (5, 6))   # ministick = Axis5/6 (U/V)

    def test_other_axes_follow_in_code_order(self):
        n = axis_numbers_for(VKB_NXT)
        self.assertEqual((n[e.ABS_HAT0X], n[e.ABS_HAT0Y]), (7, 8))

    def test_slots_are_fixed_when_axes_are_missing(self):
        n = axis_numbers_for([e.ABS_X, e.ABS_Y, e.ABS_RX])
        self.assertEqual(n, {e.ABS_X: 1, e.ABS_Y: 2, e.ABS_RX: 5})


if __name__ == "__main__":
    unittest.main()
