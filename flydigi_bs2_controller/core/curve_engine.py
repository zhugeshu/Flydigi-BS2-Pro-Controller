# flydigi_bs2_controller/core/curve_engine.py
"""
Temperature-to-RPM curve interpolation and smoothing engine.
Incorporates Flydigi BS2 Pro presets, power limit clamping, and hysteresis filtering.
"""

from typing import List, Tuple

SILENT_PRESET_20V: List[List[int]] = [
    [30, 1300],
    [40, 1300],
    [50, 1500],
    [60, 1800],
    [70, 2200],
    [80, 2600],
    [90, 3000],
    [100, 3200],
]

PERFORMANCE_PRESET_20V: List[List[int]] = [
    [30, 1800],
    [40, 2000],
    [50, 2500],
    [60, 3100],
    [70, 3600],
    [80, 4000],
    [90, 4000],
    [100, 4000],
]

POWER_LIMITS = {
    1: 2700,  # 5V standard power
    2: 3300,  # 9V fast charge
    3: 4000,  # 20V PD fast charge
}


class CurveEngine:
    def __init__(self, hysteresis: float = 2.0):
        self.mode = "silent"  # "silent" | "performance" | "custom"
        self.power_mode = 3   # Default to 20V (max 4000)
        self.max_rpm_cap = POWER_LIMITS[3]
        self.min_rpm = 1300
        self.custom_points: List[List[int]] = [list(p) for p in PERFORMANCE_PRESET_20V]

        self.hysteresis = hysteresis
        self.last_effective_temp: float = 0.0
        self.last_smooth_rpm: int = self.min_rpm

    def set_power_mode(self, mode: int) -> None:
        """Set fast charge power mode (1=5V, 2=9V, 3=20V). Clamps maximum RPM."""
        self.power_mode = mode
        self.max_rpm_cap = POWER_LIMITS.get(mode, 4000)
        self.reset_hysteresis()

    def set_mode(self, mode: str) -> None:
        """Set curve mode: 'silent', 'performance', or 'custom'."""
        self.mode = mode.lower()
        self.reset_hysteresis()

    def get_active_curve_points(self) -> List[List[int]]:
        """Return the active 8-point curve points for the current mode."""
        if self.mode == "silent":
            return [list(p) for p in SILENT_PRESET_20V]
        elif self.mode == "performance":
            return [list(p) for p in PERFORMANCE_PRESET_20V]
        else:
            return [list(p) for p in self.custom_points]

    def set_custom_curve(self, points: List[List[int]]) -> None:
        """Set custom curve points, sorted by temperature."""
        self.custom_points = sorted([list(p) for p in points], key=lambda x: x[0])
        self.reset_hysteresis()

    def reset_hysteresis(self) -> None:
        """Reset hysteresis state so new curve/power mode takes effect immediately."""
        self.last_effective_temp = 0.0

    def _get_active_points(self) -> List[List[int]]:
        if self.mode == "performance":
            return PERFORMANCE_PRESET_20V
        elif self.mode == "custom":
            return self.custom_points
        else:
            return SILENT_PRESET_20V

    def calculate_target_rpm(self, temp: float) -> int:
        """
        Calculate raw target RPM using piecewise linear interpolation on the active curve.
        Result is clamped between [min_rpm, max_rpm_cap].
        """
        points = self._get_active_points()
        if not points:
            return self.min_rpm

        # If temperature is below or equal to first point
        if temp <= points[0][0]:
            raw_rpm = points[0][1]
        # If temperature is above or equal to last point
        elif temp >= points[-1][0]:
            raw_rpm = points[-1][1]
        else:
            # Linear interpolation between adjacent points
            raw_rpm = points[0][1]
            for i in range(len(points) - 1):
                t1, r1 = points[i]
                t2, r2 = points[i + 1]
                if t1 <= temp <= t2:
                    ratio = (temp - t1) / float(t2 - t1)
                    raw_rpm = int(r1 + ratio * (r2 - r1))
                    break

        # Clamp between min_rpm and power limit cap
        clamped_rpm = max(self.min_rpm, min(self.max_rpm_cap, raw_rpm))
        return clamped_rpm

    def calculate_smooth_rpm(self, current_temp: float) -> int:
        """
        Calculate target RPM with hysteresis filtering to prevent fan hunting.
        - Rises immediately on heating.
        - On cooling, requires temperature to drop by at least `self.hysteresis` degrees before lowering RPM.
        """
        if self.last_effective_temp == 0.0:
            self.last_effective_temp = current_temp
            self.last_smooth_rpm = self.calculate_target_rpm(current_temp)
            return self.last_smooth_rpm

        # If temperature is rising
        if current_temp > self.last_effective_temp:
            self.last_effective_temp = current_temp
            self.last_smooth_rpm = self.calculate_target_rpm(current_temp)
        # If temperature dropped beyond the hysteresis deadband
        elif current_temp < (self.last_effective_temp - self.hysteresis):
            self.last_effective_temp = current_temp
            self.last_smooth_rpm = self.calculate_target_rpm(current_temp)
        # Otherwise, temperature is within deadband: keep previous RPM

        return self.last_smooth_rpm
