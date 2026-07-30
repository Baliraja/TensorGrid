"""Complete cocotb scoreboard for command_parser_updated.sv.

This test reproduces the 144 cases in command_parser_TB_updated.sv:
    TC1.1
    TC2.1--TC2.11
    TC3.1--TC3.13
    TC4.1--TC4.5
    TC5.1--TC5.3
    TC6.1--TC6.16
    TC7.1--TC7.16
    TC8.1--TC8.16
    TC9.1--TC9.17
    TC10.1--TC10.8
    TC11.1--TC11.5
    TC12.1--TC12.9
    TC13.1--TC13.17
    TC14.1--TC14.5
    TC15.1
    TC16.1

Every case is checked automatically and the simulation prints a complete
PASS/FAIL summary.
"""

from dataclasses import dataclass
import random
from typing import List, Optional, Tuple

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

from command_parser_golden_model import (
    CommandParserGoldenModel,
    DecodedCommand,
)


CLOCK_PERIOD_NS = 10
INTER_BYTE_IDLE_CYCLES = 10
TOTAL_EXPECTED_TESTS = 144

TRIGGER_SIGNALS = (
    "o_matrix_config",
    "o_data_load",
    "o_data_read",
    "o_shift_row",
    "o_shift_col",
    "o_arithmetic_op",
    "o_quantization_op",
    "o_relu_op",
    "o_clamp_op",
)

RESET_EXPECTATIONS = {
    "o_uart_tx_data": 0,
    "o_uart_tx_new": 0,
    "o_matrix_config": 0,
    "o_matrix_signed": 0,
    "o_data_load": 0,
    "o_data_read": 0,
    "o_shift_row": 0,
    "o_shift_col": 0,
    "o_arithmetic_op": 0,
    "o_arithmetic_op_type": 0,
    "o_quantization_op": 0,
    "o_relu_op": 0,
    "o_clamp_op": 0,
    "o_clamp_max": 0,
    "o_matrix_1": 0,
    "o_matrix_2": 0,
    "o_matrix_rows": 0,
    "o_matrix_cols": 0,
    "o_data": 0,
    "o_quantizer_scale": 0,
    "o_quantizer_zero_point": 0,
    "o_quantizer_target_dtype": 0,
}


@dataclass(frozen=True)
class TestVector:
    test_id: str
    description: str
    packet: Tuple[int, ...]
    read_data: Optional[int] = None


class Scoreboard:
    """Collect all mismatches and print one result for every test case."""

    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.failed_tests: List[Tuple[str, List[str]]] = []
        self._test_id = ""
        self._description = ""
        self._errors: List[str] = []

    def begin(self, test_id: str, description: str) -> None:
        self._test_id = test_id
        self._description = description
        self._errors = []

    def error(self, message: str) -> None:
        self._errors.append(message)

    def check_equal(self, dut, signal_name: str, expected: int, context: str = "") -> None:
        raw_value = getattr(dut, signal_name).value
        try:
            actual = int(raw_value)
        except (TypeError, ValueError):
            self.error(
                f"{context}{signal_name}: expected 0x{expected:X}, "
                f"received unresolved value {raw_value}"
            )
            return

        if actual != expected:
            self.error(
                f"{context}{signal_name}: expected 0x{expected:X}, "
                f"received 0x{actual:X}"
            )

    def check_triggers(
        self,
        dut,
        expected_trigger: Optional[str],
        context: str = "",
    ) -> None:
        for signal_name in TRIGGER_SIGNALS:
            expected = 1 if signal_name == expected_trigger else 0
            self.check_equal(dut, signal_name, expected, context)

    def end(self) -> None:
        self.total += 1

        if self._errors:
            self.failed += 1
            self.failed_tests.append((self._test_id, self._errors.copy()))
            cocotb.log.error(
                "[FAIL] %s — %s",
                self._test_id,
                self._description,
            )
            for message in self._errors:
                cocotb.log.error("       %s", message)
        else:
            self.passed += 1
            cocotb.log.info(
                "[PASS] %s — %s",
                self._test_id,
                self._description,
            )

    def print_summary(self) -> None:
        line = "=" * 72
        cocotb.log.info(line)
        cocotb.log.info("COMMAND PARSER SCOREBOARD SUMMARY")
        cocotb.log.info("Total tests : %d", self.total)
        cocotb.log.info("Passed      : %d", self.passed)
        cocotb.log.info("Failed      : %d", self.failed)
        cocotb.log.info(line)

        if self.failed_tests:
            cocotb.log.error("FAILED TESTS")
            for test_id, errors in self.failed_tests:
                cocotb.log.error("  %s", test_id)
                for message in errors:
                    cocotb.log.error("    - %s", message)


