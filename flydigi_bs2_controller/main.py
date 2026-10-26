# flydigi_bs2_controller/main.py
"""
Main application entry point for Flydigi BS2 / BS2 Pro lightweight controller.
Ties together BLE worker, hardware sensor, curve engine, UI, and system tray.
"""

import ctypes
import logging
import os
import sys

# Ensure package directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import Optional

from flydigi_bs2_controller.core.ble_worker import BLEWorker, ConnectionState
from flydigi_bs2_controller.core.config import ConfigManager
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.core.protocol import BS2Protocol
from flydigi_bs2_controller.core.sensor import HardwareSensor
from flydigi_bs2_controller.ui.app import MainWindow
from flydigi_bs2_controller.ui.tray import TrayManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("BS2Controller")


class SingleInstanceLock:
    """Windows Mutex to prevent multiple application instances from conflicting."""

    def __init__(self, mutex_name: str = "Local\\FlydigiBS2ControllerMutex"):
        self.mutex_name = mutex_name
        self.handle = None
        self.kernel32 = ctypes.windll.kernel32

    def acquire(self) -> bool:
        self.handle = self.kernel32.CreateMutexW(None, False, self.mutex_name)
        last_error = self.kernel32.GetLastError()
        # ERROR_ALREADY_EXISTS = 183
        if last_error == 183:
            return False
        return True

    def release(self) -> None:
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class BS2Application:
    def __init__(self, config_path: Optional[str] = None):
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config

        self.curve_engine = CurveEngine()
        self.curve_engine.set_mode(self.config.smart_preset)
        self.curve_engine.set_custom_curve(self.config.custom_curve)

        self.sensor = HardwareSensor()
        self.ble_worker = BLEWorker()
        self.ble_worker.is_smart_mode = self.config.cooling_mode == "smart"
        if not self.ble_worker.is_smart_mode:
            self.ble_worker.set_target_rpm(self.config.fixed_rpm)

        # UI & Tray
        self.app = MainWindow(
            config=self.config,
            curve_engine=self.curve_engine,
            ble_worker=self.ble_worker,
            on_save_config=self.config_manager.save,
        )

        self.tray = TrayManager(
            on_show_window=self.show_window_from_tray,
            on_quit_app=self.quit_app,
            on_set_mode=self._handle_tray_mode,
            on_toggle_gear_led=self._handle_tray_toggle_led,
        )

        self._setup_callbacks()
        self._poll_job = None
        self._is_terminating = False

    def _setup_callbacks(self) -> None:
        def on_ble_state(state: ConnectionState):
            self.app.after(0, lambda: self.app.update_connection_state(state))

        def on_rpm(cur: int, tgt: int):
            temp = self.sensor.get_effective_temp()
            self.app.after(0, lambda: self.app.update_telemetry(temp, cur))

        def on_power(mode: int):
            self.curve_engine.set_power_mode(mode)
            self.app.after(0, lambda: self.app.update_power_mode(mode))

        def on_synced():
            logger.info("Connection established/synced. Broadcasting full configuration to device...")
            # Re-sync cooling mode
            if self.config.cooling_mode == "fixed":
                self.ble_worker.set_fixed_speed(self.config.fixed_gear, self.config.fixed_rpm)
            else:
                self.ble_worker.set_smart_mode()

            # Re-sync hardware settings (gear led, auto start, smart start stop, rgb mode)
            self.ble_worker.send_command(BS2Protocol.build_set_gear_led(self.config.gear_led))
            self.ble_worker.send_command(BS2Protocol.build_set_auto_start(self.config.auto_start))
            self.ble_worker.send_command(BS2Protocol.build_set_smart_start_stop(self.config.smart_start_stop))

            if self.config.rgb_mode == 0:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(False))
            elif self.config.rgb_mode == 6:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_intelligent(1))
            else:
                mode_str = {3: "breathe", 4: "pure", 1: "streamer", 2: "rotate"}.get(self.config.rgb_mode, "breathe")
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
                self.ble_worker.send_rgb_animation(
                    mode=mode_str,
                    color=tuple(self.config.rgb_color),
                    speed=self.config.rgb_speed,
                    brightness=self.config.rgb_brightness,
                )

        self.ble_worker.on_state_change = on_ble_state
        self.ble_worker.on_rpm_update = on_rpm
        self.ble_worker.on_power_mode_update = on_power
        self.ble_worker.on_synced = on_synced

    def show_window_from_tray(self) -> None:
        self.app.after(0, self.app.show_window)

    def _handle_tray_mode(self, mode: str) -> None:
        def action():
            if mode == "fixed":
                self.app.set_cooling_mode_ui("固定转速")
            elif mode == "silent":
                self.app.set_cooling_mode_ui("智能变频")
                self.app.set_smart_preset_ui("静音模式")
            elif mode == "performance":
                self.app.set_cooling_mode_ui("智能变频")
                self.app.set_smart_preset_ui("性能模式")

        self.app.after(0, action)

    def _handle_tray_toggle_led(self) -> None:
        def action():
            current = self.app.gear_led_switch.get()
            if current:
                self.app.gear_led_switch.deselect()
            else:
                self.app.gear_led_switch.select()
            self.app._on_gear_led_toggled()

        self.app.after(0, action)

    def start(self, start_in_tray: bool = False) -> None:
        """Start all services and run Tkinter mainloop."""
        logger.info("Starting Flydigi BS2 Pro Controller...")
        if start_in_tray:
            self.app.withdraw()
        self.ble_worker.start()
        self.tray.start()
        self._poll_loop()
        self.app.mainloop()

    def _poll_loop(self) -> None:
        """Periodic 1-second background telemetry & control evaluation loop."""
        if self._is_terminating:
            return

        try:
            temp = self.sensor.get_effective_temp()

            if self.config.cooling_mode == "smart":
                target_rpm = self.curve_engine.calculate_smooth_rpm(temp)
                self.ble_worker.set_target_rpm(target_rpm)
            else:
                self.ble_worker.set_target_rpm(self.config.fixed_rpm)

            # Update UI
            self.app.update_telemetry(temp, self.ble_worker.current_rpm)

            # Update Tray tooltip
            tooltip = (
                f"飞智 BS2 Pro [{self.ble_worker.state.value}] | "
                f"温度: {int(round(temp))}°C | 转速: {self.ble_worker.current_rpm} RPM"
            )
            self.tray.update_tooltip(tooltip)

        except Exception as e:
            logger.error(f"Error in poll loop: {e}")

        self._poll_job = self.app.after(1000, self._poll_loop)

    def quit_app(self) -> None:
        """Gracefully release device control and shutdown all threads."""
        if self._is_terminating:
            return
        self._is_terminating = True
        logger.info("Shutting down Flydigi BS2 Pro Controller...")

        if self._poll_job:
            try:
                self.app.after_cancel(self._poll_job)
            except Exception:
                pass

        # Graceful disconnect: actively writes 0x24 release command over GATT before closing
        self.ble_worker.disconnect_and_release()
        self.sensor.close()
        self.tray.stop()

        try:
            self.app.after(0, self.app.destroy)
        except Exception:
            pass


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print("Flydigi BS2 Pro Controller\nUsage: FlydigiBS2Controller.exe [--tray] [--check] [--help]")
        sys.exit(0)

    if "--check" in sys.argv:
        print("OK: Flydigi BS2 Controller environment and modules loaded successfully.")
        sys.exit(0)

    lock = SingleInstanceLock()
    if not lock.acquire():
        logger.warning("Another instance of Flydigi BS2 Controller is already running.")
        sys.exit(0)

    try:
        app = BS2Application()

        # Register Windows console exit handler
        try:
            import ctypes.wintypes

            HANDLER_ROUTINE = ctypes.WINFUNCTYPE(ctypes.wintypes.BOOL, ctypes.wintypes.DWORD)

            def console_ctrl_handler(ctrl_type):
                logger.info(f"Console control signal {ctrl_type} received, shutting down gracefully...")
                app.quit_app()
                return True

            ctrl_handler_ref = HANDLER_ROUTINE(console_ctrl_handler)
            ctypes.windll.kernel32.SetConsoleCtrlHandler(ctrl_handler_ref, True)
        except Exception as e:
            logger.debug(f"Could not register console ctrl handler: {e}")

        start_in_tray = "--tray" in sys.argv or "--autostart" in sys.argv
        app.start(start_in_tray=start_in_tray)
    finally:
        lock.release()


if __name__ == "__main__":
    main()
