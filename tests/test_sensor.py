# tests/test_sensor.py
import pytest
from flydigi_bs2_controller.core.sensor import HardwareSensor

def test_sensor_fallback_and_range():
    sensor = HardwareSensor()
    cpu_temp, gpu_temp = sensor.get_temperatures()
    assert isinstance(cpu_temp, (int, float))
    assert isinstance(gpu_temp, (int, float))
    eff_temp = sensor.get_effective_temp()
    assert isinstance(eff_temp, (int, float))
    assert 20.0 <= eff_temp <= 115.0

def test_sensor_effective_max():
    sensor = HardwareSensor()
    # Mocking temperatures to test max logic
    sensor._cached_cpu = 45.0
    sensor._cached_gpu = 62.0
    assert sensor.get_effective_temp() == 62.0

    sensor._cached_cpu = 78.0
    sensor._cached_gpu = 55.0
    assert sensor.get_effective_temp() == 78.0

def test_sensor_single_missing():
    sensor = HardwareSensor()
    sensor._cached_cpu = 50.0
    sensor._cached_gpu = 0.0  # e.g. discrete GPU asleep
    assert sensor.get_effective_temp() == 50.0