def quantize_packet(
    matrix: int,
    dtype: int,
    zero_point: int,
    scale: int,
    header_reserved: int = 0,
    dtype_reserved: int = 0,
) -> Tuple[int, ...]:
    return (
        0x10 | ((matrix & 0x3) << 2) | (header_reserved & 0x3),
        ((dtype & 0x7) << 5) | (dtype_reserved & 0x1F),
        zero_point & 0xFF,
        (scale >> 24) & 0xFF,
        (scale >> 16) & 0xFF,
        (scale >> 8) & 0xFF,
        scale & 0xFF,
    )


def load_packet(
    matrix: int,
    row: int,
    column: int,
    data: int,
    reserved: int = 0,
) -> Tuple[int, ...]:
    return (
        0x20 | ((matrix & 0x3) << 2) | (reserved & 0x3),
        ((row & 0xF) << 4) | (column & 0xF),
        data & 0xFF,
    )


def read_packet(
    matrix: int,
    row: int,
    column: int,
    reserved: int = 0,
) -> Tuple[int, ...]:
    return (
        0x30 | ((matrix & 0x3) << 2) | (reserved & 0x3),
        ((row & 0xF) << 4) | (column & 0xF),
    )


def arithmetic_packet(opcode: int, matrix_1: int, matrix_2: int) -> Tuple[int, ...]:
    return (
        ((opcode & 0xF) << 4) | ((matrix_1 & 0x3) << 2) | (matrix_2 & 0x3),
    )


def dot_packet(
    matrix_1: int,
    matrix_2: int,
    row: int,
    column: int,
) -> Tuple[int, ...]:
    return (
        0x60 | ((matrix_1 & 0x3) << 2) | (matrix_2 & 0x3),
        ((row & 0xF) << 4) | (column & 0xF),
    )


def clear_packet(matrix: int, signed_mode: int) -> Tuple[int, ...]:
    return (
        0x80 | ((matrix & 0x3) << 2) | ((signed_mode & 0x1) << 1),
    )


def relu_packet(matrix: int, reserved: int = 0) -> Tuple[int, ...]:
    return (
        0x90 | ((matrix & 0x3) << 2) | (reserved & 0x3),
    )


def clamp_packet(matrix: int, clamp_max: int, reserved: int = 0) -> Tuple[int, ...]:
    return (
        0xA0 | ((matrix & 0x3) << 2) | (reserved & 0x3),
        clamp_max & 0xFF,
    )


def shift_packet(
    matrix: int,
    shift_amount: int,
    row_direction: int,
    header_reserved: int = 0,
    detail_reserved: int = 0,
) -> Tuple[int, ...]:
    return (
        0xB0 | ((matrix & 0x3) << 2) | (header_reserved & 0x3),
        ((shift_amount & 0xF) << 4) | ((row_direction & 0x1) << 3) | (detail_reserved & 0x7),
    )


