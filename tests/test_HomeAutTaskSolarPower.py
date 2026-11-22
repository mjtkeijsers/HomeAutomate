import logging
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import HomeAutTaskSolarPower as solar_power


class SolarPowerTaskTests(unittest.TestCase):
    def setUp(self):
        solar_power._solar_power_active = False
        solar_power._consecutive_readings = 0

    def run_power(self, power):
        with patch.object(solar_power, "safe_request", return_value=SimpleNamespace(text="response")):
            with patch.object(solar_power, "parse_youless_response", return_value={"pwr": power}):
                solar_power.solar_power_task()

    def test_requires_three_readings_and_rearms_after_recovery(self):
        with self.assertLogs("HomeAutTaskSolarPower", level=logging.DEBUG) as captured:
            self.run_power(-1)
            self.run_power(-1)
            self.assertFalse(any("solar power active" in line for line in captured.output))
            self.run_power(-1)
            self.run_power(-1)
            self.assertEqual(
                sum("solar power active, can switch on heat pump" in line for line in captured.output),
                1,
            )

            self.run_power(1)
            self.run_power(1)
            self.assertFalse(any("solar power inactive" in line for line in captured.output))
            self.run_power(1)
            self.assertTrue(any("solar power inactive, switch back setpoint" in line for line in captured.output))

            self.run_power(-1)
            self.run_power(-1)
            self.run_power(-1)
            self.assertEqual(
                sum("solar power active, can switch on heat pump" in line for line in captured.output),
                2,
            )

    def test_zero_reading_breaks_negative_streak(self):
        with self.assertLogs("HomeAutTaskSolarPower", level=logging.DEBUG) as captured:
            self.run_power(-1)
            self.run_power(-1)
            self.run_power(0)
            self.run_power(-1)
            self.run_power(-1)
            self.assertFalse(any("solar power active" in line for line in captured.output))
            self.run_power(-1)
            self.assertTrue(any("solar power active, can switch on heat pump" in line for line in captured.output))


if __name__ == "__main__":
    unittest.main()
