# flydigi_bs2_controller/core/sensor.py
"""
Hardware temperature sensor collector for CPU and GPU.
Integrates with LibreHardwareMonitorLib.dll via pythonnet, with graceful fallback.
"""

import logging
import os
import sys
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Search paths for LibreHardwareMonitorLib.dll
DLL_CANDIDATES = [
    r"C:\Program Files\FlydigiSpaceStation\LibreHardwareMonitorLib.dll",
    os.path.join(os.path.dirname(__file__), "..", "..", "lib", "LibreHardwareMonitorLib.dll"),
]


class HardwareSensor:
    def __init__(self):
        self._computer = None
        self._is_initialized = False
        self._cached_cpu: float = 45.0
        self._cached_gpu: float = 40.0
        self._init_backend()

    def _init_backend(self) -> None:
        """Attempt to initialize LibreHardwareMonitor via pythonnet."""
        try:
            import clr  # pythonnet

            dll_path = None
            for candidate in DLL_CANDIDATES:
                if os.path.exists(candidate):
                    dll_path = os.path.abspath(candidate)
                    break

            if not dll_path:
                logger.warning("LibreHardwareMonitorLib.dll not found in standard paths")
                return

            clr.AddReference(dll_path)
            from LibreHardwareMonitor.Hardware import Computer

            self._computer = Computer()
            self._computer.IsCpuEnabled = True
            self._computer.IsGpuEnabled = True
            self._computer.Open()
            self._is_initialized = True
            logger.info("LibreHardwareMonitor backend initialized successfully")
        except Exception as e:
            logger.warning(f"Could not initialize LibreHardwareMonitor backend: {e}")
            self._computer = None
            self._is_initialized = False

    def update(self) -> None:
        """Poll hardware sensors and update cached CPU/GPU temperatures."""
        if not self._is_initialized or not self._computer:
            return

        cpu_temps = []
        gpu_temps = []

        try:
            for hardware in self._computer.Hardware:
                hardware.Update()
                hw_type = str(hardware.HardwareType)
                for sensor in hardware.Sensors:
                    if str(sensor.SensorType) == "Temperature" and sensor.Value is not None:
                        val = float(sensor.Value)
                        if "Cpu" in hw_type:
                            cpu_temps.append(val)
                        elif "Gpu" in hw_type:
                            gpu_temps.append(val)

            if cpu_temps:
                # Prefer package/die temperature (usually max)
                self._cached_cpu = round(max(cpu_temps), 1)
            if gpu_temps:
                self._cached_gpu = round(max(gpu_temps), 1)
            else:
                self._cached_gpu = 0.0

        except Exception as e:
            logger.warning(f"Error querying hardware sensors: {e}")

    def get_temperatures(self) -> Tuple[float, float]:
        """Return (cpu_temp, gpu_temp)."""
        self.update()
        return self._cached_cpu, self._cached_gpu

    def get_effective_temp(self) -> float:
        """
        Return the primary effective temperature for fan regulation:
        max(cpu_temp, gpu_temp). If one sensor is 0 (e.g. dGPU asleep), uses the other.
        """
        cpu, gpu = self.get_temperatures()
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
        """Close sensor handles."""
        if self._computer:
            try:
                self._computer.Close()
            except Exception:
                pass
            self._computer = None
            self._is_initialized = False
