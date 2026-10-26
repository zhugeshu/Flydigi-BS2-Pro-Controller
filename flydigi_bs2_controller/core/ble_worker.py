# flydigi_bs2_controller/core/ble_worker.py
"""
Asynchronous BLE Worker for Flydigi BS2 / BS2 Pro Laptop Cooler.
Supports direct Windows WinRT paired GATT connection (instant, 100% reliable)
with automatic fallback to Bleak advertising scanner for unpaired devices.
"""

import asyncio
from enum import Enum
import logging
import threading
from typing import Callable, Optional, Tuple

from flydigi_bs2_controller.core.protocol import BS2Protocol

logger = logging.getLogger(__name__)

SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
TARGET_NAME_KEYWORDS = ["flydigi", "bs2", "bs1"]


class ConnectionState(Enum):
    DISCONNECTED = "已断开"
    SCANNING = "搜索设备中..."
    CONNECTING = "连接中..."
    CONNECTED = "已连接"
    SYNCED = "运行托管中"


class BLEWorker:
    def __init__(self):
        self.state = ConnectionState.DISCONNECTED
        self.current_rpm: int = 0
        self.target_rpm: int = 1300
        self.fixed_rpm: int = 2400
        self.fixed_gear: int = 1
        self.power_mode: int = 3  # 1: 5V, 2: 9V, 3: 20V
        self.is_smart_mode: bool = True
        self.firmware_version: str = "v1.0.0"

        # Callbacks
        self.on_state_change: Optional[Callable[[ConnectionState], None]] = None
        self.on_rpm_update: Optional[Callable[[int, int], None]] = None
        self.on_power_mode_update: Optional[Callable[[int], None]] = None
        self.on_firmware_update: Optional[Callable[[str], None]] = None
        self.on_synced: Optional[Callable[[], None]] = None

        # Threading & Asyncio internals
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._command_queue: Optional[asyncio.Queue] = None

        # WinRT handles
        self._device = None
        self._char_write = None
        self._char_notify = None

    @property
    def is_connected(self) -> bool:
        return self.state in (ConnectionState.CONNECTED, ConnectionState.SYNCED)

    def set_target_rpm(self, rpm: int) -> None:
        """Set target RPM for the control loop, clamped to [0, 4000]."""
        self.target_rpm = max(0, min(4000, int(rpm)))

    def set_fixed_speed(self, gear: int, rpm: int) -> None:
        """Switch to fixed speed mode and lock specified gear and RPM."""
        self.fixed_gear = max(0, min(3, int(gear)))
        self.fixed_rpm = max(0, min(4000, int(rpm)))
        self.is_smart_mode = False
        self.send_command(BS2Protocol.build_set_manual_gear(self.fixed_gear))
        self.send_command(BS2Protocol.build_set_mode_and_speed(self.fixed_gear, self.fixed_rpm))
        self.send_command(BS2Protocol.build_set_rpm(self.fixed_rpm))

    def set_smart_mode(self) -> None:
        """Switch to smart temperature control mode."""
        self.is_smart_mode = True
        self.send_command(BS2Protocol.build_start_smart())

    def send_rgb_animation(
        self,
        mode: str = "breathe",
        color: Tuple[int, int, int] = (0, 120, 255),
        speed: int = 15,
        brightness: int = 100,
    ) -> None:
        """Send complete 33-packet RGB animation sequence."""
        packets = BS2Protocol.get_rgb_transport_packets(mode, color, speed, brightness)
        for pkt in packets:
            self.send_command(pkt)

    def _set_state(self, new_state: ConnectionState) -> None:
        if self.state != new_state:
            self.state = new_state
            logger.info(f"BLE state changed to: {new_state.value}")
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"Error in on_state_change callback: {e}")
            if new_state == ConnectionState.SYNCED and self.on_synced:
                try:
                    self.on_synced()
                except Exception as e:
                    logger.error(f"Error in on_synced callback: {e}")

    def _handle_notification(self, char, data: bytes) -> None:
        """Parse incoming notification packet from Notify UUID."""
        try:
            cmd, payload = BS2Protocol.unpack(data)
            if cmd == BS2Protocol.CMD_CONSULT_RPM:
                cur, tgt = BS2Protocol.parse_consult_rpm(payload)
                self.current_rpm = cur
                if self.on_rpm_update:
                    self.on_rpm_update(cur, tgt)
            elif cmd == BS2Protocol.CMD_FAST_CHARGE:
                mode = BS2Protocol.parse_fast_charge(payload)
                self.power_mode = mode
                if self.on_power_mode_update:
                    self.on_power_mode_update(mode)
            elif cmd == BS2Protocol.CMD_FIRMWARE:
                fw = BS2Protocol.parse_firmware(payload)
                self.firmware_version = fw
                if self.on_firmware_update:
                    self.on_firmware_update(fw)
        except Exception as e:
            logger.debug(f"Failed to parse notify packet: {data.hex()}: {e}")

    def send_command(self, packet: bytes) -> None:
        """Enqueue command packet to be sent to device asynchronously."""
        if self._loop and self._command_queue:
            self._loop.call_soon_threadsafe(self._command_queue.put_nowait, packet)

    def start(self) -> None:
        """Start background BLE worker thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="BLEWorkerThread", daemon=True)
        self._thread.start()

    def disconnect_and_release(self) -> None:
        """Gracefully send 0x24 release packet and stop BLE event loop."""
        if not self._running:
            return
        self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._set_state(ConnectionState.DISCONNECTED)

    def stop(self) -> None:
        """Stop background BLE worker thread cleanly."""
        self.disconnect_and_release()

    def _run_loop(self) -> None:
        """Thread entry point."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._command_queue = asyncio.Queue()

        while self._running:
            try:
                self._loop.run_until_complete(self._main_worker_task())
            except Exception as e:
                logger.error(f"Unhandled BLE worker exception: {e}")
            if self._running:
                import time
                time.sleep(3.0)

        self._loop.close()

    async def _write_bytes(self, data: bytes) -> None:
        if self._char_write:
            from winrt.windows.storage.streams import DataWriter
            w = DataWriter()
            w.write_bytes(data)
            await self._char_write.write_value_async(w.detach_buffer())

    async def _find_target_device_id(self) -> Optional[str]:
        """Search paired Bluetooth devices via WinRT."""
        try:
            from winrt.windows.devices.bluetooth import BluetoothLEDevice
            from winrt.windows.devices.enumeration import DeviceInformation

            selector = BluetoothLEDevice.get_device_selector_from_pairing_state(True)
            devices = await DeviceInformation.find_all_async_aqs_filter(selector)
            for d in devices:
                name_lower = d.name.lower()
                if any(kw in name_lower for kw in TARGET_NAME_KEYWORDS):
                    logger.info(f"Matched paired cooler: {d.name} [{d.id}]")
                    return d.id
        except Exception as e:
            logger.warning(f"Error checking paired devices: {e}")
        return None

    async def _main_worker_task(self) -> None:
        """Main async connection and monitoring loop using WinRT."""
        self._set_state(ConnectionState.SCANNING)

        device_id = await self._find_target_device_id()
        if not device_id:
            # Fallback scan via Bleak if not paired yet
            logger.debug("No paired Flydigi cooler found, scanning advertisements...")
            try:
                from bleak import BleakScanner
                dev = await BleakScanner.find_device_by_filter(
                    lambda d, adv: d.name and any(kw in d.name.lower() for kw in TARGET_NAME_KEYWORDS),
                    timeout=4.0,
                )
                if dev:
                    device_id = dev.details.device_id if hasattr(dev.details, "device_id") else dev.address
            except Exception as e:
                logger.debug(f"Bleak scanner fallback error: {e}")

        if not device_id:
            logger.debug("No Flydigi cooler found, will retry...")
            return

        self._set_state(ConnectionState.CONNECTING)

        try:
            from winrt.windows.devices.bluetooth import BluetoothLEDevice
            from winrt.windows.devices.bluetooth.genericattributeprofile import (
                GattClientCharacteristicConfigurationDescriptorValue,
            )
            from winrt.windows.storage.streams import DataReader

            if device_id.startswith("BluetoothLE#"):
                dev = await BluetoothLEDevice.from_id_async(device_id)
            else:
                addr_int = int(device_id.replace(":", ""), 16)
                dev = await BluetoothLEDevice.from_bluetooth_address_async(addr_int)

            if not dev:
                logger.warning("Failed to instantiate BluetoothLEDevice from ID")
                return

            self._device = dev
            s_res = await dev.get_gatt_services_async()
            target_service = None
            for s in s_res.services:
                if "fff0" in str(s.uuid).lower():
                    target_service = s
                    break

            if not target_service:
                logger.warning("Service 0xFFF0 not found on device")
                return

            c_res = await target_service.get_characteristics_async()
            for c in c_res.characteristics:
                uuid_str = str(c.uuid).lower()
                if "fff2" in uuid_str:
                    self._char_write = c
                elif "fff1" in uuid_str:
                    self._char_notify = c

            if not self._char_write or not self._char_notify:
                logger.warning("Write or Notify characteristic missing on 0xFFF0")
                return

            # Set up notification handler
            def on_notify_val(sender, args):
                r = DataReader.from_buffer(args.characteristic_value)
                buf = bytearray(r.unconsumed_buffer_length)
                r.read_bytes(buf)
                self._handle_notification(None, bytes(buf))

            self._char_notify.add_value_changed(on_notify_val)
            await self._char_notify.write_client_characteristic_configuration_descriptor_async(
                GattClientCharacteristicConfigurationDescriptorValue.NOTIFY
            )

            self._set_state(ConnectionState.CONNECTED)

            # Initial handshake:
            # 1. Query Fast Charge
            await self._write_bytes(BS2Protocol.build_query_fast_charge())
            await asyncio.sleep(0.15)

            # 2. Query Firmware Version
            await self._write_bytes(BS2Protocol.build_query_firmware())
            await asyncio.sleep(0.15)

            # 3. Start Smart Mode or Set Fixed Mode
            if self.is_smart_mode:
                await self._write_bytes(BS2Protocol.build_start_smart())
            else:
                await self._write_bytes(BS2Protocol.build_set_manual_gear(self.fixed_gear))
                await self._write_bytes(BS2Protocol.build_set_rpm(self.fixed_rpm))
            await asyncio.sleep(0.15)

            self._set_state(ConnectionState.SYNCED)

            # Active control loop
            last_pulse_time = 0.0
            while self._running:
                # Check connection status (0: Disconnected, 1: Connected)
                if dev.connection_status == 0:
                    logger.warning("Device disconnected in Windows")
                    break

                now = asyncio.get_event_loop().time()

                # Process pending commands from queue
                while not self._command_queue.empty():
                    pkt = await self._command_queue.get()
                    await self._write_bytes(pkt)

                # 1-second periodic pulse
                if now - last_pulse_time >= 1.0:
                    last_pulse_time = now
                    if self.is_smart_mode:
                        rpm_pkt = BS2Protocol.build_set_rpm(self.target_rpm)
                        await self._write_bytes(rpm_pkt)
                        await asyncio.sleep(0.05)
                    else:
                        # In fixed mode, maintain locked target speed
                        rpm_pkt = BS2Protocol.build_set_rpm(self.fixed_rpm)
                        await self._write_bytes(rpm_pkt)
                        await asyncio.sleep(0.05)

                    # Query actual RPM
                    consult_pkt = BS2Protocol.build_consult_rpm()
                    await self._write_bytes(consult_pkt)

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"BLE connection lost or error: {e}")
        finally:
            if self._char_write:
                try:
                    await self._write_bytes(BS2Protocol.build_end_smart())
                    await asyncio.sleep(0.1)
                except Exception:
                    pass
            self._device = None
            self._char_write = None
            self._char_notify = None
            self._set_state(ConnectionState.DISCONNECTED)
