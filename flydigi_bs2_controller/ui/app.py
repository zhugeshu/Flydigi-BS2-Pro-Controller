# flydigi_bs2_controller/ui/app.py
"""
Modern Dark Theme Dashboard GUI for Flydigi BS2 Pro Cooler.
Built using CustomTkinter, mirroring the layout and features of Flydigi Space Station.
"""

import logging
from typing import Optional
import customtkinter as ctk

from flydigi_bs2_controller.core.ble_worker import BLEWorker, ConnectionState
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.core.protocol import BS2Protocol
from flydigi_bs2_controller.ui.widgets import CircularGauge, CurveCanvas

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    def __init__(
        self,
        config: AppConfig,
        curve_engine: CurveEngine,
        ble_worker: Optional[BLEWorker] = None,
        on_save_config: Optional[callable] = None,
    ):
        super().__init__()
        self.config = config
        self.curve_engine = curve_engine
        self.ble_worker = ble_worker
        self.on_save_config = on_save_config

        self.title("飞智空间站 - BS2 Pro 轻量控制台")
        self.geometry("920x580")
        self.resizable(False, False)
        self.configure(fg_color="#121212")

        # Intercept window close button
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        self._build_layout()
        self._sync_ui_from_config()

    def hide_to_tray(self) -> None:
        """Minimize/hide window to system tray."""
        self.withdraw()

    def show_window(self) -> None:
        """Restore window from tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def _build_layout(self) -> None:
        # Container grid (1 row, 2 columns)
        self.grid_columnconfigure(0, weight=4)  # Left gauge
        self.grid_columnconfigure(1, weight=6)  # Right settings panel
        self.grid_rowconfigure(0, weight=1)

        # ================= LEFT PANEL =================
        self.left_frame = ctk.CTkFrame(self, fg_color="#141414", corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=0)

        # Title & Device Name
        self.title_label = ctk.CTkLabel(
            self.left_frame,
            text="散热底座",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color="#E0E0E0",
        )
        self.title_label.pack(anchor="nw", padx=25, pady=(20, 10))

        # Circular Gauge
        self.gauge = CircularGauge(self.left_frame, width=300, height=300)
        self.gauge.pack(pady=(15, 10))

        # Current Status Badge
        self.status_badge = ctk.CTkLabel(
            self.left_frame,
            text="当前在 ⚙ 智能变频",
            fg_color="#261E1A",
            text_color="#FF6B4A",
            corner_radius=12,
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            padx=14,
            pady=4,
        )
        self.status_badge.pack(pady=5)

        # Connection status label
        self.conn_label = ctk.CTkLabel(
            self.left_frame,
            text="蓝牙状态: 已断开",
            text_color="#777777",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.conn_label.pack(pady=(15, 0))

        # ================= RIGHT PANEL =================
        self.right_frame = ctk.CTkScrollableFrame(self, fg_color="#181818", corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Row 1: Max Overclock RPM Badge
        r1_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r1_frame.pack(fill="x", padx=20, pady=(15, 10))

        ctk.CTkLabel(
            r1_frame,
            text="最大超频转速 ❓",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.max_rpm_label = ctk.CTkLabel(
            r1_frame,
            text="4000rpm",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#00E676",
        )
        self.max_rpm_label.pack(side="right")

        # Row 2: Cooling Mode (智能变频 vs 固定转速)
        r2_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r2_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            r2_frame,
            text="散热模式",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.cooling_mode_seg = ctk.CTkSegmentedButton(
            r2_frame,
            values=["智能变频", "固定转速"],
            command=self._on_cooling_mode_changed,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            selected_color="#0066CC",
            selected_hover_color="#0077EE",
        )
        self.cooling_mode_seg.pack(side="right")

        # Row 3: Smart Mode Presets
        self.smart_options_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.smart_options_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            self.smart_options_frame,
            text="- 智能变频模式",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#AAAAAA",
        ).pack(side="left")

        self.smart_preset_combo = ctk.CTkComboBox(
            self.smart_options_frame,
            values=["静音模式", "性能模式", "自定义模式"],
            command=self._on_smart_preset_changed,
            width=140,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.smart_preset_combo.pack(side="right")

        # Curve Editor Canvas
        self.curve_canvas = CurveCanvas(self.right_frame, width=440, height=190)
        self.curve_canvas.pack(padx=20, pady=6)
        self.curve_canvas.on_curve_changed = self._on_curve_modified

        # Row 4: Gear Indicator LED Switch
        r4_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r4_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            r4_frame,
            text="档位灯显示 ❓",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.gear_led_switch = ctk.CTkSwitch(
            r4_frame,
            text="",
            command=self._on_gear_led_toggled,
            progress_color="#007ACC",
        )
        self.gear_led_switch.pack(side="right")

        # Row 5: RGB Light Mode
        r5_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r5_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            r5_frame,
            text="灯光模式",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.rgb_mode_combo = ctk.CTkComboBox(
            r5_frame,
            values=["智能", "常亮", "呼吸", "幻彩流光", "关闭"],
            command=self._on_rgb_mode_changed,
            width=140,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.rgb_mode_combo.pack(side="right")

        # Row 6: Smart Start-Stop
        r6_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r6_frame.pack(fill="x", padx=20, pady=8)

        ctk.CTkLabel(
            r6_frame,
            text="智能启停 ❓",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.smart_stop_combo = ctk.CTkComboBox(
            r6_frame,
            values=["即时运行", "延时关闭", "关闭"],
            command=self._on_smart_start_stop_changed,
            width=140,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.smart_stop_combo.pack(side="right")

        # Row 7: Power-on Auto Start Switch
        r7_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r7_frame.pack(fill="x", padx=20, pady=(8, 20))

        ctk.CTkLabel(
            r7_frame,
            text="通电自启功能 ❓",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.auto_start_switch = ctk.CTkSwitch(
            r7_frame,
            text="",
            command=self._on_auto_start_toggled,
            progress_color="#007ACC",
        )
        self.auto_start_switch.pack(side="right")

    def _sync_ui_from_config(self) -> None:
        """Sync controls to initial AppConfig values."""
        # Cooling mode
        if self.config.cooling_mode == "fixed":
            self.cooling_mode_seg.set("固定转速")
            self.status_badge.configure(text="当前在 🔒 固定转速", text_color="#00A8FF", fg_color="#102030")
        else:
            self.cooling_mode_seg.set("智能变频")
            self.status_badge.configure(text="当前在 ⚙ 智能变频", text_color="#FF6B4A", fg_color="#261E1A")

        # Smart preset
        preset_map = {"silent": "静音模式", "performance": "性能模式", "custom": "自定义模式"}
        self.smart_preset_combo.set(preset_map.get(self.config.smart_preset, "静音模式"))

        # Switches
        if self.config.gear_led:
            self.gear_led_switch.select()
        else:
            self.gear_led_switch.deselect()

        if self.config.auto_start:
            self.auto_start_switch.select()
        else:
            self.auto_start_switch.deselect()

        # RGB mode
        rgb_display_map = {6: "智能", 4: "常亮", 3: "呼吸", 1: "幻彩流光", 0: "关闭"}
        self.rgb_mode_combo.set(rgb_display_map.get(self.config.rgb_mode, "智能"))

        # Smart start stop
        stop_display_map = {1: "即时运行", 2: "延时关闭", 0: "关闭"}
        self.smart_stop_combo.set(stop_display_map.get(self.config.smart_start_stop, "即时运行"))

        # Curve
        is_custom = self.config.smart_preset == "custom"
        self.curve_canvas.set_curve(self.config.custom_curve, editable=is_custom)

    def set_cooling_mode_ui(self, value: str) -> None:
        """External call to switch cooling mode and synchronize UI."""
        self.cooling_mode_seg.set(value)
        self._on_cooling_mode_changed(value)

    def set_smart_preset_ui(self, value: str) -> None:
        """External call to switch smart preset and synchronize UI."""
        self.smart_preset_combo.set(value)
        self._on_smart_preset_changed(value)

    def _on_cooling_mode_changed(self, value: str) -> None:
        if value == "固定转速":
            self.config.cooling_mode = "fixed"
            self.status_badge.configure(text="当前在 🔒 固定转速", text_color="#00A8FF", fg_color="#102030")
            if self.ble_worker:
                self.ble_worker.is_smart_mode = False
                self.ble_worker.send_command(BS2Protocol.build_set_rpm(self.config.fixed_rpm))
        else:
            self.config.cooling_mode = "smart"
            self.status_badge.configure(text="当前在 ⚙ 智能变频", text_color="#FF6B4A", fg_color="#261E1A")
            if self.ble_worker:
                self.ble_worker.is_smart_mode = True
                self.ble_worker.send_command(BS2Protocol.build_start_smart())
        self._notify_save()

    def _on_smart_preset_changed(self, value: str) -> None:
        name_map = {"静音模式": "silent", "性能模式": "performance", "自定义模式": "custom"}
        mode = name_map.get(value, "silent")
        self.config.smart_preset = mode
        self.curve_engine.set_mode(mode)
        is_custom = mode == "custom"
        self.curve_canvas.set_curve(self.config.custom_curve, editable=is_custom)
        self._notify_save()

    def _on_curve_modified(self, points) -> None:
        self.config.custom_curve = [list(p) for p in points]
        self.curve_engine.set_custom_curve(self.config.custom_curve)
        self._notify_save()

    def _on_gear_led_toggled(self) -> None:
        enabled = bool(self.gear_led_switch.get())
        self.config.gear_led = enabled
        if self.ble_worker:
            self.ble_worker.send_command(BS2Protocol.build_set_gear_led(enabled))
        self._notify_save()

    def _on_auto_start_toggled(self) -> None:
        enabled = bool(self.auto_start_switch.get())
        self.config.auto_start = enabled
        if self.ble_worker:
            self.ble_worker.send_command(BS2Protocol.build_set_auto_start(enabled))
        self._notify_save()

    def _on_rgb_mode_changed(self, value: str) -> None:
        rgb_map = {"智能": 6, "常亮": 4, "呼吸": 3, "幻彩流光": 1, "关闭": 0}
        code = rgb_map.get(value, 6)
        self.config.rgb_mode = code
        if self.ble_worker:
            if code == 0:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(False))
            elif code == 6:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_intelligent(1))
            else:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
        self._notify_save()

    def _on_smart_start_stop_changed(self, value: str) -> None:
        stop_map = {"即时运行": 1, "延时关闭": 2, "关闭": 0}
        code = stop_map.get(value, 1)
        self.config.smart_start_stop = code
        if self.ble_worker:
            self.ble_worker.send_command(BS2Protocol.build_set_smart_start_stop(code))
        self._notify_save()

    def update_telemetry(self, temp: float, cur_rpm: int) -> None:
        """Called periodically by main controller loop to update gauge and labels."""
        self.gauge.set_values(temp, cur_rpm)

    def update_connection_state(self, state: ConnectionState) -> None:
        """Update BLE status text and color."""
        color_map = {
            ConnectionState.DISCONNECTED: "#777777",
            ConnectionState.SCANNING: "#E6A23C",
            ConnectionState.CONNECTING: "#409EFF",
            ConnectionState.CONNECTED: "#67C23A",
            ConnectionState.SYNCED: "#67C23A",
        }
        self.conn_label.configure(
            text=f"蓝牙状态: {state.value}",
            text_color=color_map.get(state, "#777777"),
        )

    def update_power_mode(self, mode: int) -> None:
        """Update max RPM label based on power mode (1=5V, 2=9V, 3=20V)."""
        rpm_map = {1: "2700rpm", 2: "3300rpm", 3: "4000rpm"}
        self.max_rpm_label.configure(text=rpm_map.get(mode, "4000rpm"))

    def _notify_save(self) -> None:
        if self.on_save_config:
            try:
                self.on_save_config()
            except Exception as e:
                logger.error(f"Error persisting config: {e}")
