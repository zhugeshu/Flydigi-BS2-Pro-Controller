# flydigi_bs2_controller/core/sensor.py
"""
Hardware temperature sensor collector for CPU and GPU.
Uses native Windows Performance Counters and nvidia-smi with zero external driver dependencies.
"""

import logging
import subprocess
from typing import Tuple

logger = logging.getLogger(__name__)

CREATE_NO_WINDOW = 0x08000000


class HardwareSensor:
    def __init__(self):
        self._cached_cpu: float = 45.0
        self._cached_gpu: float = 40.0
        self._has_nvidia: bool = True
        # Initial probe
        self.update()

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
        gpu = self._query_gpu_nvidia()
        if gpu > 0:
            self._cached_gpu = round(gpu, 1)

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
        max(cpu_temp, gpu_temp).
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
        """Cleanup sensor resources."""
        pass
