"""Fast, network-free tests for ORCA's core decision rules."""

import unittest

from main import resolve_location
from server import assess
from core.tools import detect_lang, hav


class LocationTests(unittest.TestCase):
    def test_known_city_is_resolved(self):
        name, latitude, longitude = resolve_location("conditions near Chennai")
        self.assertEqual(name, "Chennai")
        self.assertAlmostEqual(latitude, 13.05)
        self.assertAlmostEqual(longitude, 80.35)

    def test_custom_coordinates_are_resolved(self):
        name, latitude, longitude = resolve_location("lat 18.90 lon 72.70")
        self.assertEqual(name, "Custom location")
        self.assertEqual((latitude, longitude), (18.90, 72.70))


class SafetyAssessmentTests(unittest.TestCase):
    def test_low_conditions_are_marked_safe(self):
        self.assertEqual(assess(0.7, 12)["level"], "safe")

    def test_caution_threshold_is_applied(self):
        self.assertEqual(assess(1.6, 12)["level"], "caution")
        self.assertEqual(assess(0.7, 31)["level"], "caution")

    def test_high_threshold_is_applied(self):
        self.assertEqual(assess(2.6, 12)["level"], "high")
        self.assertEqual(assess(0.7, 46)["level"], "high")


class UtilityTests(unittest.TestCase):
    def test_marathi_script_is_detected(self):
        self.assertEqual(detect_lang("मुंबईमध्ये हवामान कसे आहे?"), "Hindi/Marathi")

    def test_haversine_distance_is_zero_for_same_point(self):
        self.assertAlmostEqual(hav(18.9, 72.7, 18.9, 72.7), 0.0)


if __name__ == "__main__":
    unittest.main()
