"""
Golden (reference) model for reg_bank.sv

Design intent: this class is a bit-for-bit, cycle-for-cycle behavioral twin
of the RTL. You drive it exactly like the DUT (same inputs, same clock
edges) and diff its output-facing state against the DUT's ports/probed
signals every cycle inside a cocotb test.

Usage pattern in a cocotb test:

    golden = GoldenRegBank(grid_size=3)

    for _ in range(N):
        await RisingEdge(dut.i_clk)
        # after this edge, sample DUT outputs, THEN drive next-cycle inputs,
        # THEN step the golden model with the SAME inputs that were driving
        # the DUT during the edge that just occurred.
        golden.step(sampled_inputs)
        assert golden.o_idle == int(dut.o_idle.value)
        ...

Key point: this model does NOT simulate the external MAC grid or quantizer.
It takes i_result / i_quant_data as given (same as the RTL does) — so in
a cocotb testbench you still need a behavioral stub for those two blocks,
OR (recommended for a pure reg_bank unit test) drive i_result/i_quant_data
yourself from a golden MAC/quantizer function and feed the same values to
both DUT and this model.
"""

from dataclasses import dataclass, field
from enum import IntEnum


class State(IntEnum):
    IDLE = 0
    ADD = 1
    EL_MUL = 2
    MAT_MUL = 3
    DOT_PROD = 4
    QUANTIZATION = 5


@dataclass
class Inputs:
    rst_n: int = 1
    matrix_config: int = 0
    matrix_signed: int = 0
    data_load: int = 0
    data_read: int = 0
    shift_row: int = 0
    shift_col: int = 0
    arithmetic_op: int = 0
    arithmetic_op_type: int = 0   # 00 add, 01 el_mul, 10 dot_prod, 11 mat_mul
    quantization_op: int = 0
    relu_op: int = 0
    clamp_op: int = 0
    clamp_max: int = 0
    matrix_1: int = 0
    matrix_2: int = 0
    matrix_rows: int = 0
    matrix_cols: int = 0
    data: int = 0
    result: list = field(default_factory=list)   # flat list[GRID*GRID] of 23-bit signed ints
    quant_data: int = 0


def _sext(val, bit, width):
    """sign-extend an unsigned `width`-bit value if bit `bit` (MSB) set and sign flag true."""
    return val


