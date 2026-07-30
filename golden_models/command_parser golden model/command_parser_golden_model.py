from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Optional


class Opcode(IntEnum):
    QUANTIZE = 0x1
    LOAD_ELEMENT = 0x2
    READ_ELEMENT = 0x3
    ADD = 0x4
    EL_MUL = 0x5
    DOT_PROD = 0x6
    MAT_MUL = 0x7
    MATRIX_CLR = 0x8
    RELU = 0x9
    CLAMP = 0xA
    SHIFT_ROW_COL = 0xB


EXPECTED_LENGTH: Dict[Opcode, int] = {
    Opcode.QUANTIZE: 7,
    Opcode.LOAD_ELEMENT: 3,
    Opcode.READ_ELEMENT: 2,
    Opcode.ADD: 1,
    Opcode.EL_MUL: 1,
    Opcode.DOT_PROD: 2,
    Opcode.MAT_MUL: 1,
    Opcode.MATRIX_CLR: 1,
    Opcode.RELU: 1,
    Opcode.CLAMP: 2,
    Opcode.SHIFT_ROW_COL: 2,
}


@dataclass(frozen=True)
class DecodedCommand:
    """Expected outputs for one completed command."""

    name: str
    opcode: int
    valid: bool
    trigger: Optional[str]
    fields: Dict[str, int]
    read_response_delay: Optional[int] = None


class CommandParserGoldenModel:
    """Transaction-level model of the command parser protocol."""

    def __init__(self, grid_size: int = 4) -> None:
        if grid_size < 2:
            raise ValueError("grid_size must be at least 2")

        self.grid_size = grid_size
        self.address_width = (grid_size - 1).bit_length()
        self.address_mask = (1 << self.address_width) - 1
        self.reset()

    def reset(self) -> None:
        """Discard any partially received packet."""
        self._packet: List[int] = []
        self._expected_length = 0

    def accept_byte(
        self,
        value: int,
        valid: bool = True,
    ) -> Optional[DecodedCommand]:
        """Accept one UART bus value.

        Args:
            value: Value on i_uart_rx_data.
            valid: Value of i_uart_rx_new.

        Returns:
            None if the byte is not valid or the packet is incomplete.
            A DecodedCommand when a complete packet has been received.
        """
        if not 0 <= value <= 0xFF:
            raise ValueError(f"UART byte must be in the range 0..255, got {value}")

        if not valid:
            return None

        if not self._packet:
            opcode_value = (value >> 4) & 0xF
            try:
                opcode = Opcode(opcode_value)
                self._expected_length = EXPECTED_LENGTH[opcode]
            except ValueError:
                # Unsupported opcodes complete as one-byte invalid commands.
                self._expected_length = 1

        self._packet.append(value)

        if len(self._packet) < self._expected_length:
            return None

        if len(self._packet) > self._expected_length:
            raise RuntimeError("Received more bytes than the selected command expects")

        packet = self._packet.copy()
        self.reset()
        return self._decode(packet)

    def decode_packet(self, packet: List[int]) -> DecodedCommand:
        """Decode one complete packet."""
        self.reset()
        result: Optional[DecodedCommand] = None

        for byte in packet:
            result = self.accept_byte(byte, valid=True)

        if result is None:
            raise ValueError("Packet is incomplete")

        return result

    def _row(self, byte: int) -> int:
        return (byte >> 4) & self.address_mask

    def _column(self, byte: int) -> int:
        return byte & self.address_mask

    def _decode(self, packet: List[int]) -> DecodedCommand:
        first_byte = packet[0]
        opcode_value = (first_byte >> 4) & 0xF

        try:
            opcode = Opcode(opcode_value)
        except ValueError:
            return DecodedCommand(
                name=f"INVALID_0x{opcode_value:X}",
                opcode=opcode_value,
                valid=False,
                trigger=None,
                fields={},
            )

        expected_length = EXPECTED_LENGTH[opcode]
        if len(packet) != expected_length:
            raise ValueError(
                f"{opcode.name} expects {expected_length} bytes, "
                f"but received {len(packet)}"
            )

        matrix_1 = (first_byte >> 2) & 0x3
        matrix_2 = first_byte & 0x3

        if opcode == Opcode.QUANTIZE:
            scale = (
                (packet[3] << 24) | (packet[4] << 16) | (packet[5] << 8) | packet[6]
            )
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_quantization_op",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_quantizer_target_dtype": (packet[1] >> 5) & 0x7,
                    "o_quantizer_zero_point": packet[2],
                    "o_quantizer_scale": scale,
                },
            )

        if opcode == Opcode.LOAD_ELEMENT:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_data_load",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_rows": self._row(packet[1]),
                    "o_matrix_cols": self._column(packet[1]),
                    "o_data": packet[2],
                },
            )

        if opcode == Opcode.READ_ELEMENT:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_data_read",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_rows": self._row(packet[1]),
                    "o_matrix_cols": self._column(packet[1]),
                },
                # RTL pulses o_uart_tx_new four rising edges after the final READ_ELEMENT byte is sampled.
                read_response_delay=4,
            )

        if opcode in (Opcode.ADD, Opcode.EL_MUL, Opcode.MAT_MUL):
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_arithmetic_op",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_2": matrix_2,
                    "o_arithmetic_op_type": opcode_value & 0x3,
                },
            )

        if opcode == Opcode.DOT_PROD:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_arithmetic_op",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_2": matrix_2,
                    "o_arithmetic_op_type": 0b10,
                    "o_matrix_rows": self._row(packet[1]),
                    "o_matrix_cols": self._column(packet[1]),
                },
            )

        if opcode == Opcode.MATRIX_CLR:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_matrix_config",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_signed": (first_byte >> 1) & 0x1,
                },
            )

        if opcode == Opcode.RELU:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_relu_op",
                fields={"o_matrix_1": matrix_1},
            )

        if opcode == Opcode.CLAMP:
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_clamp_op",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_clamp_max": packet[1],
                },
            )

        if opcode == Opcode.SHIFT_ROW_COL:
            shift_amount = self._row(packet[1])
            row_direction = (packet[1] >> 3) & 0x1
            return DecodedCommand(
                name=opcode.name,
                opcode=opcode_value,
                valid=True,
                trigger="o_shift_row" if row_direction else "o_shift_col",
                fields={
                    "o_matrix_1": matrix_1,
                    "o_matrix_rows": shift_amount,
                    "o_matrix_cols": shift_amount,
                },
            )

        raise AssertionError(f"Golden model does not handle opcode {opcode}")


if __name__ == "__main__":
    model = CommandParserGoldenModel(grid_size=4)

    example_packets = [
        [0x43],
        [0x61, 0x00],
        [0x2C, 0x33, 0xFF],
        [0x1C, 0xE0, 0x80, 0x3F, 0x80, 0x00, 0x00],
        [0xFF],
    ]

    for example in example_packets:
        print(f"{[f'{byte:02X}' for byte in example]} -> {model.decode_packet(example)}")
