# flydigi_bs2_controller/ui/tray.py
"""
System tray icon and context menu management using pystray and Pillow.
Supports dynamic hover tooltip and background operation.
"""

import logging
import threading
from typing import Callable, Optional
from PIL import Image, ImageDraw
import pystray

logger = logging.getLogger(__name__)


def create_tray_image(width: int = 64, height: int = 64) -> Image.Image:
    """Generate a clean dark theme fan icon in memory."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer circle
    draw.ellipse([4, 4, width - 4, height - 4], fill="#1E1E1E", outline="#00A8FF", width=3)

    # 4 Fan blades
    cx, cy = width // 2, height // 2
    draw.polygon([(cx, cy), (cx - 16, cy - 20), (cx, cy - 24)], fill="#00E5FF")
    draw.polygon([(cx, cy), (cx + 20, cy - 16), (cx + 24, cy)], fill="#00E5FF")
    draw.polygon([(cx, cy), (cx + 16, cy + 20), (cx, cy + 24)], fill="#00E5FF")
    draw.polygon([(cx, cy), (cx - 20, cy + 16), (cx - 24, cy)], fill="#00E5FF")

    # Center circle
    draw.ellipse([cx - 6, cy - 6, cx + 6, cy + 6], fill="#FFFFFF")
    return img


class TrayManager:
    def __init__(
        self,
        on_show_window: Callable[[], None],
        on_quit_app: Callable[[], None],
        on_set_mode: Optional[Callable[[str], None]] = None,
        on_toggle_gear_led: Optional[Callable[[], None]] = None,
    ):
        self.on_show_window = on_show_window
        self.on_quit_app = on_quit_app
        self.on_set_mode = on_set_mode
        self.on_toggle_gear_led = on_toggle_gear_led

        self.icon: Optional[pystray.Icon] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start tray icon in a dedicated daemon thread."""
        image = create_tray_image()
        menu = pystray.Menu(
            pystray.MenuItem("打开控制面板", self._handle_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "散热模式",
                pystray.Menu(
                    pystray.MenuItem("智能变频 - 静音", lambda: self._handle_mode("silent")),
                    pystray.MenuItem("智能变频 - 性能", lambda: self._handle_mode("performance")),
                    pystray.MenuItem("固定转速", lambda: self._handle_mode("fixed")),
                ),
            ),
            pystray.MenuItem("档位指示灯 开/关", self._handle_toggle_led),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出软件", self._handle_quit),
        )

        self.icon = pystray.Icon(
            "FlydigiBS2Controller",
            image,
            "飞智 BS2 Pro 控制器",
            menu=menu,
        )

        self._thread = threading.Thread(target=self.icon.run, name="TrayThread", daemon=True)
        self._thread.start()

    def update_tooltip(self, text: str) -> None:
        """Update system tray hover tooltip dynamically."""
        if self.icon:
            try:
                self.icon.title = text
            except Exception:
                pass

    def stop(self) -> None:
        """Stop tray icon."""
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
            self.icon = None

    def _handle_show(self, icon=None, item=None) -> None:
        if self.on_show_window:
            self.on_show_window()

    def _handle_mode(self, mode: str) -> None:
        if self.on_set_mode:
            self.on_set_mode(mode)

    def _handle_toggle_led(self, icon=None, item=None) -> None:
        if self.on_toggle_gear_led:
            self.on_toggle_gear_led()

    def _handle_quit(self, icon=None, item=None) -> None:
        if self.on_quit_app:
            self.on_quit_app()