class GoldenRegBank:
    def __init__(self, grid_size=3):
        self.N = grid_size

        # storage
        self.mat_arr = [[[0] * self.N for _ in range(self.N)] for _ in range(4)]
        self.matrix_signed = [0, 0, 0, 0]
        self.accum = [[0] * self.N for _ in range(self.N)]

        # FSM
        self.state = State.IDLE

        # latched-on-IDLE config
        self.matrix_sel_a = 0
        self.matrix_sel_b = 0
        self.matrix_rows_st = 0
        self.matrix_cols_st = 0

        # streaming address counters
        self.rows_a = 0
        self.cols_a = 0
        self.rows_b = 0
        self.cols_b = 0

        self.oper_ctr = 0

        # quantization address delay line (4 stages)
        self.rows_a_d = [0, 0, 0, 0]
        self.cols_a_d = [0, 0, 0, 0]

        # registered outputs
        self.o_data_rd = 0
        self.o_idle = 1
        self.o_grid_reset = 0
        self.o_quant_reset = 0
        self.o_quant_ip = 0
        # combinational per-cycle outputs (valid AFTER step(), reflect state
        # going INTO this cycle, matching RTL's always_comb using
        # current_state/rows_a/etc as they stood before the clock edge)
        self.o_data_a = [0] * (self.N * self.N)
        self.o_data_b = [0] * (self.N * self.N)
        self.o_data_valid = [0] * (self.N * self.N)

        self._recompute_comb()

    # Combinational outputs: recompute from *current* (pre-edge) state.
    # Call this before step() consumes a clock edge, to get what the RTL
    # would be driving onto o_data_a/o_data_b/o_data_valid/o_quant_ip/
    # o_grid_reset/o_quant_reset/o_idle THIS cycle (i.e. sample these
    # before calling step() if you want the "current cycle" combinational
    # view; step() will refresh them for the NEXT cycle at the end).
    def _recompute_comb(self):
        N = self.N
        st = self.state

        self.o_idle = 1 if st == State.IDLE else 0
        self.o_grid_reset = 0 if (st == State.IDLE or st == State.QUANTIZATION) else 1
        self.o_quant_reset = 1 if st == State.QUANTIZATION else 0

        if st == State.QUANTIZATION:
            self.o_quant_ip = self.accum[self.rows_a][self.cols_a]
        else:
            self.o_quant_ip = 0

        data_a = [0] * (N * N)
        data_b = [0] * (N * N)
        valid = [0] * (N * N)

        for i in range(N):
            for j in range(N):
                idx = i * N + j
                if st == State.ADD:
                    valid[idx] = 1 if self.oper_ctr < 2 else 0
                elif st in (State.IDLE, State.QUANTIZATION):
                    valid[idx] = 0
                elif st == State.DOT_PROD:
                    valid[idx] = (1 if self.oper_ctr == 0 else 0) if (i == 0 and j == 0) else 0
                else:  # EL_MUL, MAT_MUL
                    valid[idx] = 1 if self.oper_ctr == 0 else 0

                if st == State.ADD:
                    if self.oper_ctr == 0:
                        v = self.mat_arr[self.matrix_sel_a][i][j]
                        a9 = (1 << 8 | v) if (self.matrix_signed[self.matrix_sel_a] and (v & 0x80)) else v
                    elif self.oper_ctr == 1:
                        v = self.mat_arr[self.matrix_sel_b][i][j]
                        a9 = (1 << 8 | v) if (self.matrix_signed[self.matrix_sel_b] and (v & 0x80)) else v
                    else:
                        a9 = 0
                    data_a[idx] = a9
                    data_b[idx] = 1
                elif st == State.EL_MUL:
                    va = self.mat_arr[self.matrix_sel_a][i][j]
                    vb = self.mat_arr[self.matrix_sel_b][i][j]
                    data_a[idx] = (1 << 8 | va) if (self.matrix_signed[self.matrix_sel_a] and (va & 0x80)) else va
                    data_b[idx] = (1 << 8 | vb) if (self.matrix_signed[self.matrix_sel_b] and (vb & 0x80)) else vb
                elif st == State.MAT_MUL:
                    va = self.mat_arr[self.matrix_sel_a][i][self.cols_a]
                    vb = self.mat_arr[self.matrix_sel_b][self.rows_b][j]
                    data_a[idx] = (1 << 8 | va) if (self.matrix_signed[self.matrix_sel_a] and (va & 0x80)) else va
                    data_b[idx] = (1 << 8 | vb) if (self.matrix_signed[self.matrix_sel_b] and (vb & 0x80)) else vb
                elif st == State.DOT_PROD:
                    if i == 0 and j == 0:
                        va = self.mat_arr[self.matrix_sel_a][self.rows_a][self.cols_a]
                        vb = self.mat_arr[self.matrix_sel_b][self.rows_b][self.cols_b]
                        data_a[idx] = (1 << 8 | va) if (self.matrix_signed[self.matrix_sel_a] and (va & 0x80)) else va
                        data_b[idx] = (1 << 8 | vb) if (self.matrix_signed[self.matrix_sel_b] and (vb & 0x80)) else vb
                    else:
                        data_a[idx] = 0
                        data_b[idx] = 0
                else:
                    data_a[idx] = 0
                    data_b[idx] = 0

        self.o_data_a = data_a
        self.o_data_b = data_b
        self.o_data_valid = valid


    # step(): advance one clock edge, given the Inputs that were driving
    # the DUT on that same edge. Mirrors all always_ff blocks + next_state
    # combinational logic. Call _recompute_comb() is done automatically
    # at the end so self.o_data_a/etc reflect the NEW (post-edge) state,
    # ready for the following cycle's comparison.

    def step(self, inp: Inputs):
        N = self.N

        if not inp.rst_n:
            self._reset()
            self._recompute_comb()
            return


        # RAW-hazard fix: mirror RTL non-blocking-assignment semantics.
        # In the RTL, the mat_arr update and the o_data_rd update live in
        # two independent always_ff blocks. Both read mat_arr at its
        # PRE-edge value, then commit new values in parallel. Python
        # assignments are blocking, so we must snapshot the read location
        # BEFORE any mat_arr modification is performed below.
        rd_snapshot = self.mat_arr[inp.matrix_1][inp.matrix_rows][inp.matrix_cols]

        st = self.state

        # next_state combinational logic 
        next_state = st
        if st == State.IDLE:
            if inp.arithmetic_op:
                next_state = {0b00: State.ADD, 0b01: State.EL_MUL,
                               0b11: State.MAT_MUL, 0b10: State.DOT_PROD}.get(inp.arithmetic_op_type, State.IDLE)
            elif inp.quantization_op:
                next_state = State.QUANTIZATION
        elif st in (State.ADD, State.QUANTIZATION):
            if self.oper_ctr == 4:
                next_state = State.IDLE
        elif st in (State.EL_MUL, State.MAT_MUL, State.DOT_PROD):
            if self.oper_ctr == 3:
                next_state = State.IDLE
        else:
            next_state = State.IDLE

        #  matrix_signed update (independent of state, config-gated)
        if inp.matrix_config:
            self.matrix_signed[inp.matrix_1] = inp.matrix_signed

        #  matrix_sel_a/b, matrix_rows_st/cols_st: latch only in IDLE
        if st == State.IDLE:
            new_sel_a = inp.matrix_1
            new_sel_b = inp.matrix_2
            new_rows_st = inp.matrix_rows
            new_cols_st = inp.matrix_cols
        else:
            new_sel_a = self.matrix_sel_a
            new_sel_b = self.matrix_sel_b
            new_rows_st = self.matrix_rows_st
            new_cols_st = self.matrix_cols_st

        #  rows_a/cols_a/rows_b/cols_b counters 
        rows_a, cols_a, rows_b, cols_b = self.rows_a, self.cols_a, self.rows_b, self.cols_b
        if st == State.DOT_PROD:
            n_rows_a = rows_a + 1
            n_rows_b = rows_b + 1
            n_cols_a, n_cols_b = cols_a, cols_b
            if rows_a == N - 1:
                n_rows_a = 0
                n_rows_b = 0
                n_cols_a = cols_a + 1
                n_cols_b = cols_b + 1
                if cols_a == N - 1:
                    n_rows_a, n_rows_b, n_cols_a, n_cols_b = rows_a, rows_b, cols_a, cols_b
        elif st == State.MAT_MUL:
            n_cols_a = cols_a + 1
            n_rows_b = rows_b + 1
            n_rows_a, n_cols_b = rows_a, cols_b
            if cols_a == N - 1:
                n_cols_a, n_rows_b = cols_a, rows_b
        elif st == State.QUANTIZATION:
            n_rows_a = rows_a + 1
            n_cols_a = cols_a
            n_rows_b, n_cols_b = rows_b, cols_b
            if rows_a == N - 1:
                n_rows_a = 0
                n_cols_a = cols_a + 1
                if cols_a == N - 1:
                    n_rows_a, n_cols_a = rows_a, cols_a
        else:
            n_rows_a = n_cols_a = n_rows_b = n_cols_b = 0

        #  oper_ctr 
        oc = self.oper_ctr
        if st in (State.ADD, State.EL_MUL):
            n_oc = (oc + 1) & 0x7
        elif st == State.MAT_MUL:
            n_oc = (oc + 1) & 0x7 if cols_a == N - 1 else 0
        elif st in (State.DOT_PROD, State.QUANTIZATION):
            n_oc = (oc + 1) & 0x7 if (rows_a == N - 1 and cols_a == N - 1) else 0
        else:
            n_oc = 0

        #  rows_a_d / cols_a_d delay line (always shifts) 
        new_rows_a_d = [rows_a] + self.rows_a_d[0:3]
        new_cols_a_d = [cols_a] + self.cols_a_d[0:3]

        #  accum / mat_arr writes 
        if st == State.ADD:
            if oc == 4:
                for i in range(N):
                    for j in range(N):
                        self.accum[i][j] = _to_signed23(inp.result[i * N + j])
        elif st in (State.EL_MUL, State.MAT_MUL):
            if oc == 3:
                for i in range(N):
                    for j in range(N):
                        self.accum[i][j] = _to_signed23(inp.result[i * N + j])
        elif st == State.DOT_PROD:
            if oc == 3:
                self.accum[self.matrix_rows_st][self.matrix_cols_st] = _to_signed23(inp.result[0])
        elif st == State.QUANTIZATION:
            self.mat_arr[self.matrix_sel_a][self.rows_a_d[3]][self.cols_a_d[3]] = inp.quant_data & 0xFF
        elif st == State.IDLE:
            if inp.matrix_config:
                for i in range(N):
                    for j in range(N):
                        self.mat_arr[inp.matrix_1][i][j] = 0
            elif inp.data_load:
                self.mat_arr[inp.matrix_1][inp.matrix_rows][inp.matrix_cols] = inp.data & 0xFF
            elif inp.shift_row:
                old = [row[:] for row in self.mat_arr[inp.matrix_1]]
                for i in range(N):
                    for j in range(N):
                        if i < N - inp.matrix_rows:
                            self.mat_arr[inp.matrix_1][i][j] = old[i + inp.matrix_rows][j]
                        else:
                            self.mat_arr[inp.matrix_1][i][j] = 0
            elif inp.shift_col:
                old = [row[:] for row in self.mat_arr[inp.matrix_1]]
                for i in range(N):
                    for j in range(N):
                        if j < N - inp.matrix_cols:
                            self.mat_arr[inp.matrix_1][i][j] = old[i][j + inp.matrix_cols]
                        else:
                            self.mat_arr[inp.matrix_1][i][j] = 0
            elif inp.relu_op:
                if self.matrix_signed[inp.matrix_1]:
                    for i in range(N):
                        for j in range(N):
                            if self.mat_arr[inp.matrix_1][i][j] & 0x80:
                                self.mat_arr[inp.matrix_1][i][j] = 0
            elif inp.clamp_op:
                for i in range(N):
                    for j in range(N):
                        v = self.mat_arr[inp.matrix_1][i][j]
                        if self.matrix_signed[inp.matrix_1]:
                            if _to_signed8(v) > _to_signed8(inp.clamp_max):
                                self.mat_arr[inp.matrix_1][i][j] = inp.clamp_max
                        else:
                            if v > inp.clamp_max:
                                self.mat_arr[inp.matrix_1][i][j] = inp.clamp_max

        #  o_data_rd (separate always_ff, own enable) 
        # Uses the PRE-edge snapshot to match RTL non-blocking semantics,
        # so a same-cycle write to the same address does not forward here.
        if inp.data_read:
            self.o_data_rd = rd_snapshot

        #  commit all next-state values 
        self.state = next_state
        self.matrix_sel_a, self.matrix_sel_b = new_sel_a, new_sel_b
        self.matrix_rows_st, self.matrix_cols_st = new_rows_st, new_cols_st
        self.rows_a, self.cols_a, self.rows_b, self.cols_b = n_rows_a, n_cols_a, n_rows_b, n_cols_b
        self.oper_ctr = n_oc
        self.rows_a_d, self.cols_a_d = new_rows_a_d, new_cols_a_d

        self._recompute_comb()

    def _reset(self):
        N = self.N
        self.state = State.IDLE
        self.matrix_signed = [0, 0, 0, 0]
        self.mat_arr = [[[0] * N for _ in range(N)] for _ in range(4)]
        self.accum = [[0] * N for _ in range(N)]
        self.matrix_sel_a = self.matrix_sel_b = 0
        self.matrix_rows_st = self.matrix_cols_st = 0
        self.rows_a = self.cols_a = self.rows_b = self.cols_b = 0
        self.oper_ctr = 0
        self.rows_a_d = [0, 0, 0, 0]
        self.cols_a_d = [0, 0, 0, 0]
        self.o_data_rd = 0


def _to_signed23(v):
    v &= (1 << 23) - 1
    return v - (1 << 23) if v & (1 << 22) else v


def _to_signed8(v):
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v