# tests/test_config.py
import json
import pytest
from flydigi_bs2_controller.core.config import ConfigManager, AppConfig

def test_default_config():
    cfg = AppConfig()
    assert cfg.cooling_mode == "smart"
    assert cfg.smart_preset == "silent"
    assert cfg.fixed_rpm == 2000
    assert cfg.gear_led is True
    assert cfg.auto_start is True
    assert cfg.smart_start_stop == 1
    assert cfg.rgb_mode == 6
    assert len(cfg.custom_curve) == 8
    # Curve checks: 30°C -> 1300, 100°C -> 4000
    assert cfg.custom_curve[0] == [30, 1300]
    assert cfg.custom_curve[-1] == [100, 4000]

def test_save_and_load(tmp_path):
    config_file = str(tmp_path / "test_config.json")
    mgr = ConfigManager(config_file)
    mgr.config.cooling_mode = "fixed"
    mgr.config.fixed_rpm = 2500
    mgr.config.gear_led = False
    mgr.save()

    # Verify file was written as valid JSON
    with open(config_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["cooling_mode"] == "fixed"
        assert data["fixed_rpm"] == 2500
        assert data["gear_led"] is False

    new_mgr = ConfigManager(config_file)
    assert new_mgr.config.cooling_mode == "fixed"
    assert new_mgr.config.fixed_rpm == 2500
    assert new_mgr.config.gear_led is False

def test_corrupted_config_fallback(tmp_path):
    config_file = str(tmp_path / "corrupted.json")
    with open(config_file, "w", encoding="utf-8") as f:
        f.write("{invalid json...")

    mgr = ConfigManager(config_file)
    # Should fallback to default config without crash
    assert mgr.config.cooling_mode == "smart"
    assert mgr.config.fixed_rpm == 2000
