# flydigi_bs2_controller/core/protocol.py
"""
Flydigi BS2 / BS2 Pro Bluetooth Low Energy (BLE) communication protocol implementation.
Reverse-engineered from Flydigi Space Station 3.0 (BLEServiceController.dll).
"""

from typing import Tuple


class BS2Protocol:
    HEADER: bytes = b"\x5A\xA5"

    # Command IDs
    CMD_FIRMWARE: int = 0x01
    CMD_FAST_CHARGE: int = 0x07
    CMD_AUTO_START: int = 0x0C
    CMD_SMART_START_STOP: int = 0x0D
    CMD_SET_RPM: int = 0x21
    CMD_CONSULT_RPM: int = 0x22
    CMD_START_SMART: int = 0x23
    CMD_END_SMART: int = 0x24
    CMD_SET_MODE: int = 0x26
    CMD_SET_RGB_INTELLIGENT: int = 0x44
    CMD_SET_RGB_STATE: int = 0x46
    CMD_SET_GEAR_LED: int = 0x48

    @staticmethod
    def calc_checksum(cmd_id: int, length: int, payload: bytes = b"") -> int:
        """Calculate 8-bit checksum: sum(cmd_id + length + payload) & 0xFF."""
        total = cmd_id + length + sum(payload)
        return total & 0xFF

    @classmethod
    def pack(cls, cmd_id: int, payload: bytes = b"") -> bytes:
        """
        Pack command into BS2 frame:
        [0x5A, 0xA5, cmd_id, length, payload..., checksum]
        where length = len(payload) + 3 (CmdId + Length + Checksum)
        """
        length = len(payload) + 3
        checksum = cls.calc_checksum(cmd_id, length, payload)
        return cls.HEADER + bytes([cmd_id, length]) + payload + bytes([checksum])

    @classmethod
    def unpack(cls, raw: bytes) -> Tuple[int, bytes]:
        """
        Unpack and validate a BS2 frame.
        Returns: (cmd_id, payload)
        Raises: ValueError on invalid frame or checksum mismatch
        """
        if len(raw) < 5:
            raise ValueError(f"Packet too short ({len(raw)} bytes), minimum is 5")

        if raw[:2] != cls.HEADER:
            raise ValueError(f"Invalid frame header: {raw[:2].hex()}, expected 5aa5")

        cmd_id = raw[2]
        length = raw[3]

        if len(raw) != length + 2:
            raise ValueError(f"Length field mismatch: expected {length + 2} total bytes, got {len(raw)}")

        payload = raw[4:-1]
        received_checksum = raw[-1]
        expected_checksum = cls.calc_checksum(cmd_id, length, payload)

        if received_checksum != expected_checksum:
            raise ValueError(
                f"Checksum mismatch for cmd 0x{cmd_id:02X}: got 0x{received_checksum:02X}, expected 0x{expected_checksum:02X}"
            )

        return cmd_id, payload

    @classmethod
    def build_set_rpm(cls, rpm: int) -> bytes:
        """Build target RPM command (Cmd 0x21). RPM clamped to [0, 4000]."""
        clamped_rpm = max(0, min(4000, int(rpm)))
        payload = clamped_rpm.to_bytes(2, byteorder="little", signed=False)
        return cls.pack(cls.CMD_SET_RPM, payload)

    @classmethod
    def build_consult_rpm(cls) -> bytes:
        """Build query command for current and target RPM (Cmd 0x22)."""
        return cls.pack(cls.CMD_CONSULT_RPM)

    @staticmethod
    def parse_consult_rpm(payload: bytes) -> Tuple[int, int]:
        """
        Parse response payload from Cmd 0x22:
        Payload format: [current_rpm_lo, current_rpm_hi, target_rpm_lo, target_rpm_hi]
        Returns: (current_rpm, target_rpm)
        """
        if len(payload) < 4:
            raise ValueError(f"Consult RPM payload too short ({len(payload)} bytes), expected >= 4")
        current_rpm = int.from_bytes(payload[0:2], byteorder="little")
        target_rpm = int.from_bytes(payload[2:4], byteorder="little")
        return current_rpm, target_rpm

    @classmethod
    def build_start_smart(cls) -> bytes:
        """Start smart frequency conversion mode (Cmd 0x23)."""
        return cls.pack(cls.CMD_START_SMART)

    @classmethod
    def build_end_smart(cls) -> bytes:
        """Exit smart frequency conversion mode (Cmd 0x24)."""
        return cls.pack(cls.CMD_END_SMART)

    @classmethod
    def build_set_gear_led(cls, enabled: bool) -> bytes:
        """Set gear indicator LED display on/off (Cmd 0x48)."""
        return cls.pack(cls.CMD_SET_GEAR_LED, bytes([1 if enabled else 0]))

    @classmethod
    def build_set_auto_start(cls, enabled: bool) -> bytes:
        """Set power-on auto start on/off (Cmd 0x0C)."""
        return cls.pack(cls.CMD_AUTO_START, bytes([1 if enabled else 0]))

    @classmethod
    def build_set_smart_start_stop(cls, mode: int) -> bytes:
        """Set smart start-stop mode (Cmd 0x0D): 0=off, 1=instant, 2=delay."""
        return cls.pack(cls.CMD_SMART_START_STOP, bytes([int(mode)]))

    @classmethod
    def build_set_rgb_state(cls, is_on: bool) -> bytes:
        """Turn RGB light on/off (Cmd 0x46)."""
        return cls.pack(cls.CMD_SET_RGB_STATE, bytes([1 if is_on else 0]))

    @classmethod
    def build_set_rgb_intelligent(cls, mode: int) -> bytes:
        """Set intelligent RGB following temperature gear (Cmd 0x44)."""
        return cls.pack(cls.CMD_SET_RGB_INTELLIGENT, bytes([int(mode)]))

    @classmethod
    def build_query_fast_charge(cls) -> bytes:
        """Query fast charge power mode (Cmd 0x07)."""
        return cls.pack(cls.CMD_FAST_CHARGE)

    @staticmethod
    def parse_fast_charge(payload: bytes) -> int:
        """
        Parse fast charge mode from response to Cmd 0x07:
        1 = 5V (max 2700 RPM)
        2 = 9V (max 3300 RPM)
        3 = 20V PD (max 4000 RPM)
        """
        if not payload:
            return 1
        return payload[0]
