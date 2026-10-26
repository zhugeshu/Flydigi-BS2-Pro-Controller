# flydigi_bs2_controller/ui/widgets.py
"""
Custom UI widgets for Flydigi BS2 Pro controller.
Includes CircularGauge (Temperature/RPM dial) and CurveCanvas (Interactive curve editor).
"""

import math
import tkinter as tk
from typing import Callable, List, Optional
import customtkinter as ctk


class CircularGauge(tk.Canvas):
    """
    Circular / Arc gauge widget rendering a dark glowing arc,
    large temperature number, and needle/gradient indicator.
    """

    def __init__(
        self,
        master,
        width: int = 280,
        height: int = 280,
        size: Optional[int] = None,
        max_rpm: int = 4000,
        **kwargs,
    ):
        if size is not None:
            width = size
            height = size
        self.max_rpm = max_rpm
        super().__init__(
            master,
            width=width,
            height=height,
            bg="#181818",
            highlightthickness=0,
            **kwargs,
        )
        self.width = width
        self.height = height
        self.temperature: float = 41.0
        self.rpm: int = 1300
        self.mode_text: str = "智能变频"
        self._draw_gauge()

    def set_values(self, temp: float, rpm: int, mode_text: Optional[str] = None) -> None:
        """Update gauge values and trigger redraw."""
        self.temperature = temp
        self.rpm = rpm
        if mode_text:
            self.mode_text = mode_text
        self._draw_gauge()

    def _draw_gauge(self) -> None:
        self.delete("all")
        cx = self.width / 2
        cy = self.height / 2 - 10
        radius = min(cx, cy) - 30

        # Draw background track arc (from 140° to 40° clockwise)
        # In tkinter create_arc: start angle is in degrees (0 is east, counterclockwise),
        # extent is degrees.
        # Bottom cutout arc: start = -40, extent = 260
        self.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=-40,
            extent=260,
            outline="#2A2A2A",
            width=18,
            style="arc",
        )

        # Draw active gradient/colored arc based on temperature (30°C to 100°C)
        clamped_temp = max(30.0, min(100.0, self.temperature))
        pct = (clamped_temp - 30.0) / 70.0
        active_extent = 260 * pct

        # Dynamic arc color: Cyan (#00E5FF) -> Yellow (#FFD600) -> Red (#FF3D00)
        if pct < 0.4:
            color = "#00E5FF"
        elif pct < 0.7:
            color = "#FFD600"
        else:
            color = "#FF3D00"

        # Tkinter arc starts from top-left counterclockwise; 220 start = 140° visually
        self.create_arc(
            cx - radius,
            cy - radius,
            cx + radius,
            cy + radius,
            start=220,
            extent=-active_extent,
            outline=color,
            width=18,
            style="arc",
        )

        # Central temperature text
        self.create_text(
            cx,
            cy - 10,
            text=f"{int(round(self.temperature))}°C",
            fill="#FFFFFF",
            font=("Segoe UI", 36, "bold"),
        )
        self.create_text(
            cx,
            cy + 32,
            text="💻 设备温度",
            fill="#888888",
            font=("Segoe UI", 12),
        )

        # Current RPM indicator below the dial
        self.create_text(
            cx,
            self.height - 35,
            text=f"🌀 {self.rpm}rpm",
            fill="#FFFFFF",
            font=("Segoe UI", 16, "bold"),
        )


