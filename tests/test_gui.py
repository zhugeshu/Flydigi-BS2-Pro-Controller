# tests/test_gui.py
import pytest
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.ui.app import MainWindow

def test_gui_create_and_destroy():
    cfg = AppConfig()
    engine = CurveEngine()
    app = MainWindow(cfg, engine, None)
    assert app is not None
    assert app.title() == "飞智空间站 - BS2 Pro 轻量控制台"
    app.update()
    app.destroy()

def test_gui_sync_controls_on_external_mode_change():
    """Verify Important Finding 5: Changing mode via tray updates segmented buttons and combo boxes."""
    cfg = AppConfig()
    engine = CurveEngine()
    app = MainWindow(cfg, engine, None)

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

    app.destroy()
