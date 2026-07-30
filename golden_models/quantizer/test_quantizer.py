from collections import Counter, deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

import cocotb
from cocotb.triggers import ReadWrite, RisingEdge, Timer

from quantizer_golden_model import QuantizerGoldenModel, QuantizerResult


CLOCK_PERIOD_NS = 10
SV_ASSIGNMENT_TO_OUTPUT_EDGES = 4
TOTAL_VECTOR_TESTS = 301
TOTAL_EXPECTED_TESTS = 302


@dataclass(frozen=True)
class TestVector:
    test_id: str
    description: str
    i_data: int
    i_scale: int
    i_zero_point: int
    i_target_dtype: int


class Scoreboard:

    def __init__(self) -> None:
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.failed_tests: List[Tuple[str, List[str]]] = []

    @staticmethod
    def _read_int(dut, signal_name: str) -> Tuple[Optional[int], Optional[str]]:
        raw_value = getattr(dut, signal_name).value
        try:
            return int(raw_value), None
        except (TypeError, ValueError):
            return None, f"{signal_name} is unresolved: {raw_value}"

    def check_reset(self, dut) -> None:
        errors: List[str] = []

        actual_data, data_error = self._read_int(dut, "o_quantized_data")
        actual_overflow, overflow_error = self._read_int(dut, "o_overflow")

        if data_error:
            errors.append(data_error)
        elif actual_data != 0:
            errors.append(
                f"o_quantized_data: expected 0x00, received 0x{actual_data:02X}"
            )

        if overflow_error:
            errors.append(overflow_error)
        elif actual_overflow != 0:
            errors.append(
                f"o_overflow: expected 0, received {actual_overflow}"
            )

        self._record(
            test_id="TC1.1",
            description="Active-low reset clears the quantizer outputs",
            errors=errors,
        )

    def check_vector(
        self,
        dut,
        vector: TestVector,
        expected: QuantizerResult,
    ) -> None:
        errors: List[str] = []

        actual_data, data_error = self._read_int(dut, "o_quantized_data")
        actual_overflow, overflow_error = self._read_int(dut, "o_overflow")

        if data_error:
            errors.append(data_error)
        elif actual_data != expected.output:
            errors.append(
                "o_quantized_data: "
                f"expected 0x{expected.output:02X}, "
                f"received 0x{actual_data:02X}"
            )

        if overflow_error:
            errors.append(overflow_error)
        elif actual_overflow != int(expected.overflow):
            errors.append(
                "o_overflow: "
                f"expected {int(expected.overflow)}, "
                f"received {actual_overflow}"
            )

        if errors:
            errors.extend(
                [
                    (
                        "inputs: "
                        f"data={vector.i_data}, "
                        f"scale=0x{vector.i_scale:08X}, "
                        f"zero_point=0x{vector.i_zero_point & 0xFF:02X}, "
                        f"dtype={vector.i_target_dtype}"
                    ),
                    (
                        "golden internals: "
                        f"exp={expected.exponent}, "
                        f"scaled={expected.scaled_data}, "
                        f"rounded={expected.rounded_data}, "
                        f"after_zp={expected.after_zero_point}, "
                        f"early_overflow={int(expected.early_overflow)}, "
                        f"guard={expected.guard_bit}, "
                        f"sticky={int(expected.sticky_bit)}, "
                        f"retained_lsb={expected.retained_lsb}, "
                        f"round_up={int(expected.round_up)}"
                    ),
                ]
            )

        self._record(vector.test_id, vector.description, errors)

    def _record(
        self,
        test_id: str,
        description: str,
        errors: List[str],
    ) -> None:
        self.total += 1

        if errors:
            self.failed += 1
            self.failed_tests.append((test_id, errors.copy()))
            cocotb.log.error("[FAIL] %s — %s", test_id, description)
            for message in errors:
                cocotb.log.error("       %s", message)
        else:
            self.passed += 1
            cocotb.log.info("[PASS] %s — %s", test_id, description)

    def print_summary(self) -> None:
        line = "=" * 76
        cocotb.log.info(line)
        cocotb.log.info("QUANTIZER SCOREBOARD SUMMARY")
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


def _add_group(
    tests: List[TestVector],
    prefix: str,
    dtype: int,
    cases: Tuple[Tuple[str, int, int, int], ...],
) -> None:
    for index, (description, data, scale, zero_point) in enumerate(cases, 1):
        tests.append(
            TestVector(
                test_id=f"{prefix}.{index}",
                description=description,
                i_data=data,
                i_scale=scale,
                i_zero_point=zero_point,
                i_target_dtype=dtype,
            )
        )


