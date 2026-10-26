# tests/test_sensor.py
import pytest
from flydigi_bs2_controller.core.sensor import HardwareSensor

def test_sensor_fallback_and_range():
    sensor = HardwareSensor(start_background_thread=False)
    cpu_temp, gpu_temp = sensor.get_temperatures()
    assert isinstance(cpu_temp, (int, float))
    assert isinstance(gpu_temp, (int, float))
    eff_temp = sensor.get_effective_temp()
    assert isinstance(eff_temp, (int, float))
    assert 20.0 <= eff_temp <= 115.0

def test_sensor_effective_max():
    sensor = HardwareSensor(start_background_thread=False)
    sensor._cached_cpu = 45.0
    sensor._cached_gpu = 62.0
    assert sensor.get_effective_temp() == 62.0

    sensor._cached_cpu = 78.0
    sensor._cached_gpu = 55.0
    assert sensor.get_effective_temp() == 78.0

def test_sensor_gpu_zero_resets_cached():
    """Verify Critical Finding 3: GPU returning 0.0 resets cached GPU to 0.0 without sticking to 40.0."""
    sensor = HardwareSensor(start_background_thread=False)
    # Simulate GPU missing / asleep and fixed CPU
    sensor._has_nvidia = False
    sensor._query_cpu_thermal_zone = lambda: 32.0
    sensor._cached_gpu = 40.0
    sensor.update()
    assert sensor._cached_gpu == 0.0
    assert sensor._cached_cpu == 32.0
    assert sensor.get_effective_temp() == 32.0
