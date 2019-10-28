import unittest
from acremote import vestel


class TestVestelACRemote(unittest.TestCase):
    def setUp(self):
        pass

    def test_form_octet_small(self):
        """
        When input number binary representation is less than 8 digits long
        """
        testobj = vestel.VestelACRemote()
        self.assertEqual(testobj.form_octet(69), '01000101')

    def test_form_octet_exact(self):
        """
        When input number binary representation is exactly 8 digits long
        """
        testobj = vestel.VestelACRemote()
        self.assertEqual(testobj.form_octet(192), '11000000')

    def test_form_octet_big(self):
        """
        When input number binary representation is more than 8 digits long
        """
        testobj = vestel.VestelACRemote()
        self.assertEqual(testobj.form_octet(420), '10100100')

    def test_form_bin_str_default(self):
        """
        Default values:
        {
            '_HEALTH': False,
            '_SCREEN': True,
            '_ON': False,
            '_TIMER': 0.0,
            '_TEMP': 27,
            '_SPEED': 'HIGH',
            '_SLEEP': False,
            '_CLEAN': False,
            '_FRESH': False,
            '_SWING': True,
            '_MODE': 'COOL',
            '_FEELING': False,
            '_STRONG': False}
        """
        testobj = vestel.VestelACRemote()
        self.assertEqual(
            testobj._form_bin_str(),
            '11000011000000000000011100000000000000000000000000000000000000000000000000000000000000000000000011000101'
        )

    def test_form_bin_str_custom(self):
        testobj = vestel.VestelACRemote()
        testobj.on = True
        testobj.temp = 20
        testobj.speed = 'LOW'
        testobj.swing = False
        testobj.mode = 'HEAT'
        testobj.strong = True
        testobj.timer = 1.5
        testobj._refresh_data_fields()
        self.assertEqual(
            testobj._form_bin_str(),
            '11000011111001100000011100000000100001100111101000000001000000000000000000000110000000000000000010010101'
        )
