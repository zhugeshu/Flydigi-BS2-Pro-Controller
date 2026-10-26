# flydigi_bs2_controller/ui/app.py
"""
Modern Dark Dashboard GUI for Flydigi BS2 / BS2 Pro Laptop Cooler.
Built with CustomTkinter, mirroring official Flydigi Space Station 3.0 aesthetics.
"""

import logging
from typing import Callable, Optional, Tuple
import customtkinter as ctk

from flydigi_bs2_controller.core.ble_worker import BLEWorker, ConnectionState
from flydigi_bs2_controller.core.config import AppConfig
from flydigi_bs2_controller.core.curve_engine import CurveEngine
from flydigi_bs2_controller.core.protocol import BS2Protocol
from flydigi_bs2_controller.ui.widgets import CircularGauge, CurveCanvas

logger = logging.getLogger(__name__)

# Configure CustomTkinter theme
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class MainWindow(ctk.CTk):
    def __init__(
        self,
        config: AppConfig,
        curve_engine: CurveEngine,
        ble_worker: Optional[BLEWorker] = None,
        on_save_config: Optional[Callable[[], None]] = None,
    ):
        super().__init__()

        self.config = config
        self.curve_engine = curve_engine
        self.ble_worker = ble_worker
        self.on_save_config = on_save_config

        # Window Setup
        self.title("飞智空间站 - BS2 Pro 轻量控制台")
        self.geometry("860x580")
        self.minsize(820, 540)
        self.configure(fg_color="#121212")

        # Window Closing Protocol -> minimize to tray by default
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)

        # Layout: Grid 1 row, 2 columns
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=4, minsize=320)
        self.grid_columnconfigure(1, weight=5, minsize=480)

        self._build_left_panel()
        self._build_right_panel()
        self._sync_ui_from_config()

        # Connect ble worker callbacks
        if self.ble_worker:
            self.ble_worker.on_firmware_update = self._on_firmware_received

    def _build_left_panel(self) -> None:
        """Left panel: Device Name, Dial Gauge, Badge, Real-time status."""
        self.left_frame = ctk.CTkFrame(self, fg_color="#181818", corner_radius=0)
        self.left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 2), pady=0)

        # Title & Firmware
        self.title_label = ctk.CTkLabel(
            self.left_frame,
            text="FlyDigi BS2 PRO",
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color="#FFFFFF",
        )
        self.title_label.pack(pady=(22, 2))

        self.fw_label = ctk.CTkLabel(
            self.left_frame,
            text="固件版本: 查询中...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#888888",
        )
        self.fw_label.pack(pady=(0, 10))

        # Dial Gauge (Temp & RPM)
        self.gauge = CircularGauge(self.left_frame, size=240, max_rpm=4000)
        self.gauge.pack(pady=(5, 10))

        # Status badge (Smart vs Fixed)
        self.status_badge = ctk.CTkLabel(
            self.left_frame,
            text="当前在 ⚙ 智能变频",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#FF6B4A",
            fg_color="#261E1A",
            corner_radius=12,
            padx=14,
            pady=4,
        )
        self.status_badge.pack(pady=(5, 10))

        # Bluetooth status label
        self.conn_label = ctk.CTkLabel(
            self.left_frame,
            text="蓝牙状态: 未连接",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#777777",
        )
        self.conn_label.pack(pady=(5, 0))

    def _build_right_panel(self) -> None:
        """Right panel: Controls, Presets, Curve Editor, Hardware Switches."""
        self.right_frame = ctk.CTkScrollableFrame(self, fg_color="#181818", corner_radius=0)
        self.right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

        # Row 1: Max Overclock RPM Badge
        r1_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r1_frame.pack(fill="x", padx=20, pady=(15, 8))

        ctk.CTkLabel(
            r1_frame,
            text="最大超频转速 ❓",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.max_rpm_label = ctk.CTkLabel(
            r1_frame,
            text="4000rpm (20V PD)",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            text_color="#00E676",
        )
        self.max_rpm_label.pack(side="right")

        # Row 2: Cooling Mode (智能变频 vs 固定转速)
        self.r2_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.r2_frame.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(
            self.r2_frame,
            text="散热模式",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.cooling_mode_seg = ctk.CTkSegmentedButton(
            self.r2_frame,
            values=["智能变频", "固定转速"],
            command=self._on_cooling_mode_changed,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            selected_color="#0066CC",
            selected_hover_color="#0077EE",
        )
        self.cooling_mode_seg.pack(side="right")

        # ================= SMART MODE CONTAINER =================
        self.smart_container = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.smart_container.pack(fill="x", padx=20, pady=4)

        # Smart Preset Dropdown
        self.smart_options_frame = ctk.CTkFrame(self.smart_container, fg_color="transparent")
        self.smart_options_frame.pack(fill="x", pady=(2, 6))

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

        # Curve Canvas
        self.curve_canvas = CurveCanvas(self.smart_container, width=440, height=185)
        self.curve_canvas.pack(pady=4)
        self.curve_canvas.on_curve_changed = self._on_curve_modified

        # ================= FIXED SPEED CONTAINER =================
        self.fixed_container = ctk.CTkFrame(self.right_frame, fg_color="#202020", corner_radius=8)

        # Gear Buttons Row
        gear_row = ctk.CTkFrame(self.fixed_container, fg_color="transparent")
        gear_row.pack(fill="x", padx=14, pady=(12, 6))

        ctk.CTkLabel(
            gear_row,
            text="固定档位",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color="#DDDDDD",
        ).pack(side="left")

        self.gear_seg = ctk.CTkSegmentedButton(
            gear_row,
            values=["1档 1700", "2档 2400", "3档 3000", "4档 4000"],
            command=self._on_fixed_gear_changed,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            selected_color="#0066CC",
            selected_hover_color="#0077EE",
        )
        self.gear_seg.pack(side="right")

        # Slider Row
        slider_row = ctk.CTkFrame(self.fixed_container, fg_color="transparent")
        slider_row.pack(fill="x", padx=14, pady=(6, 12))

        self.fixed_rpm_label = ctk.CTkLabel(
            slider_row,
            text=f"设定转速: {self.config.fixed_rpm} RPM",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            text_color="#00E676",
        )
        self.fixed_rpm_label.pack(side="left")

        self.fixed_slider = ctk.CTkSlider(
            slider_row,
            from_=1300,
            to=4000,
            number_of_steps=54,
            command=self._on_fixed_slider_changed,
            progress_color="#00E676",
            width=220,
        )
        self.fixed_slider.pack(side="right")

        # Row 4: Gear Indicator LED Switch
        r4_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r4_frame.pack(fill="x", padx=20, pady=6)

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
        self.r5_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        self.r5_frame.pack(fill="x", padx=20, pady=6)

        ctk.CTkLabel(
            self.r5_frame,
            text="灯光模式",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color="#BBBBBB",
        ).pack(side="left")

        self.rgb_mode_combo = ctk.CTkComboBox(
            self.r5_frame,
            values=["智能随动", "呼吸灯", "单色常亮", "幻彩流光", "风暴轮转", "关闭"],
            command=self._on_rgb_mode_changed,
            width=140,
            font=ctk.CTkFont(family="Segoe UI", size=13),
        )
        self.rgb_mode_combo.pack(side="right")

        # Advanced RGB Options (Palette & Brightness)
        self.rgb_options_container = ctk.CTkFrame(self.right_frame, fg_color="#202020", corner_radius=8)

        # Color palette
        color_row = ctk.CTkFrame(self.rgb_options_container, fg_color="transparent")
        color_row.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(
            color_row,
            text="灯效颜色",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#AAAAAA",
        ).pack(side="left")

        colors_btn_frame = ctk.CTkFrame(color_row, fg_color="transparent")
        colors_btn_frame.pack(side="right")
        self.preset_colors = [
            ("极光青", (0, 168, 255), "#00A8FF"),
            ("霓虹蓝", (0, 120, 255), "#0078FF"),
            ("魅影紫", (170, 0, 255), "#AA00FF"),
            ("荧光绿", (0, 230, 118), "#00E676"),
            ("烈焰橙", (255, 107, 74), "#FF6B4A"),
            ("火焰红", (255, 23, 68), "#FF1744"),
            ("极光白", (255, 255, 255), "#FFFFFF"),
        ]
        for name, rgb, hex_c in self.preset_colors:
            btn = ctk.CTkButton(
                colors_btn_frame,
                text="",
                width=22,
                height=22,
                corner_radius=11,
                fg_color=hex_c,
                hover_color=hex_c,
                command=lambda c=rgb: self._on_color_selected(c),
            )
            btn.pack(side="left", padx=3)

        # Brightness slider
        bright_row = ctk.CTkFrame(self.rgb_options_container, fg_color="transparent")
        bright_row.pack(fill="x", padx=14, pady=(4, 8))
        self.bright_label = ctk.CTkLabel(
            bright_row,
            text=f"灯光亮度: {self.config.rgb_brightness}%",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color="#AAAAAA",
        )
        self.bright_label.pack(side="left")

        self.bright_slider = ctk.CTkSlider(
            bright_row,
            from_=0,
            to=100,
            number_of_steps=20,
            command=self._on_brightness_changed,
            progress_color="#007ACC",
            width=200,
        )
        self.bright_slider.pack(side="right")

        # Row 6: Smart Start-Stop
        r6_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
        r6_frame.pack(fill="x", padx=20, pady=6)

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
        r7_frame.pack(fill="x", padx=20, pady=(6, 16))

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
            self.smart_container.pack_forget()
            self.fixed_container.pack(fill="x", padx=20, pady=4, after=self.r2_frame)
        else:
            self.cooling_mode_seg.set("智能变频")
            self.status_badge.configure(text="当前在 ⚙ 智能变频", text_color="#FF6B4A", fg_color="#261E1A")
            self.fixed_container.pack_forget()
            self.smart_container.pack(fill="x", padx=20, pady=4, after=self.r2_frame)

        # Fixed gear & slider
        gear_names = ["1档 1700", "2档 2400", "3档 3000", "4档 4000"]
        gear_idx = max(0, min(3, self.config.fixed_gear))
        self.gear_seg.set(gear_names[gear_idx])
        self.fixed_slider.set(self.config.fixed_rpm)
        self.fixed_rpm_label.configure(text=f"设定转速: {self.config.fixed_rpm} RPM")

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
        rgb_display_map = {6: "智能随动", 4: "单色常亮", 3: "呼吸灯", 1: "幻彩流光", 2: "风暴轮转", 0: "关闭"}
        self.rgb_mode_combo.set(rgb_display_map.get(self.config.rgb_mode, "智能随动"))
        if self.config.rgb_mode in (1, 2, 3, 4):
            self.rgb_options_container.pack(fill="x", padx=20, pady=4, after=self.r5_frame)
        else:
            self.rgb_options_container.pack_forget()

        self.bright_slider.set(self.config.rgb_brightness)
        self.bright_label.configure(text=f"灯光亮度: {self.config.rgb_brightness}%")

        # Smart start stop
        stop_display_map = {1: "即时运行", 2: "延时关闭", 0: "关闭"}
        self.smart_stop_combo.set(stop_display_map.get(self.config.smart_start_stop, "即时运行"))

        # Curve
        is_custom = self.config.smart_preset == "custom"
        self.curve_engine.set_mode(self.config.smart_preset)
        self.curve_engine.set_custom_curve(self.config.custom_curve)
        active_points = self.curve_engine.get_active_curve_points()
        self.curve_canvas.set_curve(active_points, editable=is_custom)

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
            self.smart_container.pack_forget()
            self.fixed_container.pack(fill="x", padx=20, pady=4, after=self.r2_frame)
            if self.ble_worker:
                self.ble_worker.set_fixed_speed(self.config.fixed_gear, self.config.fixed_rpm)
        else:
            self.config.cooling_mode = "smart"
            self.status_badge.configure(text="当前在 ⚙ 智能变频", text_color="#FF6B4A", fg_color="#261E1A")
            self.fixed_container.pack_forget()
            self.smart_container.pack(fill="x", padx=20, pady=4, after=self.r2_frame)
            if self.ble_worker:
                self.ble_worker.set_smart_mode()
        self._notify_save()

    def _on_fixed_gear_changed(self, gear_str: str) -> None:
        gear_speeds = {
            "1档 1700": (0, 1700),
            "2档 2400": (1, 2400),
            "3档 3000": (2, 3000),
            "4档 4000": (3, 4000),
        }
        gear, rpm = gear_speeds.get(gear_str, (1, 2400))
        self.config.fixed_gear = gear
        self.config.fixed_rpm = rpm
        self.fixed_slider.set(rpm)
        self.fixed_rpm_label.configure(text=f"设定转速: {rpm} RPM")
        if self.ble_worker:
            self.ble_worker.set_fixed_speed(gear, rpm)
        self._notify_save()

    def _on_fixed_slider_changed(self, value: float) -> None:
        rpm = int(round(value / 50.0) * 50)
        self.config.fixed_rpm = rpm
        self.fixed_rpm_label.configure(text=f"设定转速: {rpm} RPM")
        if self.ble_worker:
            self.ble_worker.set_fixed_speed(self.config.fixed_gear, rpm)
        self._notify_save()

    def _on_smart_preset_changed(self, value: str) -> None:
        name_map = {"静音模式": "silent", "性能模式": "performance", "自定义模式": "custom"}
        mode = name_map.get(value, "silent")
        self.config.smart_preset = mode
        self.curve_engine.set_mode(mode)
        is_custom = mode == "custom"
        active_points = self.curve_engine.get_active_curve_points()
        self.curve_canvas.set_curve(active_points, editable=is_custom)
        self._notify_save()

    def _on_curve_modified(self, points) -> None:
        self.config.custom_curve = [list(p) for p in points]
        self.curve_engine.set_custom_curve(self.config.custom_curve)
        if self.config.smart_preset != "custom":
            self.config.smart_preset = "custom"
            self.smart_preset_combo.set("自定义模式")
            self.curve_engine.set_mode("custom")
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
        rgb_map = {
            "智能随动": 6,
            "单色常亮": 4,
            "呼吸灯": 3,
            "风暴轮转": 2,
            "幻彩流光": 1,
            "关闭": 0,
        }
        code = rgb_map.get(value, 6)
        self.config.rgb_mode = code

        if code == 0:
            self.rgb_options_container.pack_forget()
            if self.ble_worker:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(False))
        elif code == 6:
            self.rgb_options_container.pack_forget()
            if self.ble_worker:
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
                self.ble_worker.send_command(BS2Protocol.build_set_rgb_intelligent(1))
        else:
            self.rgb_options_container.pack(fill="x", padx=20, pady=4, after=self.r5_frame)
            self._apply_rgb_animation()

        self._notify_save()

    def _on_color_selected(self, color_rgb: Tuple[int, int, int]) -> None:
        self.config.rgb_color = list(color_rgb)
        self._apply_rgb_animation()
        self._notify_save()

    def _on_brightness_changed(self, value: float) -> None:
        val = int(value)
        self.config.rgb_brightness = val
        self.bright_label.configure(text=f"灯光亮度: {val}%")
        self._apply_rgb_animation()
        self._notify_save()

    def _apply_rgb_animation(self) -> None:
        """Apply active RGB animation to hardware via BLE worker."""
        if not self.ble_worker:
            return

        mode_name_map = {3: "breathe", 4: "pure", 1: "streamer", 2: "rotate"}
        mode_str = mode_name_map.get(self.config.rgb_mode, "breathe")
        self.ble_worker.send_command(BS2Protocol.build_set_rgb_state(True))
        self.ble_worker.send_rgb_animation(
            mode=mode_str,
            color=tuple(self.config.rgb_color),
            speed=self.config.rgb_speed,
            brightness=self.config.rgb_brightness,
        )

    def _on_smart_start_stop_changed(self, value: str) -> None:
        stop_map = {"即时运行": 1, "延时关闭": 2, "关闭": 0}
        code = stop_map.get(value, 1)
        self.config.smart_start_stop = code
        if self.ble_worker:
            self.ble_worker.send_command(BS2Protocol.build_set_smart_start_stop(code))
        self._notify_save()

    def _on_firmware_received(self, fw: str) -> None:
        """Callback from ble worker when firmware version received."""
        self.after(0, lambda: self.fw_label.configure(text=f"固件版本: {fw}"))

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
        rpm_map = {1: "2700rpm (5V)", 2: "3300rpm (9V)", 3: "4000rpm (20V PD)"}
        self.max_rpm_label.configure(text=rpm_map.get(mode, "4000rpm (20V PD)"))

    def hide_to_tray(self) -> None:
        """Hide window to system tray."""
        self.withdraw()

    def show_window(self) -> None:
        """Restore window from tray."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def quit_app(self) -> None:
        """Exit app cleanly."""
        if self.ble_worker:
            self.ble_worker.disconnect_and_release()
        self.destroy()

    def _notify_save(self) -> None:
        if self.on_save_config:
            try:
                self.on_save_config()
            except Exception as e:
                logger.error(f"Error persisting config: {e}")