def build_test_vectors() -> List[TestVector]:
    """Build the 141 ordinary packet cases from the SystemVerilog TB."""
    tests: List[TestVector] = []

    # TC2: Original randomized tests.
    rng = random.Random(0xC0A11D)

    random_matrix = rng.randrange(4)
    random_dtype = rng.randrange(8)
    random_zero_point = rng.randrange(256)
    random_exponent = rng.randrange(255)
    random_mantissa = rng.randrange(1 << 23)
    random_scale = (random_exponent << 23) | random_mantissa
    tests.append(
        TestVector(
            "TC2.1",
            "Randomized QUANTIZE",
            quantize_packet(
                random_matrix,
                random_dtype,
                random_zero_point,
                random_scale,
            ),
        )
    )

    tests.append(
        TestVector(
            "TC2.2",
            "Randomized LOAD_ELEMENT",
            load_packet(
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(256),
            ),
        )
    )

    tests.append(
        TestVector(
            "TC2.3",
            "Randomized READ_ELEMENT",
            read_packet(
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(4),
            ),
            read_data=rng.randrange(256),
        )
    )

    tests.append(
        TestVector(
            "TC2.4",
            "Randomized ADD",
            arithmetic_packet(0x4, rng.randrange(4), rng.randrange(4)),
        )
    )
    tests.append(
        TestVector(
            "TC2.5",
            "Randomized EL_MUL",
            arithmetic_packet(0x5, rng.randrange(4), rng.randrange(4)),
        )
    )
    tests.append(
        TestVector(
            "TC2.6",
            "Randomized MAT_MUL",
            arithmetic_packet(0x7, rng.randrange(4), rng.randrange(4)),
        )
    )
    tests.append(
        TestVector(
            "TC2.7",
            "Randomized DOT_PROD",
            dot_packet(
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(4),
            ),
        )
    )
    tests.append(
        TestVector(
            "TC2.8",
            "Randomized CLEAR_MATRIX",
            clear_packet(rng.randrange(4), rng.randrange(2)),
        )
    )
    tests.append(
        TestVector(
            "TC2.9",
            "Randomized RELU",
            relu_packet(rng.randrange(4)),
        )
    )
    tests.append(
        TestVector(
            "TC2.10",
            "Randomized CLAMP",
            clamp_packet(rng.randrange(4), rng.randrange(256)),
        )
    )
    tests.append(
        TestVector(
            "TC2.11",
            "Randomized SHIFT_ROW_COL",
            shift_packet(
                rng.randrange(4),
                rng.randrange(4),
                rng.randrange(2),
            ),
        )
    )

    # TC3: QUANTIZE corner and datatype cases.
    tests.append(
        TestVector(
            "TC3.1",
            "QUANTIZE minimum field values",
            quantize_packet(0, 0, 0x00, 0x00000000),
        )
    )
    tests.append(
        TestVector(
            "TC3.2",
            "QUANTIZE maximum raw field values",
            quantize_packet(3, 7, 0xFF, 0xFFFFFFFF),
        )
    )

    for dtype in range(8):
        tests.append(
            TestVector(
                f"TC3.{3 + dtype}",
                f"QUANTIZE datatype encoding {dtype}",
                quantize_packet(dtype % 4, dtype, 0x80, 0x3F800000),
            )
        )

    tests.append(
        TestVector(
            "TC3.11",
            "QUANTIZE negative scale bit pattern",
            quantize_packet(2, 0, 0x80, 0xBF800000),
        )
    )
    tests.append(
        TestVector(
            "TC3.12",
            "QUANTIZE distinct-byte scale ordering",
            quantize_packet(3, 6, 0xA6, 0x12345678),
        )
    )
    tests.append(
        TestVector(
            "TC3.13",
            "QUANTIZE reserved bits set",
            quantize_packet(
                1,
                4,
                0x55,
                0x3F000000,
                header_reserved=0b11,
                dtype_reserved=0b11111,
            ),
        )
    )

    # TC4: LOAD_ELEMENT.
    tests.extend(
        [
            TestVector("TC4.1", "LOAD minimum address/data", load_packet(0, 0, 0, 0x00)),
            TestVector("TC4.2", "LOAD maximum address/data", load_packet(3, 3, 3, 0xFF)),
            TestVector("TC4.3", "LOAD repeated address first value", load_packet(1, 2, 2, 0xAA)),
            TestVector("TC4.4", "LOAD repeated address replacement", load_packet(1, 2, 2, 0x55)),
            TestVector(
                "TC4.5",
                "LOAD reserved bits set",
                load_packet(2, 1, 3, 0xA5, reserved=0b11),
            ),
        ]
    )

    # TC5: READ_ELEMENT.
    tests.extend(
        [
            TestVector("TC5.1", "READ minimum address", read_packet(0, 0, 0), read_data=0x00),
            TestVector("TC5.2", "READ maximum address", read_packet(3, 3, 3), read_data=0xFF),
            TestVector(
                "TC5.3",
                "READ reserved bits set",
                read_packet(2, 1, 2, reserved=0b11),
                read_data=0x5A,
            ),
        ]
    )

    # TC6, TC7, TC8: All source-matrix pairs.
    arithmetic_groups = (
        ("TC6", 0x4, "ADD"),
        ("TC7", 0x5, "EL_MUL"),
        ("TC8", 0x7, "MAT_MUL"),
    )
    for prefix, opcode, name in arithmetic_groups:
        index = 1
        for matrix_1 in range(4):
            for matrix_2 in range(4):
                tests.append(
                    TestVector(
                        f"{prefix}.{index}",
                        f"{name} source pair ({matrix_1},{matrix_2})",
                        arithmetic_packet(opcode, matrix_1, matrix_2),
                    )
                )
                index += 1

    # TC9: DOT_PROD source combinations and maximum destination address.
    index = 1
    for matrix_1 in range(4):
        for matrix_2 in range(4):
            tests.append(
                TestVector(
                    f"TC9.{index}",
                    f"DOT_PROD source pair ({matrix_1},{matrix_2}) to [0,0]",
                    dot_packet(matrix_1, matrix_2, 0, 0),
                )
            )
            index += 1

    tests.append(
        TestVector(
            "TC9.17",
            "DOT_PROD maximum destination row/column",
            dot_packet(3, 0, 3, 3),
        )
    )

    # TC10: CLEAR_MATRIX all matrices and signed modes.
    index = 1
    for matrix in range(4):
        for signed_mode in range(2):
            tests.append(
                TestVector(
                    f"TC10.{index}",
                    f"CLEAR matrix {matrix}, signed_mode={signed_mode}",
                    clear_packet(matrix, signed_mode),
                )
            )
            index += 1

    # TC11: RELU.
    for matrix in range(4):
        tests.append(
            TestVector(
                f"TC11.{matrix + 1}",
                f"RELU matrix {matrix}",
                relu_packet(matrix),
            )
        )
    tests.append(
        TestVector(
            "TC11.5",
            "RELU reserved bits set",
            relu_packet(2, reserved=0b11),
        )
    )

    # TC12: CLAMP.
    index = 1
    for matrix in range(4):
        for clamp_max in (0x00, 0xFF):
            tests.append(
                TestVector(
                    f"TC12.{index}",
                    f"CLAMP matrix {matrix} to 0x{clamp_max:02X}",
                    clamp_packet(matrix, clamp_max),
                )
            )
            index += 1

    tests.append(
        TestVector(
            "TC12.9",
            "CLAMP reserved bits set",
            clamp_packet(1, 0x7F, reserved=0b11),
        )
    )

    # TC13: SHIFT_ROW_COL.
    index = 1
    for matrix in range(4):
        shift_cases = (
            (0, 0, "column shift by 0"),
            (3, 0, "column shift by 3"),
            (0, 1, "row shift by 0"),
            (3, 1, "row shift by 3"),
        )
        for shift_amount, row_direction, description in shift_cases:
            tests.append(
                TestVector(
                    f"TC13.{index}",
                    f"Matrix {matrix}, {description}",
                    shift_packet(matrix, shift_amount, row_direction),
                )
            )
            index += 1

    tests.append(
        TestVector(
            "TC13.17",
            "SHIFT reserved bits set",
            shift_packet(
                2,
                2,
                1,
                header_reserved=0b11,
                detail_reserved=0b111,
            ),
        )
    )

    # TC14: Invalid opcodes.
    for index, byte in enumerate((0x00, 0xC0, 0xD5, 0xEA, 0xFF), start=1):
        tests.append(
            TestVector(
                f"TC14.{index}",
                f"Unsupported command byte 0x{byte:02X}",
                (byte,),
            )
        )

    if len(tests) != 141:
        raise RuntimeError(f"Expected 141 ordinary packet tests, built {len(tests)}")

    return tests


