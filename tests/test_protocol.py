# tests/test_protocol.py
import pytest
from flydigi_bs2_controller.core.protocol import BS2Protocol

def test_calc_checksum():
    # 0x01 + 0x02 = 0x03
    assert BS2Protocol.calc_checksum(0x01, 0x02, b"") == 0x03
    # 0x21 + 0x04 + 0xDC + 0x05 = 0x106 -> 0x06
    assert BS2Protocol.calc_checksum(0x21, 0x04, bytes([0xDC, 0x05])) == 0x06

def test_pack_unpack_command():
    pkt = BS2Protocol.pack(0x21, bytes([0xDC, 0x05]))
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x04, 0xDC, 0x05, 0x06])
    cmd, payload = BS2Protocol.unpack(pkt)
    assert cmd == 0x21
    assert payload == bytes([0xDC, 0x05])

    # Test backward compatibility with legacy format (total = length + 2)
    legacy_pkt = bytes([0x5A, 0xA5, 0x21, 0x05, 0xDC, 0x05, 0x07])
    l_cmd, l_payload = BS2Protocol.unpack(legacy_pkt)
    assert l_cmd == 0x21
    assert l_payload == bytes([0xDC, 0x05])

def test_fan_speed_command():
    pkt = BS2Protocol.build_set_rpm(1500)
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x04, 0xDC, 0x05, 0x06])

def test_fan_speed_clamp():
    # Negative should clamp to 0
    pkt_zero = BS2Protocol.build_set_rpm(-100)
    cmd, payload = BS2Protocol.unpack(pkt_zero)
    rpm = int.from_bytes(payload, "little")
    assert rpm == 0

    # Over 4000 should clamp to 4000
    pkt_max = BS2Protocol.build_set_rpm(5000)
    cmd, payload = BS2Protocol.unpack(pkt_max)
    rpm = int.from_bytes(payload, "little")
    assert rpm == 4000

def test_consult_rpm():
    req = BS2Protocol.build_consult_rpm()
    assert req == bytes([0x5A, 0xA5, 0x22, 0x02, 0x24])
    # Mock response: Current = 1300 (0x0514 -> 0x14, 0x05), Target = 2000 (0x07D0 -> 0xD0, 0x07)
    resp = BS2Protocol.pack(0x22, bytes([0x14, 0x05, 0xD0, 0x07]))
    cmd, payload = BS2Protocol.unpack(resp)
    cur_rpm, target_rpm = BS2Protocol.parse_consult_rpm(payload)
    assert cur_rpm == 1300
    assert target_rpm == 2000

def test_gear_led_and_auto_start():
    assert BS2Protocol.build_set_gear_led(True) == bytes([0x5A, 0xA5, 0x48, 0x03, 0x01, 0x4C])
    assert BS2Protocol.build_set_gear_led(False) == bytes([0x5A, 0xA5, 0x48, 0x03, 0x00, 0x4B])
    assert BS2Protocol.build_set_auto_start(True) == bytes([0x5A, 0xA5, 0x0C, 0x03, 0x01, 0x10])
    assert BS2Protocol.build_set_auto_start(False) == bytes([0x5A, 0xA5, 0x0C, 0x03, 0x00, 0x0F])

def test_smart_start_stop():
    assert BS2Protocol.build_set_smart_start_stop(1) == bytes([0x5A, 0xA5, 0x0D, 0x03, 0x01, 0x11])

def test_rgb_commands():
    assert BS2Protocol.build_set_rgb_state(True) == bytes([0x5A, 0xA5, 0x46, 0x03, 0x01, 0x4A])
    assert BS2Protocol.build_set_rgb_state(False) == bytes([0x5A, 0xA5, 0x46, 0x03, 0x00, 0x49])
    assert BS2Protocol.build_set_rgb_intelligent(1) == bytes([0x5A, 0xA5, 0x44, 0x03, 0x01, 0x48])

def test_firmware_and_manual_modes():
    # Firmware query
    assert BS2Protocol.build_query_firmware() == bytes([0x5A, 0xA5, 0x01, 0x02, 0x03])
    assert BS2Protocol.parse_firmware(bytes([1, 0, 0, 8])) == "v1.0.0.8"

    # Set manual gear (0x08)
    assert BS2Protocol.build_set_manual_gear(0) == bytes([0x5A, 0xA5, 0x08, 0x03, 0x00, 0x0B])
    assert BS2Protocol.build_set_manual_gear(3) == bytes([0x5A, 0xA5, 0x08, 0x03, 0x03, 0x0E])

    # Set mode and speed (0x26)
    # Mode 0 (1档), 1700 RPM (0x06A4 -> 0xA4, 0x06)
    assert BS2Protocol.build_set_mode_and_speed(0, 1700) == bytes(
        [0x5A, 0xA5, 0x26, 0x05, 0x00, 0xA4, 0x06, 0xD5]
    )

def test_rgb_table_and_transport():
    # Table generation for breathe
    table = BS2Protocol.build_rgb_config_table("breathe", (0, 120, 255), speed=15, brightness=100)
    assert len(table) == 306
    assert table[0] == 0 and table[1] == 2 and table[3] == 1 and table[4] == 15 and table[5] == 100
    # Group 0 Color 1
    assert table[9] == 0 and table[10] == 120 and table[11] == 255

    # Transport packets (prepare + 31 chunks + finish = 33 packets)
    pkts = BS2Protocol.get_rgb_transport_packets("breathe", (0, 120, 255))
    assert len(pkts) == 33
    assert pkts[0] == bytes([0x5A, 0xA5, 0x41, 0x02, 0x43])  # Prepare
    assert pkts[1].startswith(bytes([0x5A, 0xA5, 0x47, 0x0D, 0x00]))  # Order 0
    assert pkts[31].startswith(bytes([0x5A, 0xA5, 0x47, 0x0D, 0x1E]))  # Order 30 (0x1E)
    assert pkts[32] == bytes([0x5A, 0xA5, 0x43, 0x02, 0x45])  # Finish

def test_unpack_malformed():
    # Too short
    with pytest.raises(ValueError):
        BS2Protocol.unpack(b"\x5A\xA5")
    # Bad header
    with pytest.raises(ValueError):
        BS2Protocol.unpack(b"\x00\x00\x01\x03\x04")
    # Checksum mismatch
    with pytest.raises(ValueError):
        BS2Protocol.unpack(b"\x5A\xA5\x01\x03\xFF")
