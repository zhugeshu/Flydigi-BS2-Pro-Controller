# tests/test_curve_engine.py
import pytest
from flydigi_bs2_controller.core.curve_engine import CurveEngine

def test_preset_silent_curve():
    engine = CurveEngine()
    engine.set_power_mode(3)  # 20V, max 4000
    engine.set_mode("silent")
    # Low temp <= 30°C should be minimum 1300 RPM
    assert engine.calculate_target_rpm(25.0) == 1300
    assert engine.calculate_target_rpm(30.0) == 1300
    # Intermediate temp (e.g. 50°C)
    assert 1500 <= engine.calculate_target_rpm(50.0) <= 2500
    # High temp >= 80°C
    assert engine.calculate_target_rpm(85.0) >= 3000

def test_preset_performance_curve():
    engine = CurveEngine()
    engine.set_power_mode(3)  # 20V, max 4000
    engine.set_mode("performance")
    assert engine.calculate_target_rpm(30.0) >= 1300
    # Performance curve at 80°C+ reaches 4000 RPM
    assert engine.calculate_target_rpm(90.0) == 4000

def test_power_mode_clamping():
    engine = CurveEngine()
    # 5V mode: Max 2700 RPM
    engine.set_power_mode(1)
    engine.set_mode("performance")
    assert engine.calculate_target_rpm(100.0) == 2700

    # 9V mode: Max 3300 RPM
    engine.set_power_mode(2)
    assert engine.calculate_target_rpm(100.0) == 3300

def test_custom_curve():
    engine = CurveEngine()
    engine.set_power_mode(3)
    custom = [
        [30, 1500],
        [50, 2500],
        [80, 3500],
        [100, 4000],
    ]
    engine.set_custom_curve(custom)
    engine.set_mode("custom")
    # Exact point
    assert engine.calculate_target_rpm(50.0) == 2500
    # Interpolation at 40°C (halfway between 30 and 50) -> 2000 RPM
    assert engine.calculate_target_rpm(40.0) == 2000

def test_hysteresis_smoothing():
    engine = CurveEngine(hysteresis=2.0)
    engine.set_mode("performance")
    engine.set_power_mode(3)

    rpm1 = engine.calculate_smooth_rpm(70.0)
    # Temp drops by 1°C (within 2°C hysteresis deadband) -> RPM should NOT drop
    rpm2 = engine.calculate_smooth_rpm(69.0)
    assert rpm2 == rpm1

    # Temp rises -> RPM responds immediately
    rpm3 = engine.calculate_smooth_rpm(75.0)
    assert rpm3 > rpm1

    # Temp drops by 4°C (> 2°C deadband) -> RPM should now drop
    rpm4 = engine.calculate_smooth_rpm(65.0)
    assert rpm4 < rpm3