async def sample_rising_edge(dut) -> None:
    await RisingEdge(dut.i_clk)
    await ReadOnly()


async def check_idle_edge(
    dut,
    scoreboard: Scoreboard,
    expected_uart_tx_new: int,
    expected_uart_data: Optional[int],
    context: str,
) -> None:
    scoreboard.check_triggers(dut, None, context)
    scoreboard.check_equal(dut, "o_uart_tx_new", expected_uart_tx_new, context)

    if expected_uart_data is not None and expected_uart_tx_new:
        scoreboard.check_equal(dut, "o_uart_tx_data", expected_uart_data, context)


async def exercise_packet(
    dut,
    model: CommandParserGoldenModel,
    scoreboard: Scoreboard,
    packet: Tuple[int, ...],
    read_data: Optional[int],
    context_prefix: str = "",
) -> None:
    """Drive one packet and score its fields, trigger, and idle timing."""
    model.reset()
    final_event: Optional[DecodedCommand] = None

    for byte_index, byte in enumerate(packet):
        # All writes occur after a falling edge, so cocotb is never asked to drive a value during the ReadOnly phase.
        await FallingEdge(dut.i_clk)

        if byte_index == 0 and read_data is not None:
            # Match the original TB: begin with a known old value, then update i_data_rd two idle edges after the final READ byte.
            dut.i_data_rd.value = 0

        dut.i_uart_rx_data.value = byte
        dut.i_uart_rx_new.value = 1

        expected_event = model.accept_byte(byte, valid=True)
        await sample_rising_edge(dut)

        byte_context = f"{context_prefix}byte {byte_index + 1}: "

        if expected_event is None:
            scoreboard.check_triggers(dut, None, byte_context)
        elif not expected_event.valid:
            scoreboard.check_triggers(dut, None, byte_context)
            final_event = expected_event
        else:
            scoreboard.check_triggers(dut, expected_event.trigger, byte_context)
            for signal_name, expected_value in expected_event.fields.items():
                scoreboard.check_equal(
                    dut,
                    signal_name,
                    expected_value,
                    byte_context,
                )
            final_event = expected_event

        # A previous READ response cannot overlap because every byte is followed by ten idle cycles.
        scoreboard.check_equal(dut, "o_uart_tx_new", 0, byte_context)

        await FallingEdge(dut.i_clk)
        dut.i_uart_rx_new.value = 0

        for idle_edge in range(1, INTER_BYTE_IDLE_CYCLES + 1):
            await sample_rising_edge(dut)

            expected_tx_new = 0
            expected_tx_data: Optional[int] = None

            if (
                expected_event is not None
                and expected_event.valid
                and expected_event.read_response_delay is not None
                and idle_edge == expected_event.read_response_delay
            ):
                expected_tx_new = 1
                expected_tx_data = read_data

            idle_context = (
                f"{context_prefix}after byte {byte_index + 1}, "
                f"idle edge {idle_edge}: "
            )
            await check_idle_edge(
                dut,
                scoreboard,
                expected_tx_new,
                expected_tx_data,
                idle_context,
            )

            if idle_edge < INTER_BYTE_IDLE_CYCLES:
                await FallingEdge(dut.i_clk)

                # The original SystemVerilog READ tests update data_in after two rising edges following the final address byte.
                if (
                    read_data is not None
                    and expected_event is not None
                    and expected_event.valid
                    and expected_event.read_response_delay is not None
                    and idle_edge == 2
                ):
                    dut.i_data_rd.value = read_data

    if final_event is None:
        scoreboard.error("Golden model did not complete the packet")


