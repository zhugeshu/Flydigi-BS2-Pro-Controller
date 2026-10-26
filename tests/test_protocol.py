# tests/test_protocol.py
import pytest
from flydigi_bs2_controller.core.protocol import BS2Protocol

def test_calc_checksum():
    # 0x01 + 0x03 = 0x04
    assert BS2Protocol.calc_checksum(0x01, 0x03, b"") == 0x04
    # 0x21 + 0x05 + 0xDC + 0x05 = 0x107 -> 0x07
    assert BS2Protocol.calc_checksum(0x21, 0x05, bytes([0xDC, 0x05])) == 0x07

def test_pack_unpack_command():
    pkt = BS2Protocol.pack(0x21, bytes([0xDC, 0x05]))
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x05, 0xDC, 0x05, 0x07])
    cmd, payload = BS2Protocol.unpack(pkt)
    assert cmd == 0x21
    assert payload == bytes([0xDC, 0x05])

def test_fan_speed_command():
    pkt = BS2Protocol.build_set_rpm(1500)
    assert pkt == bytes([0x5A, 0xA5, 0x21, 0x05, 0xDC, 0x05, 0x07])

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
    assert req == bytes([0x5A, 0xA5, 0x22, 0x03, 0x25])
    # Mock response: Current = 1300 (0x0514 -> 0x14, 0x05), Target = 2000 (0x07D0 -> 0xD0, 0x07)
    resp = BS2Protocol.pack(0x22, bytes([0x14, 0x05, 0xD0, 0x07]))
    cmd, payload = BS2Protocol.unpack(resp)
    cur_rpm, target_rpm = BS2Protocol.parse_consult_rpm(payload)
    assert cur_rpm == 1300
    assert target_rpm == 2000

def test_gear_led_and_auto_start():
    assert BS2Protocol.build_set_gear_led(True) == bytes([0x5A, 0xA5, 0x48, 0x04, 0x01, 0x4D])
    assert BS2Protocol.build_set_gear_led(False) == bytes([0x5A, 0xA5, 0x48, 0x04, 0x00, 0x4C])
    assert BS2Protocol.build_set_auto_start(True) == bytes([0x5A, 0xA5, 0x0C, 0x04, 0x01, 0x11])
    assert BS2Protocol.build_set_auto_start(False) == bytes([0x5A, 0xA5, 0x0C, 0x04, 0x00, 0x10])

def test_smart_start_stop():
    assert BS2Protocol.build_set_smart_start_stop(1) == bytes([0x5A, 0xA5, 0x0D, 0x04, 0x01, 0x12])

def test_rgb_commands():
    assert BS2Protocol.build_set_rgb_state(True) == bytes([0x5A, 0xA5, 0x46, 0x04, 0x01, 0x4B])
    assert BS2Protocol.build_set_rgb_state(False) == bytes([0x5A, 0xA5, 0x46, 0x04, 0x00, 0x4A])
    assert BS2Protocol.build_set_rgb_intelligent(1) == bytes([0x5A, 0xA5, 0x44, 0x04, 0x01, 0x49])

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
