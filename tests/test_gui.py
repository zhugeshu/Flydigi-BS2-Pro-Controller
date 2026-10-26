# tests/test_gui.py
import pytest
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.ui.app import MainWindow

def test_gui_create_and_destroy():
    cfg = AppConfig()
    engine = CurveEngine()
    # Test initialization in headless/test mode
    app = MainWindow(cfg, engine, None)
    assert app is not None
    assert app.title() == "飞智空间站 - BS2 Pro 轻量控制台"
    app.update()
    app.destroy()
