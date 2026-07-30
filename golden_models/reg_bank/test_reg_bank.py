"""
cocotb testbench for reg_bank.sv, cross-checked cycle-by-cycle against
golden_regbank.GoldenRegBank.

Ported from reg_bank_TB_2.sv (test categories 1-16 + random stress).

Per-cycle protocol (matches the golden model's docstring):
    1. drive inputs (DUT + shadow Inputs struct)
    2. await RisingEdge
    3. golden.step(same inputs)          <- model consumes the same edge
    4. await ReadOnly, compare ALL DUT outputs vs golden outputs
    5. await NextTimeStep, loop
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, NextTimeStep

from golden_regbank import GoldenRegBank, Inputs, _to_signed23

GRID  = 3
NCELL = GRID * GRID
NMAT  = 4


# ======================================================================
# Testbench harness
# ======================================================================
class RegBankTB:
    def __init__(self, dut):
        self.dut    = dut
        self.golden = GoldenRegBank(grid_size=GRID)
        self.errors = 0
        self.inp    = Inputs(result=[0] * NCELL)

    # ------------------------------------------------------------------
    def check_eq(self, actual, expected, what=""):
        if actual != expected:
            self.errors += 1
            self.dut._log.error(f"MISMATCH {what}: expected={expected} actual={actual}")

    def finish(self):
        assert self.errors == 0, f"{self.errors} mismatches against golden model"

    # ------------------------------------------------------------------
    # Input driving
    # ------------------------------------------------------------------
    def drive(self, **kwargs):
        """Update shadow Inputs and apply everything to the DUT pins."""
        for k, v in kwargs.items():
            setattr(self.inp, k, v)
        d, i = self.dut, self.inp
        d.i_rst_n.value              = i.rst_n
        d.i_matrix_config.value      = i.matrix_config
        d.i_matrix_signed.value      = i.matrix_signed
        d.i_data_load.value          = i.data_load
        d.i_data_read.value          = i.data_read
        d.i_shift_row.value          = i.shift_row
        d.i_shift_col.value          = i.shift_col
        d.i_arithmetic_op.value      = i.arithmetic_op
        d.i_arithmetic_op_type.value = i.arithmetic_op_type
        d.i_quantization_op.value    = i.quantization_op
        d.i_relu_op.value            = i.relu_op
        d.i_clamp_op.value           = i.clamp_op
        d.i_clamp_max.value          = i.clamp_max & 0xFF
        d.i_matrix_1.value           = i.matrix_1
        d.i_matrix_2.value           = i.matrix_2
        d.i_matrix_rows.value        = i.matrix_rows
        d.i_matrix_cols.value        = i.matrix_cols
        d.i_data.value               = i.data & 0xFF
        d.i_quant_data.value         = i.quant_data & 0xFF
        flat = 0
        for idx, v in enumerate(i.result):
            flat |= (v & 0x7FFFFF) << (23 * idx)
        d.i_result.value = flat

    def clear_inputs(self):
        self.inp = Inputs(rst_n=1, result=[0] * NCELL)
        self.drive()

    # ------------------------------------------------------------------
    # Clocking + checking
    # ------------------------------------------------------------------
    async def tick(self, n=1):
        for _ in range(n):
            await RisingEdge(self.dut.i_clk)
            self.golden.step(self.inp)          # same inputs, same edge
            await ReadOnly()
            if self.inp.rst_n:                  # avoid X-compares in reset
                self._compare()
            await NextTimeStep()

    def _compare(self):
        g, d = self.golden, self.dut
        self.check_eq(int(d.o_idle.value),        g.o_idle,        "o_idle")
        self.check_eq(int(d.o_grid_reset.value),  g.o_grid_reset,  "o_grid_reset")
        self.check_eq(int(d.o_quant_reset.value), g.o_quant_reset, "o_quant_reset")
        self.check_eq(_to_signed23(int(d.o_quant_ip.value)), g.o_quant_ip, "o_quant_ip")
        self.check_eq(int(d.o_data_rd.value),     g.o_data_rd,     "o_data_rd")
        da = int(d.o_data_a.value)
        db = int(d.o_data_b.value)
        dv = int(d.o_data_valid.value)
        for k in range(NCELL):
            self.check_eq((da >> 9 * k) & 0x1FF, g.o_data_a[k],     f"o_data_a[{k}]")
            self.check_eq((db >> 9 * k) & 0x1FF, g.o_data_b[k],     f"o_data_b[{k}]")
            self.check_eq((dv >> k) & 1,         g.o_data_valid[k], f"o_data_valid[{k}]")

    # ------------------------------------------------------------------
    # SV-TB helper task equivalents
    # ------------------------------------------------------------------
    async def reset(self):
        self.drive(rst_n=0)
        await self.tick(3)
        self.drive(rst_n=1)
        await self.tick()

    async def wait_idle(self, timeout=100):
        for _ in range(timeout):
            if self.golden.o_idle:
                break
            await self.tick()
        else:
            raise AssertionError("wait_idle timeout")
        await self.tick()

    async def start_op(self, op_type, m1, m2):
        self.drive(arithmetic_op=1, arithmetic_op_type=op_type,
                   matrix_1=m1, matrix_2=m2)
        await self.tick()
        self.drive(arithmetic_op=0)

    async def write_val(self, m, r, c, val):
        self.drive(data_load=1, matrix_1=m, matrix_rows=r,
                   matrix_cols=c, data=val)
        await self.tick()
        self.drive(data_load=0)

    async def fill_matrix(self, m, val):
        for r in range(GRID):
            for c in range(GRID):
                await self.write_val(m, r, c, val)

    async def read_val(self, m, r, c, expected=None):
        self.drive(data_read=1, matrix_1=m, matrix_rows=r, matrix_cols=c)
        await self.tick()                       # DUT vs golden checked here
        self.drive(data_read=0)
        val = self.golden.o_data_rd
        if expected is not None:
            self.check_eq(val, expected & 0xFF, f"read m{m}[{r}][{c}]")
        return val

    async def check_all_cleared(self):
        self.check_eq(self.golden.o_idle, 1, "idle after reset")
        for r in range(GRID):
            for c in range(GRID):
                self.check_eq(self.golden.accum[r][c], 0, f"accum[{r}][{c}] cleared")
        for m in range(NMAT):
            for r in range(GRID):
                for c in range(GRID):
                    await self.read_val(m, r, c, expected=0)

    def check_accum_uniform(self, expected):
        exp = _to_signed23(expected & 0x7FFFFF)
        for r in range(GRID):
            for c in range(GRID):
                self.check_eq(self.golden.accum[r][c], exp, f"accum[{r}][{c}]")

    def check_valid_uniform(self, expected):
        for k in range(NCELL):
            self.check_eq(self.golden.o_data_valid[k], expected, f"valid[{k}]")

    async def config_matrix(self, m, signed):
        self.drive(matrix_config=1, matrix_1=m, matrix_signed=signed)
        await self.tick()
        self.drive(matrix_config=0)


async def make_tb(dut):
    cocotb.start_soon(Clock(dut.i_clk, 10, units="ns").start())
    tb = RegBankTB(dut)
    tb.clear_inputs()
    await tb.reset()
    return tb


# ======================================================================
# CATEGORY 1: RESET / INITIAL STATE  (cases 1-9)
# ======================================================================
@cocotb.test()
async def test_01_reset(dut):
    tb = await make_tb(dut)

    dut._log.info("Test 1: Reset during IDLE")
    await tb.reset()
    await tb.check_all_cleared()

    for name, op in (("ADD", 0b00), ("EL_MUL", 0b01),
                     ("MAT_MUL", 0b11), ("DOT_PROD", 0b10)):
        dut._log.info(f"Tests 2-5: Reset during {name}")
        await tb.fill_matrix(0, 0xFF)           # give it something to lose
        await tb.start_op(op, 0, 1)
        await tb.tick()
        tb.drive(rst_n=0); await tb.tick()
        tb.drive(rst_n=1); await tb.tick()
        await tb.check_all_cleared()

    dut._log.info("Test 6: Reset during QUANTIZATION")
    tb.drive(quantization_op=1, matrix_1=2, quant_data=0xAA)
    await tb.tick()
    tb.drive(quantization_op=0)
    await tb.tick()
    tb.drive(rst_n=0); await tb.tick()
    tb.drive(rst_n=1, quant_data=0); await tb.tick()

    dut._log.info("Tests 7-9: matrices/accum cleared, o_idle=1")
    await tb.check_all_cleared()
    tb.finish()


# ======================================================================
# CATEGORY 2: MATRIX CONFIGURATION  (cases 10-17)
# ======================================================================
@cocotb.test()
async def test_02_matrix_config(dut):
    tb = await make_tb(dut)

    for m in range(NMAT):                       # cases 10-15
        dut._log.info(f"Tests 10-15: configure matrix {m} signed=0/1")
        await tb.config_matrix(m, 0)
        tb.check_eq(tb.golden.matrix_signed[m], 0, f"signed[{m}]")
        await tb.config_matrix(m, 1)
        tb.check_eq(tb.golden.matrix_signed[m], 1, f"signed[{m}]")

    dut._log.info("Test 16: reconfigure matrix 0 multiple times")
    await tb.config_matrix(0, 0)
    tb.check_eq(tb.golden.matrix_signed[0], 0, "signed[0]")
    await tb.config_matrix(0, 1)
    tb.check_eq(tb.golden.matrix_signed[0], 1, "signed[0]")

    await tb.wait_idle()
    tb.finish()


# ======================================================================
# CATEGORY 3: DATA LOAD / READ  (cases 18-30)
# ======================================================================
@cocotb.test()
async def test_03_data_load_read(dut):
    tb = await make_tb(dut)

    dut._log.info("Test 28: read after reset")
    await tb.read_val(0, 0, 0, expected=0)

    dut._log.info("Tests 18-21: fill 0x00 / 0xFF / 0x80 / 0x7F")
    await tb.fill_matrix(0, 0x00)
    await tb.fill_matrix(1, 0xFF)
    await tb.fill_matrix(2, 0x80)
    await tb.fill_matrix(3, 0x7F)

    dut._log.info("Test 22: checkerboard pattern")
    board = {}
    for r in range(GRID):
        for c in range(GRID):
            v = 0xAA if (r + c) % 2 else 0x55
            board[(0, r, c)] = v
            await tb.write_val(0, r, c, v)

    dut._log.info("Test 23: random pattern")
    for r in range(GRID):
        for c in range(GRID):
            v = random.randrange(256)
            board[(1, r, c)] = v
            await tb.write_val(1, r, c, v)

    dut._log.info("Tests 24-27: boundary coordinates")
    await tb.write_val(2, 0, 0, 0x11)
    await tb.write_val(2, GRID - 1, GRID - 1, 0x22)
    for c in range(GRID):
        await tb.write_val(2, 0, c, 0x33)
    for r in range(GRID):
        await tb.write_val(2, r, GRID - 1, 0x44)

    dut._log.info("Tests 29-30: read back every location of every matrix")
    for m in range(NMAT):
        for r in range(GRID):
            for c in range(GRID):
                exp = board.get((m, r, c), tb.golden.mat_arr[m][r][c])
                await tb.read_val(m, r, c, expected=exp)
    tb.finish()


# ======================================================================
# CATEGORY 4: SIGN EXTENSION  (cases 31-37)
# ======================================================================
@cocotb.test()
async def test_04_sign_extension(dut):
    tb = await make_tb(dut)
    vectors = [  # (value, signed 9-bit expected, unsigned 9-bit expected)
        (0x00, 0x000, 0x000), (0x01, 0x001, 0x001), (0x7F, 0x07F, 0x07F),
        (0x80, 0x180, 0x080), (0x81, 0x181, 0x081), (0xFF, 0x1FF, 0x0FF),
    ]
    await tb.config_matrix(0, 1)                # matrix 0 signed
    await tb.config_matrix(1, 0)                # matrix 1 unsigned

    for val, s_exp, u_exp in vectors:
        dut._log.info(f"Tests 31-37: value {val:#04x} signed vs unsigned")
        await tb.fill_matrix(0, val)
        await tb.fill_matrix(1, val)
        await tb.start_op(0b01, 0, 1)           # EL_MUL exposes both operands
        for k in range(NCELL):
            tb.check_eq(tb.golden.o_data_a[k], s_exp, f"data_a[{k}] of {val:#04x}")
            tb.check_eq(tb.golden.o_data_b[k], u_exp, f"data_b[{k}] of {val:#04x}")
        await tb.wait_idle()
    tb.finish()


# ======================================================================
# CATEGORY 5: ADD OPERATION  (cases 38-46)
# ======================================================================
@cocotb.test()
async def test_05_add(dut):
    tb = await make_tb(dut)

    async def add_case(v0, v1, result):
        await tb.fill_matrix(0, v0)
        await tb.fill_matrix(1, v1)
        tb.drive(result=[result & 0x7FFFFF] * NCELL)
        await tb.start_op(0b00, 0, 1)
        await tb.wait_idle()
        tb.check_accum_uniform(result)

    await tb.config_matrix(0, 0)
    await tb.config_matrix(1, 0)
    dut._log.info("Test 38: 0 + 0")
    await add_case(0x00, 0x00, 0)
    dut._log.info("Test 39: max + max (unsigned)")
    await add_case(0xFF, 0xFF, 510)

    await tb.config_matrix(0, 1)
    await tb.config_matrix(1, 1)
    dut._log.info("Test 40: negative + negative")
    await add_case(0x80, 0x80, -256)
    dut._log.info("Test 41: positive + negative")
    await add_case(0x7F, 0x80, -1)

    dut._log.info("Tests 44-46: ADD operand valid timing (2 cycles then off)")
    await tb.start_op(0b00, 0, 1)               # -> ADD, oper_ctr=0
    tb.check_valid_uniform(1)                   # first operand cycle
    await tb.tick()
    tb.check_valid_uniform(1)                   # second operand cycle
    await tb.tick()
    tb.check_valid_uniform(0)                   # extra cycles ignored
    await tb.wait_idle()
    tb.finish()


# ======================================================================
# CATEGORY 6: ELEMENT MULTIPLY  (cases 47-55)
# ======================================================================
@cocotb.test()
async def test_06_el_mul(dut):
    tb = await make_tb(dut)
    await tb.config_matrix(0, 0)
    await tb.config_matrix(1, 0)

    dut._log.info("Test 47 + 54-55: 0*0, all outputs valid one cycle only")
    await tb.fill_matrix(0, 0x00)
    await tb.fill_matrix(1, 0x00)
    await tb.start_op(0b01, 0, 1)
    tb.check_valid_uniform(1)                   # case 54
    await tb.tick()
    tb.check_valid_uniform(0)                   # case 55
    await tb.wait_idle()

    for name, v0, v1, s0, s1 in (
        ("48: 1*1",           0x01, 0x01, 0, 0),
        ("53: umax*umax",     0xFF, 0xFF, 0, 0),
        ("49: -1*-1",         0xFF, 0xFF, 1, 1),
        ("50: max*max",       0x7F, 0x7F, 1, 1),
        ("51: min*min",       0x80, 0x80, 1, 1),
        ("52: pos*neg",       0x7F, 0x80, 1, 1),
    ):
        dut._log.info(f"Test {name}")
        await tb.config_matrix(0, s0)
        await tb.config_matrix(1, s1)
        await tb.fill_matrix(0, v0)
        await tb.fill_matrix(1, v1)
        await tb.start_op(0b01, 0, 1)
        await tb.wait_idle()
    tb.finish()


# ======================================================================
# CATEGORY 7: MATRIX MULTIPLY  (cases 56-67)
# ======================================================================
@cocotb.test()
async def test_07_mat_mul(dut):
    tb = await make_tb(dut)

    dut._log.info("Tests 59-64: general MatMul (m0=1, m1=2)")
    await tb.fill_matrix(0, 0x01)
    await tb.fill_matrix(1, 0x02)
    tb.drive(result=[6] * NCELL)
    await tb.start_op(0b11, 0, 1)

    dut._log.info("Test 65: all GRID MAC streaming cycles valid")
    for _ in range(GRID):
        tb.check_valid_uniform(1)
        await tb.tick()
    dut._log.info("Test 66: valid deasserted after last MAC cycle")
    tb.check_valid_uniform(0)
    await tb.wait_idle()

    dut._log.info("Test 67: accumulation stored correctly")
    tb.check_accum_uniform(6)
    tb.finish()


# ======================================================================
# CATEGORY 8: DOT PRODUCT  (cases 68-78)
# ======================================================================
@cocotb.test()
async def test_08_dot_prod(dut):
    tb = await make_tb(dut)

    dut._log.info("Tests 68-77: dot product, only MAC[0] valid")
    tb.drive(result=[18] * NCELL, matrix_rows=0, matrix_cols=GRID - 1)
    await tb.start_op(0b10, 0, 1)
    for cyc in range(NCELL):                    # 9 streaming cycles
        tb.check_eq(tb.golden.o_data_valid[0], 1, f"dot valid[0] cyc {cyc}")
        for k in range(1, NCELL):
            tb.check_eq(tb.golden.o_data_valid[k], 0, f"dot valid[{k}] cyc {cyc}")
        await tb.tick()
    await tb.wait_idle()

    dut._log.info("Test 78: result stored at (0, GRID-1)")
    tb.check_eq(tb.golden.accum[0][GRID - 1], 18, "dot accum location")
    tb.finish()


# ======================================================================
# CATEGORY 9: ACCUMULATOR  (cases 79-83)
# ======================================================================
@cocotb.test()
async def test_09_accum(dut):
    tb = await make_tb(dut)
    for name, res in (("79: minimum", 0x400000),      # -4194304
                      ("80: maximum", 0x3FFFFF),
                      ("81: zero",    0),
                      ("82: negative", -12345),
                      ("83: overwrite", 999)):
        dut._log.info(f"Test {name}")
        tb.drive(result=[res & 0x7FFFFF] * NCELL)
        await tb.start_op(0b00, 0, 1)
        await tb.wait_idle()
        tb.check_accum_uniform(res)
    tb.finish()


# ======================================================================
# CATEGORY 10: QUANTIZATION  (cases 84-93)
# ======================================================================
@cocotb.test()
async def test_10_quant(dut):
    tb = await make_tb(dut)

    # Load accum through a real ADD op: all zero except last = max.
    dut._log.info("Tests 84-88: seed accum (0 everywhere, max at last)")
    res = [0] * NCELL
    res[NCELL - 1] = 0x3FFFFF
    tb.drive(result=res)
    await tb.start_op(0b00, 0, 1)
    await tb.wait_idle()

    dut._log.info("Tests 89-93: run quantization into matrix 2")
    tb.drive(quant_data=0xAA, quantization_op=1, matrix_1=2)
    await tb.tick()
    tb.drive(quantization_op=0)
    # Case 89/92: first quantizer input is accum[0][0] = 0
    tb.check_eq(tb.golden.o_quant_ip, 0, "first o_quant_ip")
    await tb.wait_idle()

    # Cases 90-91/93: every element written, last one included
    for r in range(GRID):
        for c in range(GRID):
            await tb.read_val(2, r, c, expected=0xAA)
    tb.finish()


# ======================================================================
# CATEGORY 11: SHIFT ROW  (cases 94-102)
# ======================================================================
@cocotb.test()
async def test_11_shift_row(dut):
    tb = await make_tb(dut)

    dut._log.info("Test 97/94: zeros, shift amount 0")
    await tb.fill_matrix(0, 0x00)
    tb.drive(shift_row=1, matrix_1=0, matrix_rows=0)
    await tb.tick()
    tb.drive(shift_row=0)

    dut._log.info("Tests 98-99: unique/negative values per row")
    for r in range(GRID):
        for c in range(GRID):
            await tb.write_val(0, r, c, 0x80 + r)

    dut._log.info("Test 95 + 100-102: shift by 1")
    tb.drive(shift_row=1, matrix_1=0, matrix_rows=1)
    await tb.tick()
    tb.drive(shift_row=0)
    for r in range(GRID):
        exp = (0x80 + r + 1) if r < GRID - 1 else 0
        for c in range(GRID):
            await tb.read_val(0, r, c, expected=exp)

    dut._log.info("Test 96: shift by GRID-1")
    tb.drive(shift_row=1, matrix_1=0, matrix_rows=GRID - 1)
    await tb.tick()
    tb.drive(shift_row=0)
    for r in range(1, GRID):
        for c in range(GRID):
            await tb.read_val(0, r, c, expected=0)
    tb.finish()


# ======================================================================
# CATEGORY 12: SHIFT COLUMN  (cases 103-111)
# ======================================================================
@cocotb.test()
async def test_12_shift_col(dut):
    tb = await make_tb(dut)

    dut._log.info("Test 106/103: zeros, shift amount 0")
    await tb.fill_matrix(0, 0x00)
    tb.drive(shift_col=1, matrix_1=0, matrix_cols=0)
    await tb.tick()
    tb.drive(shift_col=0)

    dut._log.info("Tests 107-108: unique/negative values per column")
    for r in range(GRID):
        for c in range(GRID):
            await tb.write_val(0, r, c, 0x80 + c)

    dut._log.info("Test 104 + 109-111: shift by 1")
    tb.drive(shift_col=1, matrix_1=0, matrix_cols=1)
    await tb.tick()
    tb.drive(shift_col=0)
    for r in range(GRID):
        for c in range(GRID):
            exp = (0x80 + c + 1) if c < GRID - 1 else 0
            await tb.read_val(0, r, c, expected=exp)

    dut._log.info("Test 105: shift by GRID-1")
    tb.drive(shift_col=1, matrix_1=0, matrix_cols=GRID - 1)
    await tb.tick()
    tb.drive(shift_col=0)
    for r in range(GRID):
        for c in range(1, GRID):
            await tb.read_val(0, r, c, expected=0)
    tb.finish()


# ======================================================================
# CATEGORY 13: RELU  (cases 112-116)
# ======================================================================
@cocotb.test()
async def test_13_relu(dut):
    tb = await make_tb(dut)

    dut._log.info("Tests 112-115: signed relu (pos kept, neg zeroed)")
    await tb.config_matrix(2, 1)                # config also clears matrix 2
    await tb.write_val(2, 0, 0, 0x7F)
    await tb.write_val(2, 0, 1, 0x80)
    tb.drive(relu_op=1, matrix_1=2)
    await tb.tick()
    tb.drive(relu_op=0)
    await tb.read_val(2, 0, 0, expected=0x7F)
    await tb.read_val(2, 0, 1, expected=0x00)

    dut._log.info("Test 116: unsigned relu is a no-op")
    await tb.config_matrix(2, 0)
    await tb.write_val(2, 0, 0, 0x80)
    tb.drive(relu_op=1, matrix_1=2)
    await tb.tick()
    tb.drive(relu_op=0)
    await tb.read_val(2, 0, 0, expected=0x80)
    tb.finish()


# ======================================================================
# CATEGORY 14: CLAMP  (cases 117-126)
# ======================================================================
@cocotb.test()
async def test_14_clamp(dut):
    tb = await make_tb(dut)

    dut._log.info("Tests 117-120, 125: signed clamp @ 0x7F")
    await tb.config_matrix(3, 1)
    await tb.write_val(3, 0, 0, 0x10)           # below limit
    await tb.write_val(3, 0, 1, 0x7F)           # equal limit
    await tb.write_val(3, 0, 2, 0x80)           # negative -> untouched
    tb.drive(clamp_op=1, matrix_1=3, clamp_max=0x7F)
    await tb.tick()
    tb.drive(clamp_op=0)
    await tb.read_val(3, 0, 0, expected=0x10)
    await tb.read_val(3, 0, 1, expected=0x7F)
    await tb.read_val(3, 0, 2, expected=0x80)

    dut._log.info("Tests 121-124: unsigned clamp @ 0x00")
    await tb.config_matrix(3, 0)
    await tb.write_val(3, 0, 0, 0xFF)
    tb.drive(clamp_op=1, matrix_1=3, clamp_max=0x00)
    await tb.tick()
    tb.drive(clamp_op=0)
    await tb.read_val(3, 0, 0, expected=0x00)

    dut._log.info("Test 126: unsigned clamp @ 0xFF (no change)")
    await tb.write_val(3, 0, 0, 0xFF)
    tb.drive(clamp_op=1, matrix_1=3, clamp_max=0xFF)
    await tb.tick()
    tb.drive(clamp_op=0)
    await tb.read_val(3, 0, 0, expected=0xFF)
    tb.finish()


# ======================================================================
# CATEGORY 15: FSM TRANSITIONS  (cases 127-134)
# ======================================================================
@cocotb.test()
async def test_15_fsm(dut):
    tb = await make_tb(dut)
    for name, op in (("ADD", 0b00), ("EL_MUL", 0b01),
                     ("MAT_MUL", 0b11), ("DOT_PROD", 0b10)):
        dut._log.info(f"Tests 127-130+132: IDLE -> {name} -> IDLE")
        tb.check_eq(tb.golden.o_idle, 1, "idle before op")
        await tb.start_op(op, 0, 1)
        tb.check_eq(tb.golden.o_idle, 0, "busy during op")     # case 133
        await tb.wait_idle()
        tb.check_eq(tb.golden.o_idle, 1, "idle after op")

    dut._log.info("Test 131+132: IDLE -> QUANTIZATION -> IDLE")
    tb.check_eq(tb.golden.o_idle, 1, "idle before quant")
    tb.drive(quantization_op=1)
    await tb.tick()
    tb.drive(quantization_op=0)
    tb.check_eq(tb.golden.o_idle, 0, "busy during quant")
    await tb.wait_idle()
    tb.check_eq(tb.golden.o_idle, 1, "idle after quant")

    dut._log.info("Test 134: new command ignored while busy")
    await tb.start_op(0b00, 0, 1)
    tb.drive(arithmetic_op=1, arithmetic_op_type=0b11)         # ignored
    await tb.tick()
    tb.drive(arithmetic_op=0)
    await tb.wait_idle()
    tb.finish()


# ======================================================================
# CATEGORY 16: INVALID / STRESS  (cases 135-139)
# ======================================================================
@cocotb.test()
async def test_16_invalid(dut):
    tb = await make_tb(dut)

    dut._log.info("Tests 135-137: change selection/data mid-operation")
    await tb.start_op(0b00, 0, 1)
    await tb.tick()
    tb.drive(matrix_1=2, data=0xFF)
    await tb.tick()
    await tb.wait_idle()

    dut._log.info("Tests 138-139: multiple control signals together")
    tb.drive(data_load=1, shift_row=1, relu_op=1,
             matrix_1=0, matrix_rows=1, matrix_cols=0, data=0xFF)
    await tb.tick()
    tb.drive(data_load=0, shift_row=0, relu_op=0)
    # data_load has priority in the IDLE branch -> mat[0][1][0] == 0xFF
    await tb.read_val(0, 1, 0, expected=0xFF)
    tb.finish()


# ======================================================================
# CATEGORY 17: RANDOM STRESS  (cases 140-151, lockstep golden diff)
# ======================================================================
@cocotb.test()
async def test_17_random_stress(dut):
    tb = await make_tb(dut)
    random.seed(0xC0C0)
    VALS = [0x00, 0x01, 0x7F, 0x80, 0xFF]

    pulses = dict(matrix_config=0, data_load=0, data_read=0, shift_row=0,
                  shift_col=0, arithmetic_op=0, quantization_op=0,
                  relu_op=0, clamp_op=0)

    for _ in range(3000):
        tb.drive(**pulses)                               # deassert pulses
        cmd = random.randrange(14)
        fields = dict(
            matrix_1=random.randrange(NMAT),
            matrix_2=random.randrange(NMAT),
            matrix_rows=random.randrange(GRID),
            matrix_cols=random.randrange(GRID),
            data=random.choice(VALS),
            clamp_max=random.choice(VALS),
            matrix_signed=random.randrange(2),
            arithmetic_op_type=random.randrange(4),
            result=[random.getrandbits(23) for _ in range(NCELL)],
            quant_data=random.getrandbits(8),
        )
        if   cmd == 0:  fields["matrix_config"]   = 1
        elif cmd == 1:  fields["data_load"]       = 1
        elif cmd == 2:  fields["data_read"]       = 1
        elif cmd == 3:  fields["shift_row"]       = 1
        elif cmd == 4:  fields["shift_col"]       = 1
        elif cmd == 5:  fields["relu_op"]         = 1
        elif cmd == 6:  fields["clamp_op"]        = 1
        elif cmd == 7:  fields["quantization_op"] = 1
        elif cmd in (8, 9, 10):
            fields["arithmetic_op"] = 1
        elif cmd == 11:                                   # command collision
            fields["data_load"] = fields["shift_row"] = fields["relu_op"] = 1
        # cmd 12/13: idle cycle (no strobe)
        tb.drive(**fields)
        await tb.tick()
        tb.drive(arithmetic_op=0)

    await tb.wait_idle(timeout=200)
    tb.finish()