def build_test_vectors() -> List[TestVector]:

    tests: List[TestVector] = []


    # TC2: int8 specific cases (original cases 1--15)
    _add_group(
        tests,
        "TC2",
        0,
        (
            ("Normal positive result", 162574, 0x391C68A3, 41),
            ("Negative signed zero point", 147, 0x3E7182C0, -12),
            ("Negative input data", -9, 0x415AAAAB, 108),
            ("Zero data returns zero point", 0, 0x45841234, 124),
            ("Large positive early overflow", 1, 0x45841234, 124),
            ("Positive exponent-135 overflow", 1, 0x43800000, 124),
            ("Negative exponent-135 overflow", -1, 0x43800000, 124),
            ("Exact int8 positive limit", 127, 0x3F800000, 0),
            ("One above int8 positive limit", 128, 0x3F800000, 0),
            ("Exact int8 negative limit", -128, 0x3F800000, 0),
            ("One below int8 negative limit", -129, 0x3F800000, 0),
            ("Positive 0.5 tie", 8, 0x3D800000, 0),
            ("Positive 1.5 tie", 4, 0x3EC00000, 0),
            ("Negative 0.5 tie", -8, 0x3D800000, 0),
            ("Negative 1.5 tie", -4, 0x3EC00000, 0),
        ),
    )

    # TC3: uint8 specific cases (original cases 16--27)
    _add_group(
        tests,
        "TC3",
        1,
        (
            ("Exact uint8 lower limit", 0, 0x3F800000, 0),
            ("Exact uint8 upper limit", 255, 0x3F800000, 0),
            ("One above uint8 upper limit", 256, 0x3F800000, 0),
            ("One below uint8 lower limit", -1, 0x3F800000, 0),
            ("Zero point reaches uint8 maximum", 250, 0x3F800000, 5),
            ("Zero point causes uint8 overflow", 251, 0x3F800000, 5),
            ("Unsigned zero-point cancellation", -5, 0x3F800000, 5),
            ("Unsigned zero-point lower overflow", -6, 0x3F800000, 5),
            ("Positive 0.5 tie", 1, 0x3F000000, 0),
            ("Positive 1.5 tie", 3, 0x3F000000, 0),
            ("Negative 0.5 tie", -1, 0x3F000000, 0),
            ("Negative 1.5 tie clips to zero", -3, 0x3F000000, 0),
        ),
    )

    # TC4: int4 specific cases (original cases 28--39)
    _add_group(
        tests,
        "TC4",
        2,
        (
            ("Exact int4 negative limit", -8, 0x3F800000, 0),
            ("One below int4 negative limit", -9, 0x3F800000, 0),
            ("Exact int4 positive limit", 7, 0x3F800000, 0),
            ("One above int4 positive limit", 8, 0x3F800000, 0),
            ("Zero point reaches int4 maximum", 3, 0x3F800000, 4),
            ("Zero point causes int4 positive overflow", 4, 0x3F800000, 4),
            ("Signed zero point reaches int4 minimum", -3, 0x3F800000, -5),
            ("Signed zero point causes int4 negative overflow", -4, 0x3F800000, -5),
            ("Positive 0.5 tie", 1, 0x3F000000, 0),
            ("Positive 1.5 tie", 3, 0x3F000000, 0),
            ("Negative 0.5 tie", -1, 0x3F000000, 0),
            ("Negative 1.5 tie", -3, 0x3F000000, 0),
        ),
    )

    # TC5: uint4 specific cases (original cases 40--52)
    _add_group(
        tests,
        "TC5",
        3,
        (
            ("Exact uint4 lower limit", 0, 0x3F800000, 0),
            ("Exact uint4 upper limit", 15, 0x3F800000, 0),
            ("One above uint4 upper limit", 16, 0x3F800000, 0),
            ("One below uint4 lower limit", -1, 0x3F800000, 0),
            ("Zero point reaches uint4 maximum", 10, 0x3F800000, 5),
            ("Zero point causes uint4 overflow", 11, 0x3F800000, 5),
            ("Unsigned zero-point cancellation", -5, 0x3F800000, 5),
            ("Unsigned zero-point lower overflow", -6, 0x3F800000, 5),
            ("Positive 0.5 tie", 1, 0x3F000000, 0),
            ("Positive 1.5 tie", 3, 0x3F000000, 0),
            ("15.5 tie saturates to uint4 maximum", 31, 0x3F000000, 0),
            ("Negative 0.5 tie", -1, 0x3F000000, 0),
            ("Negative 1.5 tie clips to zero", -3, 0x3F000000, 0),
        ),
    )

    # TC6: int2 specific cases (original cases 53--65)
    _add_group(
        tests,
        "TC6",
        4,
        (
            ("Exact int2 negative limit", -2, 0x3F800000, 0),
            ("One below int2 negative limit", -3, 0x3F800000, 0),
            ("Exact int2 positive limit", 1, 0x3F800000, 0),
            ("One above int2 positive limit", 2, 0x3F800000, 0),
            ("Signed zero point reaches int2 maximum", 2, 0x3F800000, -1),
            ("Signed zero point causes int2 positive overflow", 3, 0x3F800000, -1),
            ("Signed zero point reaches int2 minimum", -1, 0x3F800000, -1),
            ("Signed zero point causes int2 negative overflow", -2, 0x3F800000, -1),
            ("Positive 0.5 tie", 1, 0x3F000000, 0),
            ("Positive 1.5 tie saturates", 3, 0x3F000000, 0),
            ("Negative 0.5 tie", -1, 0x3F000000, 0),
            ("Negative 1.5 tie", -3, 0x3F000000, 0),
            ("Negative 3.5 tie saturates", -7, 0x3F000000, 0),
        ),
    )

    # TC7: uint2 specific cases (original cases 66--78)
    _add_group(
        tests,
        "TC7",
        5,
        (
            ("Exact uint2 lower limit", 0, 0x3F800000, 0),
            ("Exact uint2 upper limit", 3, 0x3F800000, 0),
            ("One above uint2 upper limit", 4, 0x3F800000, 0),
            ("One below uint2 lower limit", -1, 0x3F800000, 0),
            ("Zero point reaches uint2 maximum", 2, 0x3F800000, 1),
            ("Zero point causes uint2 overflow", 3, 0x3F800000, 1),
            ("Unsigned zero-point cancellation", -1, 0x3F800000, 1),
            ("Unsigned zero-point lower overflow", -2, 0x3F800000, 1),
            ("Positive 0.5 tie", 1, 0x3F000000, 0),
            ("Positive 1.5 tie", 3, 0x3F000000, 0),
            ("Positive 3.5 tie saturates", 7, 0x3F000000, 0),
            ("Negative 0.5 tie", -1, 0x3F000000, 0),
            ("Negative 1.5 tie clips to zero", -3, 0x3F000000, 0),
        ),
    )


    # TC8: complete below/tie/above RNE boundaries for dtypes 0--5
    rounding_cases: Tuple[Tuple[str, int, int], ...] = (
        ("P0a below +0.5", 8, 0x3D7FFFFF),
        ("P0b exact +0.5 tie", 8, 0x3D800000),
        ("P0c above +0.5", 8, 0x3D800001),
        ("P1a below +1.5", 4, 0x3EBFFFFF),
        ("P1b exact +1.5 tie", 4, 0x3EC00000),
        ("P1c above +1.5", 4, 0x3EC00001),
        ("N0a inside -0.5", -8, 0x3D7FFFFF),
        ("N0b exact -0.5 tie", -8, 0x3D800000),
        ("N0c outside -0.5", -8, 0x3D800001),
        ("N1a inside -1.5", -4, 0x3EBFFFFF),
        ("N1b exact -1.5 tie", -4, 0x3EC00000),
        ("N1c outside -1.5", -4, 0x3EC00001),
    )

    tc8_index = 1
    dtype_names = ("int8", "uint8", "int4", "uint4", "int2", "uint2")
    for dtype, dtype_name in enumerate(dtype_names):
        for label, data, scale in rounding_cases:
            tests.append(
                TestVector(
                    test_id=f"TC8.{tc8_index}",
                    description=f"{dtype_name} RNE {label}",
                    i_data=data,
                    i_scale=scale,
                    i_zero_point=0,
                    i_target_dtype=dtype,
                )
            )
            tc8_index += 1


    # TC9: shift and exponent cases (original cases 79--90)
    shift_cases = (
        (1, "Exponent 101 below supported range", 4194303, 0x32FFFFFF, 44),
        (1, "Exponent 102 lower supported boundary", 4194303, 0x337FFFFF, 44),
        (1, "Exponent 104 with maximum mantissa", 4194303, 0x347FFFFF, 44),
        (1, "Exponent 105 scale 2^-22", 4194303, 0x34800000, 44),
        (1, "Exponent 126 exact 0.5 tie", 1, 0x3F000000, 44),
        (1, "Exponent 127 scale 1.0", 1, 0x3F800000, 44),
        (1, "Exponent 128 scale 2.0", 64, 0x40000000, 44),
        (1, "Exponent 134 upper normal boundary", 1, 0x43000000, 0),
        (1, "Exponent 135 positive uint8 early overflow", 1, 0x43800000, 44),
        (1, "Exponent 135 negative uint8 early overflow", -1, 0x43800000, 44),
        (0, "Exponent 135 positive int8 early overflow", 1, 0x43800000, 44),
        (0, "Exponent 135 negative int8 early overflow", -1, 0x43800000, 44),
    )
    for index, (dtype, description, data, scale, zero_point) in enumerate(
        shift_cases, 1
    ):
        tests.append(
            TestVector(
                test_id=f"TC9.{index}",
                description=description,
                i_data=data,
                i_scale=scale,
                i_zero_point=zero_point,
                i_target_dtype=dtype,
            )
        )


    # TC10--TC15: small-scale sweeps
    scale_sweep_16 = (
        0x37FFFFFF,
        0x377FFFFF,
        0x36FFFFFF,
        0x367FFFFF,
        0x35FFFFFF,
        0x357FFFFF,
        0x34FFFFFF,
        0x347FFFFF,
        0x33FFFFFF,
        0x337FFFFF,
        0x32FFFFFF,
        0x327FFFFF,
        0x31FFFFFF,
        0x317FFFFF,
        0x30FFFFFF,
        0x307FFFFF,
    )
    scale_sweep_10 = scale_sweep_16[:10]

    sweep_specs = (
        ("TC10", "int8", 0, 44, scale_sweep_16),
        ("TC11", "uint8", 1, 44, scale_sweep_10),
        ("TC12", "int4", 2, 4, scale_sweep_10),
        ("TC13", "uint4", 3, 4, scale_sweep_10),
        ("TC14", "int2", 4, 0, scale_sweep_10),
        ("TC15", "uint2", 5, 1, scale_sweep_10),
    )

    for prefix, dtype_name, dtype, zero_point, scales in sweep_specs:
        index = 1
        for sign_name, data in (
            ("positive", 4194303),
            ("negative", -4194303),
        ):
            for sweep_index, scale in enumerate(scales, 1):
                tests.append(
                    TestVector(
                        test_id=f"{prefix}.{index}",
                        description=(
                            f"{dtype_name} {sign_name} scale sweep "
                            f"{sign_name[0].upper()}{sweep_index}"
                        ),
                        i_data=data,
                        i_scale=scale,
                        i_zero_point=zero_point,
                        i_target_dtype=dtype,
                    )
                )
                index += 1


    # TC16: codes 6 and 7 equivalent to int8 and uint8
    equivalent_cases = (
        (6, "Dtype 6 exact int8 positive limit", 127, 0x3F800000, 0),
        (6, "Dtype 6 int8 positive saturation", 128, 0x3F800000, 0),
        (6, "Dtype 6 exact int8 negative limit", -128, 0x3F800000, 0),
        (6, "Dtype 6 int8 negative saturation", -129, 0x3F800000, 0),
        (7, "Dtype 7 exact uint8 upper limit", 255, 0x3F800000, 0),
        (7, "Dtype 7 uint8 positive saturation", 256, 0x3F800000, 0),
        (7, "Dtype 7 uint8 negative saturation", -1, 0x3F800000, 0),
    )
    for index, (dtype, description, data, scale, zero_point) in enumerate(
        equivalent_cases, 1
    ):
        tests.append(
            TestVector(
                test_id=f"TC16.{index}",
                description=description,
                i_data=data,
                i_scale=scale,
                i_zero_point=zero_point,
                i_target_dtype=dtype,
            )
        )

    if len(tests) != TOTAL_VECTOR_TESTS:
        raise RuntimeError(
            f"Expected {TOTAL_VECTOR_TESTS} vectors, built {len(tests)}"
        )

    expected_counts = {
        "TC2": 15,
        "TC3": 12,
        "TC4": 12,
        "TC5": 13,
        "TC6": 13,
        "TC7": 13,
        "TC8": 72,
        "TC9": 12,
        "TC10": 32,
        "TC11": 20,
        "TC12": 20,
        "TC13": 20,
        "TC14": 20,
        "TC15": 20,
        "TC16": 7,
    }
    actual_counts = Counter(vector.test_id.split(".")[0] for vector in tests)
    if dict(actual_counts) != expected_counts:
        raise RuntimeError(
            f"Unexpected test-group counts: {dict(actual_counts)}"
        )

    return tests


