import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from golden_model import IntMacGolden


async def reset_dut(dut):
    dut.i_rst_n.value = 0
    dut.i_valid.value = 0
    dut.i_a.value = 0
    dut.i_b.value = 0
    await RisingEdge(dut.i_clk)
    await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    await RisingEdge(dut.i_clk)


def to_signed9(v: int) -> int:
    """Wrap a python int into 9-bit two's complement range for driving the DUT."""
    return v & 0x1FF


async def drive_and_check(dut, golden, stimulus):
    """
    stimulus: list of (valid, a, b) tuples, one entry per clock cycle.
    Drives DUT + golden in lockstep, comparing DUT outputs (which reflect
    the *previous* edge's updates) against golden outputs after each edge.
    """
    for (valid, a, b) in stimulus:
        # Drive inputs before the edge
        dut.i_valid.value = valid
        dut.i_a.value = to_signed9(a)
        dut.i_b.value = to_signed9(b)

        await RisingEdge(dut.i_clk)
        # Let DUT outputs settle (they're registered, but give delta-cycle margin)
        await Timer(1, unit="ns")

        # Advance golden model with the same inputs applied on this edge
        golden.step(valid, a, b)

        # Compare
        dut_result = dut.o_result.value.to_signed()
        dut_valid = int(dut.o_valid.value)
        dut_overflow = int(dut.o_overflow.value)

        gold_result = sign_extend_check(golden.o_result, 23)
        gold_valid = golden.o_valid
        gold_overflow = golden.o_overflow

        assert dut_valid == gold_valid, (
            f"o_valid mismatch: dut={dut_valid} golden={gold_valid} "
            f"(inputs valid={valid},a={a},b={b})"
        )
        assert dut_overflow == gold_overflow, (
            f"o_overflow mismatch: dut={dut_overflow} golden={gold_overflow} "
            f"(inputs valid={valid},a={a},b={b})"
        )
        assert dut_result == gold_result, (
            f"o_result mismatch: dut={dut_result} golden={gold_result} "
            f"(inputs valid={valid},a={a},b={b})"
        )


