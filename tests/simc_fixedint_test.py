import unittest

from server.simc_fixedint import MutableUInt32


class SimcFixedIntTest(unittest.TestCase):
    def test_uint32_wraps_arithmetic_and_bitwise_operations(self):
        value = MutableUInt32(0xFFFFFFFF)

        self.assertEqual(int(value + 1), 0)
        value += 2
        self.assertEqual(int(value), 1)
        value ^= MutableUInt32(0xFFFFFFFF)
        self.assertEqual(int(value), 0xFFFFFFFE)

    def test_uint32_shifts_support_salsa20_rotation(self):
        value = MutableUInt32(0x80000001)

        rotated = (value << 1) | (value >> 31)

        self.assertEqual(int(value << 1), 0x00000002)
        self.assertEqual(int(value >> 31), 0x00000001)
        self.assertEqual(int(rotated), 0x00000003)

    def test_uint32_copies_and_uses_little_endian_bytes(self):
        original = MutableUInt32.from_bytes(
            b"\x78\x56\x34\x12ignored",
            "little",
        )
        copied = MutableUInt32(original)

        original += 1

        self.assertEqual(int(copied), 0x12345678)
        self.assertEqual(
            copied.to_bytes(4, "little"),
            b"\x78\x56\x34\x12",
        )


if __name__ == "__main__":
    unittest.main()
