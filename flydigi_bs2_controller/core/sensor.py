# flydigi_bs2_controller/core/sensor.py
"""
Hardware temperature sensor collector for CPU and GPU.
Uses native Windows Performance Counters and nvidia-smi with zero external driver dependencies.
Runs queries in a dedicated background worker thread to prevent blocking GUI responsiveness.
"""

import logging
import subprocess
import threading
import time
from typing import Tuple

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000


class HardwareSensor:
    def __init__(self, start_background_thread: bool = True):
        self._cached_cpu: float = 45.0
        self._cached_gpu: float = 0.0  # Default to 0.0 (no dGPU assumed until detected)
        self._has_nvidia: bool = True

        # Initial synchronous probe
        self.update()

        # Background polling thread
        self._running = False
        self._thread: Optional[threading.Thread] = None
        if start_background_thread:
            self.start_background_polling()

    def start_background_polling(self, interval: float = 1.0) -> None:
        """Start non-blocking daemon thread to update temperatures continuously."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._background_loop,
            args=(interval,),
            name="SensorPollingThread",
            daemon=True,
        )
        self._thread.start()

    def _background_loop(self, interval: float) -> None:
        while self._running:
            try:
                self.update()
            except Exception as e:
                logger.debug(f"Background sensor update error: {e}")
            time.sleep(interval)

    def _query_gpu_nvidia(self) -> float:
        """Query NVIDIA GPU temperature using nvidia-smi."""
        if not self._has_nvidia:
            return 0.0
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                creationflags=CREATE_NO_WINDOW,
                timeout=1.0,
            ).decode().strip()
            if out:
                return float(out.splitlines()[0].strip())
        except Exception:
            self._has_nvidia = False
        return 0.0

    def _query_cpu_thermal_zone(self) -> float:
        """Query CPU/System temperature from Win32_PerfFormattedData_Counters_ThermalZoneInformation."""
        try:
            cmd = [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance -ClassName Win32_PerfFormattedData_Counters_ThermalZoneInformation -ErrorAction SilentlyContinue).HighPrecisionTemperature",
            ]
            out = subprocess.check_output(cmd, creationflags=CREATE_NO_WINDOW, timeout=1.5).decode().strip()
            if out:
                raw_val = float(out.split()[0].strip())
                celsius = (raw_val - 2732.0) / 10.0
                if 20.0 <= celsius <= 115.0:
                    return round(celsius, 1)
        except Exception as e:
            logger.debug(f"Error querying thermal zone: {e}")
        return 0.0

    def update(self) -> None:
        """Poll hardware sensors and update cached CPU/GPU temperatures."""
        # Query GPU (resets to 0.0 if dGPU is asleep or absent)
        gpu = self._query_gpu_nvidia()
        self._cached_gpu = round(gpu, 1) if gpu > 0 else 0.0

        # Query CPU
        cpu = self._query_cpu_thermal_zone()
        if cpu > 0:
            self._cached_cpu = round(cpu, 1)

    def get_temperatures(self, refresh: bool = False) -> Tuple[float, float]:
        """Return (cpu_temp, gpu_temp)."""
        if refresh:
            self.update()
        return self._cached_cpu, self._cached_gpu

    def get_effective_temp(self, refresh: bool = False) -> float:
        """
        Return the primary effective temperature for fan regulation:
        max(cpu_temp, gpu_temp). If one sensor is 0 (e.g. dGPU asleep), uses the other.
        """
        cpu, gpu = self.get_temperatures(refresh=refresh)
        if cpu > 0 and gpu > 0:
            eff = max(cpu, gpu)
        elif cpu > 0:
            eff = cpu
        elif gpu > 0:
            eff = gpu
        else:
            eff = 45.0
        return round(eff, 1)

    def close(self) -> None:
        """Cleanup sensor resources and stop background thread."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
