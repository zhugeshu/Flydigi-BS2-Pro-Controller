# tests/test_curve_engine.py
import pytest
from flydigi_bs2_controller.core.curve_engine import CurveEngine

def test_preset_silent_curve():
    engine = CurveEngine()
    engine.set_power_mode(3)  # 20V, max 4000
    engine.set_mode("silent")
    assert engine.calculate_target_rpm(25.0) == 1300
    assert engine.calculate_target_rpm(30.0) == 1300
    assert 1500 <= engine.calculate_target_rpm(50.0) <= 2500
    assert engine.calculate_target_rpm(85.0) >= 3000

def test_preset_performance_curve():
    engine = CurveEngine()
    engine.set_power_mode(3)  # 20V, max 4000
    engine.set_mode("performance")
    assert engine.calculate_target_rpm(30.0) >= 1300
    assert engine.calculate_target_rpm(90.0) == 4000

def test_power_mode_clamping():
    engine = CurveEngine()
    engine.set_power_mode(1)
    engine.set_mode("performance")
    assert engine.calculate_target_rpm(100.0) == 2700

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
    assert engine.calculate_target_rpm(50.0) == 2500
    assert engine.calculate_target_rpm(40.0) == 2000

def test_hysteresis_smoothing():
    engine = CurveEngine(hysteresis=2.0)
    engine.set_mode("performance")
    engine.set_power_mode(3)

    rpm1 = engine.calculate_smooth_rpm(70.0)
    rpm2 = engine.calculate_smooth_rpm(69.0)
    assert rpm2 == rpm1

    rpm3 = engine.calculate_smooth_rpm(75.0)
    assert rpm3 > rpm1

    rpm4 = engine.calculate_smooth_rpm(65.0)
    assert rpm4 < rpm3

def test_hysteresis_reset_on_mode_change():
    """Verify Important Finding 6: Switching mode resets hysteresis deadband immediately."""
    engine = CurveEngine(hysteresis=2.0)
    engine.set_power_mode(3)
    engine.set_mode("silent")
    silent_rpm = engine.calculate_smooth_rpm(60.0)

    # Switch to performance at same temperature
    engine.set_mode("performance")
    perf_rpm = engine.calculate_smooth_rpm(60.0)
    # Performance RPM at 60°C is 2700, while Silent RPM at 60°C is 2100
    assert perf_rpm > silent_rpm