def drive_vector(dut, vector: TestVector) -> None:
    """Drive raw port bits for one vector."""
    dut.i_data.value = vector.i_data & ((1 << 23) - 1)
    dut.i_scale.value = vector.i_scale & 0xFFFFFFFF
    dut.i_zero_point.value = vector.i_zero_point & 0xFF
    dut.i_target_dtype.value = vector.i_target_dtype & 0x7


def drive_neutral_vector(dut) -> None:
    dut.i_data.value = 0
    dut.i_scale.value = 0
    dut.i_zero_point.value = 0
    dut.i_target_dtype.value = 0


async def generate_clock(dut) -> None:

    dut.i_clk.value = 0

    while True:
        await Timer(CLOCK_PERIOD_NS // 2, unit="ns")
        dut.i_clk.value = 0 if int(dut.i_clk.value) else 1


async def wait_for_rising_write_phase(dut) -> None:

    await RisingEdge(dut.i_clk)
    await ReadWrite()


async def run_reset_case(dut, scoreboard: Scoreboard) -> int:
    
    dut.i_rst_n.value = 0
    drive_neutral_vector(dut)

    # Confirm the asynchronous reset response before the first clock edge.
    await Timer(1, unit="ns")
    scoreboard.check_reset(dut)

    edge_number = 0
    for _ in range(2):
        await wait_for_rising_write_phase(dut)
        edge_number += 1


    dut.i_rst_n.value = 1
    return edge_number


@cocotb.test()
async def quantizer_scoreboard(dut) -> None:
    """Execute and score all 302 quantizer test-plan cases."""
    cocotb.start_soon(generate_clock(dut))

    scoreboard = Scoreboard()
    model = QuantizerGoldenModel()
    vectors = build_test_vectors()

    current_edge = await run_reset_case(dut, scoreboard)

    pending: Deque[Tuple[int, TestVector, QuantizerResult]] = deque()

   
    first_vector = vectors[0]
    drive_vector(dut, first_vector)
    first_expected = model.quantize(
        i_data=first_vector.i_data,
        i_scale=first_vector.i_scale,
        i_zero_point=first_vector.i_zero_point,
        i_target_dtype=first_vector.i_target_dtype,
    )
    pending.append(
        (
            current_edge + SV_ASSIGNMENT_TO_OUTPUT_EDGES,
            first_vector,
            first_expected,
        )
    )

    next_vector_index = 1
    neutral_driven = False

    while pending:
        await wait_for_rising_write_phase(dut)
        current_edge += 1

        if pending and pending[0][0] == current_edge:
            _, due_vector, due_expected = pending.popleft()
            scoreboard.check_vector(dut, due_vector, due_expected)

        if next_vector_index < len(vectors):
           
            vector = vectors[next_vector_index]
            drive_vector(dut, vector)

            expected = model.quantize(
                i_data=vector.i_data,
                i_scale=vector.i_scale,
                i_zero_point=vector.i_zero_point,
                i_target_dtype=vector.i_target_dtype,
            )
            pending.append(
                (
                    current_edge + SV_ASSIGNMENT_TO_OUTPUT_EDGES,
                    vector,
                    expected,
                )
            )
            next_vector_index += 1

        elif not neutral_driven:
            
            drive_neutral_vector(dut)
            neutral_driven = True

    await Timer(1, unit="ns")

    scoreboard.print_summary()

    if scoreboard.total != TOTAL_EXPECTED_TESTS:
        raise AssertionError(
            f"Scoreboard ran {scoreboard.total} tests; "
            f"expected {TOTAL_EXPECTED_TESTS}"
        )

    if scoreboard.failed:
        raise AssertionError(
            f"{scoreboard.failed} of {scoreboard.total} quantizer tests "
            "failed. See the scoreboard summary above."
        )

    cocotb.log.info(
        "ALL %d QUANTIZER TESTS PASSED",
        scoreboard.total,
    )