class CurveCanvas(tk.Canvas):
    """
    Interactive fan curve graph matching Flydigi Space Station.
    Displays 8 temperature control points (30°C ~ 100°C) and allows node dragging in custom mode.
    """

    def __init__(self, master, width: int = 420, height: int = 220, **kwargs):
        super().__init__(
            master,
            width=width,
            height=height,
            bg="#181818",
            highlightthickness=1,
            highlightbackground="#2A2A2A",
            **kwargs,
        )
        self.width = width
        self.height = height

        self.padding_left = 45
        self.padding_right = 25
        self.padding_top = 20
        self.padding_bottom = 35

        self.points: List[List[int]] = [
            [30, 1300],
            [40, 1700],
            [50, 2100],
            [60, 2600],
            [70, 3200],
            [80, 3700],
            [90, 4000],
            [100, 4000],
        ]
        self.is_editable: bool = False
        self.selected_point_idx: Optional[int] = None
        self.on_curve_changed: Optional[Callable[[List[List[int]]], None]] = None

        self.bind("<Button-1>", self._on_click)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.draw_curve()

    def set_curve(self, points: List[List[int]], editable: bool = False) -> None:
        """Update curve points and editability state."""
        self.points = [list(p) for p in points]
        self.is_editable = editable
        self.draw_curve()

    def _temp_to_x(self, temp: float) -> float:
        plot_w = self.width - self.padding_left - self.padding_right
        return self.padding_left + (temp - 30.0) / 70.0 * plot_w

    def _rpm_to_y(self, rpm: float) -> float:
        plot_h = self.height - self.padding_top - self.padding_bottom
        # 1300 RPM at bottom, 4000 RPM at top
        clamped = max(1300, min(4000, rpm))
        pct = (clamped - 1300) / (4000 - 1300)
        return (self.height - self.padding_bottom) - pct * plot_h

    def _y_to_rpm(self, y: float) -> int:
        plot_h = self.height - self.padding_top - self.padding_bottom
        pct = (self.height - self.padding_bottom - y) / plot_h
        raw_rpm = 1300 + pct * (4000 - 1300)
        # Snap to nearest 50 RPM
        snapped = round(raw_rpm / 50.0) * 50
        return int(max(1300, min(4000, snapped)))

    def draw_curve(self) -> None:
        self.delete("all")

        plot_w = self.width - self.padding_left - self.padding_right
        plot_h = self.height - self.padding_top - self.padding_bottom

        # Grid lines & labels (Y-axis: 1档 to 12档)
        for i, gear in enumerate(["1档", "3档", "6档", "9档", "12档"]):
            y = self.padding_top + i * (plot_h / 4.0)
            self.create_line(self.padding_left, y, self.width - self.padding_right, y, fill="#242424")
            self.create_text(self.padding_left - 18, y, text=gear, fill="#666666", font=("Segoe UI", 9))

        # X-axis ticks (30°C to 100°C)
        for temp in [30, 40, 50, 60, 70, 80, 90, 100]:
            x = self._temp_to_x(temp)
            self.create_line(x, self.padding_top, x, self.height - self.padding_bottom, fill="#242424")
            self.create_text(
                x,
                self.height - self.padding_bottom + 15,
                text=str(temp),
                fill="#888888",
                font=("Segoe UI", 9),
            )

        # X-axis label
        self.create_text(
            self.width / 2,
            self.height - 8,
            text="温度/°C",
            fill="#777777",
            font=("Segoe UI", 9),
        )

        # Plot line segments connecting points
        canvas_coords = []
        for temp, rpm in self.points:
            canvas_coords.extend([self._temp_to_x(temp), self._rpm_to_y(rpm)])

        if len(canvas_coords) >= 4:
            self.create_line(canvas_coords, fill="#007ACC", width=2)

        # Draw nodes (circles)
        node_color = "#00A8FF" if self.is_editable else "#005588"
        for i, (temp, rpm) in enumerate(self.points):
            x = self._temp_to_x(temp)
            y = self._rpm_to_y(rpm)
            r = 5
            self.create_oval(x - r, y - r, x + r, y + r, fill=node_color, outline="#FFFFFF", width=1)

        # If not editable, draw watermark instruction text
        if not self.is_editable:
            self.create_text(
                self.width / 2,
                self.height / 2 - 5,
                text="仅自定义模式下可调节曲线",
                fill="#555555",
                font=("Segoe UI", 12),
            )

    def _on_click(self, event) -> None:
        if not self.is_editable:
            return
        # Find nearest point within 15 pixels
        for i, (temp, rpm) in enumerate(self.points):
            x = self._temp_to_x(temp)
            y = self._rpm_to_y(rpm)
            if math.hypot(event.x - x, event.y - y) <= 15:
                self.selected_point_idx = i
                break

    def _on_drag(self, event) -> None:
        if not self.is_editable or self.selected_point_idx is None:
            return
        idx = self.selected_point_idx
        # Y determines RPM
        new_rpm = self._y_to_rpm(event.y)
        self.points[idx][1] = new_rpm
        self.draw_curve()
        if self.on_curve_changed:
            self.on_curve_changed(self.points)

    def _on_release(self, event) -> None:
        self.selected_point_idx = None
