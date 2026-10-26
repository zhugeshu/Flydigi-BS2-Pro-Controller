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
    CMD_SET_MANUAL_GEAR: int = 0x08
    CMD_AUTO_START: int = 0x0C
    CMD_SMART_START_STOP: int = 0x0D
    CMD_SET_RPM: int = 0x21
    CMD_CONSULT_RPM: int = 0x22
    CMD_START_SMART: int = 0x23
    CMD_END_SMART: int = 0x24
    CMD_SET_MODE: int = 0x26
    CMD_RGB_PREPARE: int = 0x41
    CMD_RGB_TRANSPORT: int = 0x42
    CMD_RGB_FINISH: int = 0x43
    CMD_SET_RGB_INTELLIGENT: int = 0x44
    CMD_SET_RGB_STATE: int = 0x46
    CMD_RGB_TRANSPORT_ORDER: int = 0x47
    CMD_SET_GEAR_LED: int = 0x48

    @staticmethod
    def calc_checksum(cmd_id: int, length: int, payload: bytes = b"") -> int:
        """Calculate 8-bit checksum: sum(cmd_id + length + payload) & 0xFF."""
        total = cmd_id + length + sum(payload)
        return total & 0xFF

    @classmethod
    def pack(cls, cmd_id: int, payload: bytes = b"") -> bytes:
        """
        Pack command into BS2 frame following Flydigi standard:
        [0x5A, 0xA5, cmd_id, length, payload..., checksum]
        where length = len(payload) + 2 (CmdId + Length).
        Total packet length is len(payload) + 5 = length + 3.
        """
        length = len(payload) + 2
        checksum = cls.calc_checksum(cmd_id, length, payload)
        return cls.HEADER + bytes([cmd_id, length]) + payload + bytes([checksum])

    @classmethod
    def unpack(cls, raw: bytes) -> Tuple[int, bytes]:
        """
        Unpack and validate a BS2 frame.
        Supports both official format (total = length + 3) and legacy format (total = length + 2).
        Returns: (cmd_id, payload)
        Raises: ValueError on invalid frame or checksum mismatch
        """
        if len(raw) < 5:
            raise ValueError(f"Packet too short ({len(raw)} bytes), minimum is 5")

        if raw[:2] != cls.HEADER:
            raise ValueError(f"Invalid frame header: {raw[:2].hex()}, expected 5aa5")

        cmd_id = raw[2]
        length = raw[3]

        if len(raw) != length + 3 and len(raw) != length + 2:
            raise ValueError(
                f"Length field mismatch: expected {length + 3} or {length + 2} total bytes, got {len(raw)}"
            )

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

    @classmethod
    def build_query_firmware(cls) -> bytes:
        """Query firmware version (Cmd 0x01)."""
        return cls.pack(cls.CMD_FIRMWARE)

    @staticmethod
    def parse_firmware(payload: bytes) -> str:
        """
        Parse firmware version from response to Cmd 0x01.
        Payload format: [major, minor, patch, build] or similar.
        """
        if not payload:
            return "v1.0.0"
        if len(payload) == 4:
            return f"v{payload[0]}.{payload[1]}.{payload[2]}.{payload[3]}"
        return "v" + ".".join(str(b) for b in payload)

    @classmethod
    def build_set_manual_gear(cls, gear: int) -> bytes:
        """
        Set manual fan speed gear (Cmd 0x08).
        gear: 0=1档(1700), 1=2档(2400), 2=3档(3000), 3=4档(4000)
        """
        clamped_gear = max(0, min(3, int(gear)))
        return cls.pack(cls.CMD_SET_MANUAL_GEAR, bytes([clamped_gear]))

    @classmethod
    def build_set_mode_and_speed(cls, gear: int, rpm: int) -> bytes:
        """
        Set fan speed mode and target speed (Cmd 0x26).
        gear: 0=1档, 1=2档, 2=3档, 3=4档, 4=SMART
        rpm: target RPM [0, 4000]
        """
        clamped_gear = max(0, min(4, int(gear)))
        clamped_rpm = max(0, min(4000, int(rpm)))
        payload = bytes([clamped_gear]) + clamped_rpm.to_bytes(2, byteorder="little")
        return cls.pack(cls.CMD_SET_MODE, payload)

    @classmethod
    def build_rgb_prepare(cls) -> bytes:
        """Notify hardware to prepare for RGB config transport (Cmd 0x41)."""
        return cls.pack(cls.CMD_RGB_PREPARE)

    @classmethod
    def build_rgb_finish(cls) -> bytes:
        """Notify hardware RGB config transport finished (Cmd 0x43)."""
        return cls.pack(cls.CMD_RGB_FINISH)

    @classmethod
    def build_rgb_transport_order(cls, order: int, chunk: bytes) -> bytes:
        """
        Send an ordered 10-byte slice of RGB config table (Cmd 0x47).
        order: sequence index (0 to 30)
        chunk: up to 10 bytes (padded with 0 to 10 bytes)
        """
        padded = chunk[:10].ljust(10, b"\x00")
        payload = bytes([order & 0xFF]) + padded
        return cls.pack(cls.CMD_RGB_TRANSPORT_ORDER, payload)

    @classmethod
    def build_rgb_config_table(
        cls,
        mode: str = "breathe",
        color: Tuple[int, int, int] = (0, 120, 255),
        speed: int = 15,
        brightness: int = 100,
    ) -> bytes:
        """
        Build the official 306-byte RGBConfig animation table for BS2 / BS2 Pro hardware.
        Supports 'breathe', 'pure', 'streamer', 'rotate'.
        """
        table = bytearray(306)
        table[0] = 0
        table[1] = 2  # Version 2
        table[2] = 0  # LoopStart 0
        table[4] = max(1, min(60, int(speed)))  # LoopTime (speed interval)
        table[5] = max(0, min(100, int(brightness)))  # LightScale (0~100)

        r, g, b = (max(0, min(255, c)) for c in color)

        if mode == "breathe":
            table[3] = 1  # LoopEnd 1 (cycles between black and target color)
            for grp in range(10):
                offset = 6 + grp * 30
                # Color 0: (0, 0, 0)
                # Color 1: target (r, g, b)
                table[offset + 3] = r
                table[offset + 4] = g
                table[offset + 5] = b
        elif mode == "pure":
            table[3] = 0  # LoopEnd 0 (solid color)
            for grp in range(10):
                offset = 6 + grp * 30
                table[offset + 0] = r
                table[offset + 1] = g
                table[offset + 2] = b
        elif mode == "streamer":
            table[3] = 5  # LoopEnd 5 (6 rainbow colors)
            base_colors = [
                (0, 0, 255),
                (0, 127, 127),
                (0, 255, 0),
                (127, 127, 0),
                (255, 0, 0),
                (127, 0, 127),
            ]
            for grp in range(10):
                offset = 6 + grp * 30
                shift = grp % 6
                shifted = base_colors[shift:] + base_colors[:shift]
                for c_idx, (cr, cg, cb) in enumerate(shifted):
                    c_off = offset + c_idx * 3
                    table[c_off] = cr
                    table[c_off + 1] = cg
                    table[c_off + 2] = cb
        elif mode == "rotate":
            table[3] = 5
            # Two-tone rotation with selected color and complementary/fade
            c1 = (r, g, b)
            c2 = (r // 4, g // 4, b // 4)
            c_cycle = [c1, c2, (0, 0, 0), (0, 0, 0), (0, 0, 0), c2]
            for grp in range(10):
                offset = 6 + grp * 30
                shift = grp % 6
                shifted = c_cycle[shift:] + c_cycle[:shift]
                for c_idx, (cr, cg, cb) in enumerate(shifted):
                    c_off = offset + c_idx * 3
                    table[c_off] = cr
                    table[c_off + 1] = cg
                    table[c_off + 2] = cb

        return bytes(table)

    @classmethod
    def get_rgb_transport_packets(
        cls,
        mode: str = "breathe",
        color: Tuple[int, int, int] = (0, 120, 255),
        speed: int = 15,
        brightness: int = 100,
    ) -> list:
        """
        Generate complete sequence of BLE packets to update hardware RGB animation table:
        1. RGBPrepare (0x41)
        2. 31 packets of RGBTransportOrder (0x47)
        3. RGBFinish (0x43)
        """
        table = cls.build_rgb_config_table(mode, color, speed, brightness)
        packets = [cls.build_rgb_prepare()]
        for order in range(31):
            chunk = table[order * 10 : (order + 1) * 10]
            packets.append(cls.build_rgb_transport_order(order, chunk))
        packets.append(cls.build_rgb_finish())
        return packets
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
