# flydigi_bs2_controller/core/ble_worker.py
"""
Asynchronous BLE Worker for Flydigi BS2 / BS2 Pro Laptop Cooler.
Manages automatic discovery, connection lifecycle, notify subscriptions,
and resilient auto-reconnect loops.
"""

import asyncio
from enum import Enum
import logging
import threading
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic

from flydigi_bs2_controller.core.protocol import BS2Protocol

logger = logging.getLogger(__name__)

SERVICE_UUID = "0000FFF0-0000-1000-8000-00805F9B34FB"
WRITE_UUID = "0000FFF2-0000-1000-8000-00805F9B34FB"
NOTIFY_UUID = "0000FFF1-0000-1000-8000-00805F9B34FB"
TARGET_NAME_PREFIXES = ["Flydigi BS2", "Flydigi BS1"]


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
        self.power_mode: int = 3  # 1: 5V, 2: 9V, 3: 20V
        self.is_smart_mode: bool = True

        # Callbacks
        self.on_state_change: Optional[Callable[[ConnectionState], None]] = None
        self.on_rpm_update: Optional[Callable[[int, int], None]] = None
        self.on_power_mode_update: Optional[Callable[[int], None]] = None

        # Threading & Asyncio internals
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._running = False
        self._client: Optional[BleakClient] = None
        self._command_queue: Optional[asyncio.Queue] = None

    @property
    def is_connected(self) -> bool:
        return self.state in (ConnectionState.CONNECTED, ConnectionState.SYNCED)

    def set_target_rpm(self, rpm: int) -> None:
        """Set target RPM for the control loop, clamped to [0, 4000]."""
        self.target_rpm = max(0, min(4000, int(rpm)))

    def _set_state(self, new_state: ConnectionState) -> None:
        if self.state != new_state:
            self.state = new_state
            logger.info(f"BLE state changed to: {new_state.value}")
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"Error in on_state_change callback: {e}")

    def _handle_notification(self, char: Optional[BleakGATTCharacteristic], data: bytes) -> None:
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

    def stop(self) -> None:
        """Stop background BLE worker thread cleanly."""
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._set_state(ConnectionState.DISCONNECTED)

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

    async def _main_worker_task(self) -> None:
        """Main async connection and monitoring loop."""
        self._set_state(ConnectionState.SCANNING)
        device = None

        try:
            devices = await BleakScanner.discover(timeout=4.0)
            for d in devices:
                if d.name and any(d.name.startswith(p) for p in TARGET_NAME_PREFIXES):
                    device = d
                    break
        except Exception as e:
            logger.warning(f"Error during BLE scanning: {e}")
            return

        if not device:
            logger.debug("No Flydigi cooler found, will retry...")
            return

        logger.info(f"Discovered cooler: {device.name} [{device.address}], connecting...")
        self._set_state(ConnectionState.CONNECTING)

        try:
            async with BleakClient(device.address, timeout=10.0) as client:
                self._client = client
                self._set_state(ConnectionState.CONNECTED)

                # Enable Notifications
                try:
                    await client.start_notify(NOTIFY_UUID, self._handle_notification)
                except Exception as e:
                    logger.warning(f"Failed to subscribe to Notify UUID: {e}")

                # Initial Handshake
                # 1. Query Fast Charge
                await client.write_gatt_char(WRITE_UUID, BS2Protocol.build_query_fast_charge(), response=False)
                await asyncio.sleep(0.2)

                # 2. Start Smart Mode
                if self.is_smart_mode:
                    await client.write_gatt_char(WRITE_UUID, BS2Protocol.build_start_smart(), response=False)
                    await asyncio.sleep(0.2)

                self._set_state(ConnectionState.SYNCED)

                # Active control loop
                last_pulse_time = 0.0
                while self._running and client.is_connected:
                    now = asyncio.get_event_loop().time()

                    # Process custom pending commands
                    while not self._command_queue.empty():
                        pkt = await self._command_queue.get()
                        await client.write_gatt_char(WRITE_UUID, pkt, response=False)

                    # 1-second periodic pulse
                    if now - last_pulse_time >= 1.0:
                        last_pulse_time = now
                        if self.is_smart_mode:
                            rpm_pkt = BS2Protocol.build_set_rpm(self.target_rpm)
                            await client.write_gatt_char(WRITE_UUID, rpm_pkt, response=False)
                            await asyncio.sleep(0.05)

                        # Query actual RPM
                        consult_pkt = BS2Protocol.build_consult_rpm()
                        await client.write_gatt_char(WRITE_UUID, consult_pkt, response=False)

                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.warning(f"BLE connection lost or error: {e}")
        finally:
            self._client = None
            self._set_state(ConnectionState.DISCONNECTED)
