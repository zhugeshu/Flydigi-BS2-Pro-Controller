# tests/test_gui.py
import pytest
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.ui.app import MainWindow

def test_gui_full_lifecycle_and_mode_sync():
    cfg = AppConfig()
    engine = CurveEngine()
    app = MainWindow(cfg, engine, None)
    assert app is not None
    assert app.title() == "飞智空间站 - BS2 Pro 轻量控制台"
    app.update()

    # Change to fixed
    app.set_cooling_mode_ui("固定转速")
    assert app.cooling_mode_seg.get() == "固定转速"
    assert "固定转速" in app.status_badge.cget("text")

    # Change to smart performance
    app.set_cooling_mode_ui("智能变频")
    app.set_smart_preset_ui("性能模式")
    assert app.cooling_mode_seg.get() == "智能变频"
    assert app.smart_preset_combo.get() == "性能模式"
    assert "智能变频" in app.status_badge.cget("text")

    # Test fixed gear change
    app.set_cooling_mode_ui("固定转速")
    app._on_fixed_gear_changed("3档 3000")
    assert app.config.fixed_gear == 2
    assert app.config.fixed_rpm == 3000

    # Test RGB mode change
    app._on_rgb_mode_changed("呼吸灯")
    assert app.config.rgb_mode == 3

    app.destroy()