def sign_extend_check(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


@cocotb.test()
async def test_directed(dut):
    """Directed test cases matching the original testbench's directed vectors."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    stimulus = [
        (1, 100, 50),
        (1, -100, 50),
        (1, 100, -100),
        (1, -100, -50),
        (1, 50, 50),
        (1, 50, 25),
        (1, -50, -25),
        (0, 20, 30),
        (0, 10, 10),
        (0, 5, 15),
        (0, 0, 0),
        (0, 0, 0),  # a couple extra idle cycles to flush pipeline / check o_valid drop
        (0, 0, 0),
    ]
    await drive_and_check(dut, golden, stimulus)


@cocotb.test()
async def test_overflow_freeze(dut):
    """Drive repeated large products to force overflow, then confirm freeze behavior."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    # 255 as raw 9-bit pattern is out of signed range for a direct python int,
    # but to_signed9 wraps it: 255 in 9 bits = positive 255 (fits, 9-bit signed
    # range is -256..255), matching original TB's use of 9'sd255.
    stimulus = [(1, 255, 255) for _ in range(66)]
    stimulus.append((0, 0, 0))
    await drive_and_check(dut, golden, stimulus)

    # After forcing overflow, confirm several more idle/valid cycles stay frozen
    stimulus2 = [(1, 1, 1) for _ in range(5)]
    await drive_and_check(dut, golden, stimulus2)


@cocotb.test()
async def test_reset_midstream(dut):
    """Reset in the middle of accumulation, confirm both DUT and golden clear."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    stimulus = [(1, 10, 10), (1, 20, 20), (1, 30, 30)]
    await drive_and_check(dut, golden, stimulus)

    # Mid-stream async reset
    await reset_dut(dut)
    golden.reset()

    stimulus2 = [(1, 5, 5), (1, 5, 5), (0, 0, 0)]
    await drive_and_check(dut, golden, stimulus2)


@cocotb.test()
async def test_overflow_exact_boundary(dut):
    """
    Push the accumulator to exactly MAX (4194303), confirm no overflow there,
    then add exactly 1 more to confirm overflow fires on that precise cycle
    (not one cycle early/late).

    23-bit signed range: -4194304 .. 4194303
    Build-up: 1023 cycles of product=4096 (a=64,b=64)  -> 1023*4096 = 4190208
              1 cycle of product=4095   (a=63,b=65)     -> +4095 = 4194303 (== MAX, no overflow)
              1 cycle of product=1      (a=1, b=1)      -> +1    = 4194304 (overflow, exceeds MAX by 1)
    """
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    stimulus = [(1, 64, 64) for _ in range(1023)]  # coarse fill, product = 4096 each
    stimulus.append((1, 63, 65))                    # fine step, product = 4095 -> lands exactly at MAX
    stimulus.append((1, 1, 1))                       # tips over by exactly 1 -> overflow must fire here
    stimulus.append((1, 1, 1))                       # confirm frozen the cycle after
    stimulus.append((0, 0, 0))
    await drive_and_check(dut, golden, stimulus)


@cocotb.test()
async def test_underflow_exact_boundary(dut):
    """
    Same idea as above but for the negative boundary (MIN = -4194304).
    1024 cycles of product = -4096 (a=64, b=-64) lands exactly at MIN
    (1024 * -4096 = -4194304) with no overflow, then one more negative
    product tips it under by exactly 1.
    """
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    stimulus = [(1, 64, -64) for _ in range(1024)]  # -4096 each -> exactly MIN, no overflow
    stimulus.append((1, -1, 1))                      # product = -1 -> tips under by 1, must overflow here
    stimulus.append((1, -1, 1))                       # confirm frozen after
    stimulus.append((0, 0, 0))
    await drive_and_check(dut, golden, stimulus)


@cocotb.test()
async def test_valid_toggling(dut):
    """
    Toggle i_valid every other cycle with distinct operand values each time,
    to stress the case where the pipeline has 'holes' -- product register
    must hold its last-loaded value through idle cycles, and valid_0/o_valid
    must correctly track the sparse i_valid pattern (not treat gaps as
    still-valid).
    """
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    stimulus = []
    for i in range(40):
        if i % 2 == 0:
            stimulus.append((1, (i % 200) - 100, ((i * 3) % 200) - 100))
        else:
            # idle cycle -- garbage-ish operands on the bus, must be ignored since valid=0
            stimulus.append((0, 255, 255))
    await drive_and_check(dut, golden, stimulus)


@cocotb.test()
async def test_overflow_reset_overflow_again(dut):
    """
    Overflow once, reset mid-freeze, confirm clean state, then drive it into
    overflow a second time -- checks that reset fully clears the 'sticky'
    overflow latch rather than it somehow surviving reset.
    """
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    # First overflow
    stimulus = [(1, 255, 255) for _ in range(66)]
    await drive_and_check(dut, golden, stimulus)
    assert int(dut.o_overflow.value) == 1, "expected DUT to be in overflow before reset"

    # Reset mid-freeze
    await reset_dut(dut)
    golden.reset()
    assert int(dut.o_overflow.value) == 0, "overflow flag did not clear on reset"

    # Confirm clean accumulation works again post-reset
    stimulus2 = [(1, 10, 10), (1, 10, 10), (0, 0, 0)]
    await drive_and_check(dut, golden, stimulus2)

    # Drive into overflow a second time
    stimulus3 = [(1, 255, 255) for _ in range(66)]
    await drive_and_check(dut, golden, stimulus3)
    assert int(dut.o_overflow.value) == 1, "expected DUT to overflow again after second stress"


@cocotb.test()
async def test_reset_dominates_over_valid(dut):
    """
    Unlike every other test (which forces i_valid=0 whenever i_rst_n=0 via
    reset_dut()), this test drives i_valid=1 with real operand values WHILE
    i_rst_n=0, for several cycles. Confirms the async reset dominates:
    product/valid_0/result_reg/o_overflow/o_valid must all stay at their
    reset values regardless of i_valid, since the reset branch in both
    always_ff blocks has no i_valid gating at all.

    Then deasserts reset (still holding i_valid=1) and confirms normal
    pipelined operation resumes correctly from that point, checked against
    the golden model.
    """
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    # Manually drive reset LOW while i_valid=1 -- do NOT use reset_dut() here,
    # since that helper deliberately forces i_valid=0.
    dut.i_rst_n.value = 0
    dut.i_valid.value = 1
    dut.i_a.value = to_signed9(100)
    dut.i_b.value = to_signed9(50)

    for _ in range(4):
        await RisingEdge(dut.i_clk)
        await Timer(1, unit="ns")
        assert int(dut.o_valid.value) == 0, "o_valid should stay 0 while i_rst_n=0, regardless of i_valid"
        assert dut.o_result.value.to_signed() == 0, "o_result should stay 0 while i_rst_n=0, regardless of i_valid"
        assert int(dut.o_overflow.value) == 0, "o_overflow should stay 0 while i_rst_n=0, regardless of i_valid"

    golden.reset()  # golden model's state after any number of reset cycles is the same: all zero

    # Deassert reset while i_valid is still 1 -- next edge should behave like
    # a completely normal first valid cycle (matches reset_dut()'s own last
    # RisingEdge with i_rst_n=1, i_valid still whatever it was left at).
    dut.i_rst_n.value = 1
    await RisingEdge(dut.i_clk)
    await Timer(1, unit="ns")
    golden.step(1, 100, 50)  # i_valid was already 1 going into this edge

    assert int(dut.o_valid.value) == golden.o_valid
    assert dut.o_result.value.to_signed() == sign_extend_check(golden.o_result, 23)
    assert int(dut.o_overflow.value) == golden.o_overflow

    # Continue with a few more normal cycles through drive_and_check to confirm
    # the pipeline is fully healthy post-reset (not just the single edge above).
    stimulus = [(1, 100, 50), (1, 10, 10), (0, 0, 0)]
    await drive_and_check(dut, golden, stimulus)


@cocotb.test()
async def test_randomized(dut):
    """Randomized stimulus, matching the original TB's random loop (100 cycles)."""
    cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())
    golden = IntMacGolden()

    await reset_dut(dut)
    golden.reset()

    random.seed(42)
    stimulus = []
    for _ in range(150):
        valid = random.choice([0, 1, 1, 1])  # mostly valid, some idle
        a = random.randint(-256, 255)
        b = random.randint(-256, 255)
        stimulus.append((valid, a, b))
    stimulus.extend([(0, 0, 0)] * 4)

    await drive_and_check(dut, golden, stimulus)