async def run_packet_case(
    dut,
    model: CommandParserGoldenModel,
    scoreboard: Scoreboard,
    vector: TestVector,
) -> None:
    scoreboard.begin(vector.test_id, vector.description)

    try:
        await exercise_packet(
            dut,
            model,
            scoreboard,
            vector.packet,
            vector.read_data,
        )
    except Exception as exc:  # Keep running so the final summary is complete.
        scoreboard.error(f"Unexpected testbench exception: {type(exc).__name__}: {exc}")

    scoreboard.end()


async def run_reset_case(dut, scoreboard: Scoreboard) -> None:
    scoreboard.begin("TC1.1", "Asynchronous reset initializes all outputs")

    dut.i_rst_n.value = 0
    dut.i_uart_rx_data.value = 0
    dut.i_uart_rx_new.value = 0
    dut.i_data_rd.value = 0
    dut.i_idle.value = 0

    for _ in range(5):
        await sample_rising_edge(dut)

    for signal_name, expected in RESET_EXPECTATIONS.items():
        scoreboard.check_equal(dut, signal_name, expected, "reset: ")

    scoreboard.end()

    await FallingEdge(dut.i_clk)
    dut.i_rst_n.value = 1

    for _ in range(5):
        await sample_rising_edge(dut)


async def run_reset_recovery_case(
    dut,
    model: CommandParserGoldenModel,
    scoreboard: Scoreboard,
) -> None:
    scoreboard.begin(
        "TC15.1",
        "Reset discards a partial QUANTIZE packet and parser accepts ADD",
    )

    try:
        model.reset()
        partial_packet = (0x14, 0x40, 0x20)

        for byte_index, byte in enumerate(partial_packet):
            await FallingEdge(dut.i_clk)
            dut.i_uart_rx_data.value = byte
            dut.i_uart_rx_new.value = 1

            event = model.accept_byte(byte, valid=True)
            await sample_rising_edge(dut)

            context = f"partial QUANTIZE byte {byte_index + 1}: "
            if event is not None:
                scoreboard.error(
                    f"{context}golden model completed before seven bytes"
                )
            scoreboard.check_triggers(dut, None, context)

            await FallingEdge(dut.i_clk)
            dut.i_uart_rx_new.value = 0

            for idle_edge in range(1, INTER_BYTE_IDLE_CYCLES + 1):
                await sample_rising_edge(dut)
                scoreboard.check_triggers(
                    dut,
                    None,
                    f"{context}idle edge {idle_edge}: ",
                )
                scoreboard.check_equal(
                    dut,
                    "o_uart_tx_new",
                    0,
                    f"{context}idle edge {idle_edge}: ",
                )
                if idle_edge < INTER_BYTE_IDLE_CYCLES:
                    await FallingEdge(dut.i_clk)

        # Assert active-low reset for three rising edges.
        await FallingEdge(dut.i_clk)
        dut.i_rst_n.value = 0
        model.reset()

        for reset_edge in range(1, 4):
            await sample_rising_edge(dut)
            for signal_name, expected in RESET_EXPECTATIONS.items():
                scoreboard.check_equal(
                    dut,
                    signal_name,
                    expected,
                    f"recovery reset edge {reset_edge}: ",
                )

        # Release reset and allow three clocks before the recovery command.
        await FallingEdge(dut.i_clk)
        dut.i_rst_n.value = 1

        for release_edge in range(1, 4):
            await sample_rising_edge(dut)
            scoreboard.check_triggers(
                dut,
                None,
                f"after reset release edge {release_edge}: ",
            )
            if release_edge < 3:
                await FallingEdge(dut.i_clk)

        # The parser must treat 0x43 as a fresh ADD command.
        await exercise_packet(
            dut,
            model,
            scoreboard,
            (0x43,),
            read_data=None,
            context_prefix="post-reset ADD: ",
        )

    except Exception as exc:
        scoreboard.error(f"Unexpected testbench exception: {type(exc).__name__}: {exc}")

    scoreboard.end()


