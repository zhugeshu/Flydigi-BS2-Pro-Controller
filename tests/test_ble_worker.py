# tests/test_ble_worker.py
import pytest
from flydigi_bs2_controller.core.ble_worker import BLEWorker, ConnectionState
from flydigi_bs2_controller.core.protocol import BS2Protocol

def test_worker_initial_state():
    worker = BLEWorker()
    assert worker.state == ConnectionState.DISCONNECTED
    assert worker.current_rpm == 0
    assert worker.target_rpm == 1300
    assert worker.power_mode == 3  # default assumed 20V until read
    assert worker.is_connected is False

def test_worker_target_rpm_update():
    worker = BLEWorker()
    worker.set_target_rpm(2500)
    assert worker.target_rpm == 2500
    worker.set_target_rpm(5000)
    assert worker.target_rpm == 4000  # clamped

def test_notification_packet_parsing():
    worker = BLEWorker()
    received_rpm = []
    worker.on_rpm_update = lambda cur, tgt: received_rpm.append((cur, tgt))

    # Simulate Cmd 0x22 (RPM Consult) Notify packet:
    # 5A A5 22 06 14 05 D0 07 <chk> (Cur: 1300, Tgt: 2000)
    notify_pkt = BS2Protocol.pack(0x22, bytes([0x14, 0x05, 0xD0, 0x07]))
    worker._handle_notification(None, notify_pkt)

    assert worker.current_rpm == 1300
    assert len(received_rpm) == 1
    assert received_rpm[0] == (1300, 2000)

def test_notification_fast_charge_parsing():
    worker = BLEWorker()
    power_updates = []
    worker.on_power_mode_update = lambda mode: power_updates.append(mode)

    # Simulate Cmd 0x07 (Fast Charge) Notify packet:
    # 5A A5 07 03 03 <chk> (Mode 3: 20V)
    notify_pkt = BS2Protocol.pack(0x07, bytes([0x03]))
    worker._handle_notification(None, notify_pkt)

    assert worker.power_mode == 3
    assert power_updates == [3]

def test_worker_synced_callback():
    """Verify Important Finding 7: Entering SYNCED triggers on_synced callback for full state broadcast."""
    worker = BLEWorker()
    synced_events = []
    worker.on_synced = lambda: synced_events.append(True)

    worker._set_state(ConnectionState.CONNECTING)
    assert len(synced_events) == 0

    worker._set_state(ConnectionState.SYNCED)
    assert len(synced_events) == 1