async def run_valid_negative_case(
    dut,
    model: CommandParserGoldenModel,
    scoreboard: Scoreboard,
) -> None:
    scoreboard.begin(
        "TC16.1",
        "UART data changes are ignored when i_uart_rx_new is low",
    )

    try:
        model.reset()

        await FallingEdge(dut.i_clk)
        dut.i_uart_rx_new.value = 0
        dut.i_uart_rx_data.value = 0xFF
        if model.accept_byte(0xFF, valid=False) is not None:
            scoreboard.error("Golden model accepted 0xFF while valid was low")

        for edge in range(1, 4):
            await sample_rising_edge(dut)
            scoreboard.check_triggers(
                dut,
                None,
                f"0xFF with valid low, edge {edge}: ",
            )
            scoreboard.check_equal(
                dut,
                "o_uart_tx_new",
                0,
                f"0xFF with valid low, edge {edge}: ",
            )
            if edge < 3:
                await FallingEdge(dut.i_clk)

        await FallingEdge(dut.i_clk)
        dut.i_uart_rx_data.value = 0x00
        if model.accept_byte(0x00, valid=False) is not None:
            scoreboard.error("Golden model accepted 0x00 while valid was low")

        for edge in range(1, 4):
            await sample_rising_edge(dut)
            scoreboard.check_triggers(
                dut,
                None,
                f"0x00 with valid low, edge {edge}: ",
            )
            scoreboard.check_equal(
                dut,
                "o_uart_tx_new",
                0,
                f"0x00 with valid low, edge {edge}: ",
            )
            if edge < 3:
                await FallingEdge(dut.i_clk)

    except Exception as exc:
        scoreboard.error(f"Unexpected testbench exception: {type(exc).__name__}: {exc}")

    scoreboard.end()


@cocotb.test()
async def command_parser_complete_python_scoreboard(dut) -> None:
    """Execute and score all 144 command-parser test-plan cases."""
    cocotb.start_soon(
        Clock(dut.i_clk, CLOCK_PERIOD_NS, unit="ns").start()
    )

    scoreboard = Scoreboard()
    model = CommandParserGoldenModel(grid_size=4)

    await run_reset_case(dut, scoreboard)

    for vector in build_test_vectors():
        await run_packet_case(dut, model, scoreboard, vector)

    await run_reset_recovery_case(dut, model, scoreboard)
    await run_valid_negative_case(dut, model, scoreboard)

    scoreboard.print_summary()

    if scoreboard.total != TOTAL_EXPECTED_TESTS:
        raise AssertionError(
            f"Scoreboard ran {scoreboard.total} tests; "
            f"expected {TOTAL_EXPECTED_TESTS}"
        )

    if scoreboard.failed:
        raise AssertionError(
            f"{scoreboard.failed} of {scoreboard.total} command-parser tests failed. See the scoreboard summary above."
        )

    cocotb.log.info(
        "ALL %d COMMAND PARSER TESTS PASSED",
        scoreboard.total,
    )
