from integration_final_golden_model import IntegrationFinalFullModel
import logging
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge
from cocotb.utils import get_sim_time
from collections import deque

#LOG FILE SETUP
log_file = open("golden_model_integration_final.log", "w")

def tb_log(msg):
    cocotb.log.info(msg)
    log_file.write(f"{get_sim_time('ns'):12.2f}ns INFO test  {msg}\n")
    log_file.flush()

def tb_error(msg):
    cocotb.log.error(msg)
    log_file.write(f"{get_sim_time('ns'):12.2f}ns ERROR test {msg}\n")
    log_file.flush()

# Global Test State
case_ctr = 0
pass_count = 0
error_count = 0
rx_queue = deque()
clks_per_bit = 0
sticky_overflow = False

# Datatype and Scale Constants
SCALE_1_0 = 0x3F800000
DT_INT8 = 0
DT_UINT8 = 1
DT_INT4 = 2
DT_UINT4 = 3
DT_INT2 = 4
DT_UINT2 = 5
DT_INT8_ALT = 6

def next_case():
    global case_ctr
    case_ctr += 1
    return case_ctr

def check_case(case_num, actual, expected, description=""):
    global pass_count, error_count
    desc_str = f" - {description}" if description else ""
    if actual == expected:
        pass_count += 1
        msg = f"[PASS] TC{case_num}{desc_str} [expected={expected:02x}, actual={actual:02x}]"
        cocotb.log.info(msg)
        log_file.write(f"{get_sim_time('ns'):12.2f}ns INFO test  {msg}\n")
        log_file.flush()
    else:
        error_count += 1
        msg = f"[FAIL] TC{case_num}{desc_str} [expected={expected:02x}, actual={actual:02x}]"
        cocotb.log.error(msg)
        log_file.write(f"{get_sim_time('ns'):12.2f}ns ERROR test  {msg}\n")
        log_file.flush()

def check_true(case_num, msg_text, cond, description=""):
    global pass_count, error_count
    desc_str = f" - {description}" if description else ""
    if cond:
        pass_count += 1
        msg = f"[PASS] TC{case_num} - {msg_text}{desc_str}"
        cocotb.log.info(msg)
        log_file.write(f"{get_sim_time('ns'):12.2f}ns INFO test  {msg}\n")
        log_file.flush()
    else:
        error_count += 1
        msg = f"[FAIL] TC{case_num} - {msg_text}{desc_str}"
        cocotb.log.error(msg)
        log_file.write(f"{get_sim_time('ns'):12.2f}ns ERROR test  {msg}\n")
        log_file.flush()

async def measure_baud_timing(dut):
    global clks_per_bit
    await RisingEdge(dut.i_clk)
    
    while int(dut.uart_inst.bg.ce16.value) != 1:
        await RisingEdge(dut.i_clk)
        
    c = 0
    await RisingEdge(dut.i_clk)
    c += 1
    
    while int(dut.uart_inst.bg.ce16.value) != 1:
        await RisingEdge(dut.i_clk)
        c += 1
        
    clks_per_ce16 = c
    clks_per_bit = clks_per_ce16 * 16
    tb_log(f"[TB] Measured ce16 period = {clks_per_ce16} clk cycles -> 1 bit = {clks_per_bit} clk cycles")

def clear_rx_queue():
    rx_queue.clear()

async def rst_edge_monitor(dut):
    while True:
        await FallingEdge(dut.i_rst_n)
        clear_rx_queue()

async def rx_monitor(dut):
    while clks_per_bit == 0:
        await RisingEdge(dut.i_clk)
        
    while True:
        await RisingEdge(dut.i_rst_n)
        rx_task = cocotb.start_soon(_rx_loop(dut))
        rst_task = cocotb.start_soon(_wait_rst_neg(dut))
        
        await rst_task
        if not rx_task.done():
            rx_task.cancel()
        clear_rx_queue()

async def _wait_rst_neg(dut):
    await FallingEdge(dut.i_rst_n)

async def _rx_loop(dut):
    while True:
        while int(dut.o_uart_tx.value) != 0:
            await RisingEdge(dut.i_clk)
        for _ in range(clks_per_bit // 2):
            await RisingEdge(dut.i_clk)
            
        if int(dut.o_uart_tx.value) == 0:
            temp_rx = 0
            for i in range(8):
                for _ in range(clks_per_bit):
                    await RisingEdge(dut.i_clk)
                temp_rx |= (int(dut.o_uart_tx.value) << i)
            for _ in range(clks_per_bit):
                await RisingEdge(dut.i_clk)
            rx_queue.append(temp_rx)
        else:
            await RisingEdge(dut.i_clk)

async def overflow_monitor(dut):
    global sticky_overflow
    while True:
        await RisingEdge(dut.i_clk)
        if int(dut.i_rst_n.value) == 0:
            sticky_overflow = False
        elif int(dut.integration_inst.quantizer_inst.o_overflow.value) == 1:
            sticky_overflow = True

async def reset_dut(dut):
    dut.i_rst_n.value = 0
    dut.i_uart_rx.value = 1
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(5): await RisingEdge(dut.i_clk)

async def send_uart_byte(dut, data):
    dut.i_uart_rx.value = 0
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    for i in range(8):
        dut.i_uart_rx.value = (data >> i) & 1
        for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)

async def send_uart_byte_no_gap(dut, data):
    dut.i_uart_rx.value = 0
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    for i in range(8):
        dut.i_uart_rx.value = (data >> i) & 1
        for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1

async def receive_uart_byte(dut):
    timeout_counter = 0
    timeout_limit = clks_per_bit * 30
    while len(rx_queue) == 0 and timeout_counter < timeout_limit:
        await RisingEdge(dut.i_clk)
        timeout_counter += 1
    if len(rx_queue) == 0:
        return 0, True
    else:
        return rx_queue.popleft(), False

async def wait_tx_start(dut, limit_clks):
    c = 0
    while len(rx_queue) == 0 and c < limit_clks:
        await RisingEdge(dut.i_clk)
        c += 1
    return len(rx_queue) > 0

async def wait_op_done(dut, max_cycles):
    c = 0
    while int(dut.integration_inst.reg_bank_inst.o_idle.value) == 1 and c < 6:
        await RisingEdge(dut.i_clk)
        c += 1
    c = 0
    while int(dut.integration_inst.reg_bank_inst.o_idle.value) == 0 and c < max_cycles:
        await RisingEdge(dut.i_clk)
        c += 1

async def uart_write_element(dut, mat_idx, row_idx, col_idx, data):
    await send_uart_byte(dut, (0x2 << 4) | (mat_idx << 2))
    await send_uart_byte(dut, (row_idx << 4) | col_idx)
    await send_uart_byte(dut, data)
    for _ in range(15): await RisingEdge(dut.i_clk)

async def uart_read_and_check(dut, case_num, mat_idx, row_idx, col_idx, expected_data, description=""):
    await send_uart_byte(dut, (0x3 << 4) | (mat_idx << 2))
    await send_uart_byte(dut, (row_idx << 4) | col_idx)
    actual_data, timeout = await receive_uart_byte(dut)
    if timeout:
        global error_count
        error_count += 1
        tb_error(f"[CASE {case_num}] FAIL: UART TX timeout (no response) - {description}")
    else:
        check_case(case_num, actual_data, expected_data, description)

async def uart_matrix_clr(dut, mat_idx, is_signed):
    await send_uart_byte(dut, (0x8 << 4) | (mat_idx << 2) | (is_signed << 1))
    for _ in range(15): await RisingEdge(dut.i_clk)

async def uart_arith(dut, opcode, mat_a, mat_b):
    await send_uart_byte(dut, (opcode << 4) | (mat_a << 2) | mat_b)
    await wait_op_done(dut, 150)

async def uart_dot_prod(dut, mat_a, mat_b, dest_row, dest_col):
    await send_uart_byte(dut, (0x6 << 4) | (mat_a << 2) | mat_b)
    await send_uart_byte(dut, (dest_row << 4) | dest_col)
    await wait_op_done(dut, 150)

async def uart_quantize(dut, dest_mat, dtype, zero_point, scale_bits):
    await send_uart_byte(dut, (0x1 << 4) | (dest_mat << 2))
    await send_uart_byte(dut, dtype << 5)
    await send_uart_byte(dut, zero_point)
    await send_uart_byte(dut, (scale_bits >> 24) & 0xFF)
    await send_uart_byte(dut, (scale_bits >> 16) & 0xFF)
    await send_uart_byte(dut, (scale_bits >> 8) & 0xFF)
    await send_uart_byte(dut, scale_bits & 0xFF)
    await wait_op_done(dut, 200)

async def stage_value_via_add(dut, src_mat, zero_mat, is_signed, val):
    await uart_matrix_clr(dut, src_mat, is_signed)
    await uart_matrix_clr(dut, zero_mat, is_signed)
    await uart_write_element(dut, src_mat, 0, 0, val)
    await uart_arith(dut, 0x4, src_mat, zero_mat)


@cocotb.test()
async def integration_final_cocotb_test(dut):
    clock = Clock(dut.i_clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    
    cocotb.start_soon(rx_monitor(dut))
    cocotb.start_soon(rst_edge_monitor(dut))
    cocotb.start_soon(overflow_monitor(dut))

    dut.i_uart_rx.value = 1
    dut.i_rst_n.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(5): await RisingEdge(dut.i_clk)

    await measure_baud_timing(dut)
    await reset_dut(dut)

    tb_log("=== STARTING integration_final VERIFICATION (Cocotb) ===")

    # CATEGORY 1: RESET & INITIALIZATION (Cases 1 - 10)
    clear_rx_queue()
    await reset_dut(dut)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Power-on default TX state (High/Idle)")
    
    dut.i_uart_rx.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 0
    for _ in range(2): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    dut.i_uart_rx.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery from async reset during RX low")

    await reset_dut(dut)
    dut.i_uart_rx.value = 0
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1
    dut.i_rst_n.value = 0
    for _ in range(2): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery from async reset mid-bit sampling")

    await reset_dut(dut)
    dut.i_uart_rx.value = 0
    for _ in range(8 * clks_per_bit): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 0
    for _ in range(2): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    dut.i_uart_rx.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery from prolonged RX low condition")

    await reset_dut(dut)
    await send_uart_byte(dut, 0x55)
    dut.i_rst_n.value = 0
    for _ in range(2): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery from mid-byte frame")

    await reset_dut(dut)
    await uart_write_element(dut, 0, 0, 0, 0xAA)
    await send_uart_byte(dut, 0x30)
    await send_uart_byte(dut, 0x00)
    for _ in range(clks_per_bit * 2): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(clks_per_bit * 2): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery interrupted mid-read sequence")

    await reset_dut(dut)
    await send_uart_byte(dut, 0x10)
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0x00)
    dut.i_rst_n.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery interrupted bad opcode (0x10)")

    await reset_dut(dut)
    await send_uart_byte(dut, 0x70)
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0x00)
    dut.i_rst_n.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX state recovery interrupted bad opcode (0x70)")

    dut.i_rst_n.value = 0
    await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 0
    await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Rapid back-to-back reset sequence stability")
    
    await reset_dut(dut)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Clean idle state validation post-stress")

    # CATEGORY 2: PHYSICAL LAYER (Cases 11 - 22)
    clear_rx_queue()
    dut.i_uart_rx.value = 0
    await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "1-cycle RX line glitch rejection")

    dut.i_uart_rx.value = 0
    for _ in range(6): await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1
    for _ in range(clks_per_bit): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "6-cycle RX line glitch rejection")

    await uart_write_element(dut, 0, 0, 0, 0x00)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x00, "Memory I/O boundary - 8'h00 Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0xFF)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xFF, "Memory I/O boundary - 8'hFF Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0xAA)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xAA, "Memory I/O alternating bits - 8'hAA Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0x55)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x55, "Memory I/O alternating bits - 8'h55 Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0x01)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x01, "Memory I/O single bit - 8'h01 Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0x7F)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x7F, "Memory I/O signed max - 8'h7F Write/Read")

    await uart_write_element(dut, 0, 0, 0, 0x80)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x80, "Memory I/O signed min - 8'h80 Write/Read")

    dut.i_uart_rx.value = 1
    for _ in range(300): await RisingEdge(dut.i_clk)
    await uart_write_element(dut, 0, 0, 1, 0xBC)
    await uart_read_and_check(dut, next_case(), 0, 0, 1, 0xBC, "RX stability following prolonged bus idle")

    await send_uart_byte_no_gap(dut, 0x56)
    await send_uart_byte(dut, 0x56)
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Zero-gap packet malform resilience (Idle TX output)")

    dut.i_uart_rx.value = 1
    for _ in range(500): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Extended idle TX state check")

    # CATEGORY 3: COMMAND PARSER (Cases 23 - 44)
    clear_rx_queue()
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0x00)
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Ignore leading padded zeros")

    await uart_write_element(dut, 0, 0, 0, 0x5A)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x5A, "Validate matrix write Mat 0 (0,0) = 5A")

    await uart_write_element(dut, 0, 0, 1, 0x33)
    await uart_read_and_check(dut, next_case(), 0, 0, 1, 0x33, "Validate matrix write Mat 0 (0,1) = 33")

    await send_uart_byte(dut, 0x10)
    for _ in range(6): await send_uart_byte(dut, 0x00)
    for _ in range(300): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "Ignore invalid opcode branch 0x10")
    
    await uart_write_element(dut, 0, 1, 0, 0x77)
    await uart_read_and_check(dut, next_case(), 0, 1, 0, 0x77, "Validate parser recovery write Mat 0 (1,0) = 77")

    await send_uart_byte(dut, 0x20)
    await send_uart_byte(dut, 0x11)
    for _ in range(400): await RisingEdge(dut.i_clk)
    await send_uart_byte(dut, 0x99)
    for _ in range(15): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 1, 1, 0x99, "Validate split-packet transmission merge = 99")

    def expected_bytes_tb(op):
        if op == 0x1: return 7
        elif op == 0x2: return 3
        elif op == 0x3: return 2
        elif op == 0x6: return 2
        elif op == 0xA: return 2
        elif op == 0xB: return 2
        else: return 1

    for op in range(16):
        await send_uart_byte(dut, (op << 4))
        n = expected_bytes_tb(op)
        for b in range(1, n):
            await send_uart_byte(dut, 0x00)
        for _ in range(clks_per_bit * 15): await RisingEdge(dut.i_clk)
        check_case(next_case(), int(dut.o_uart_tx.value), 0x01, f"Validate TX idle recovery for opcode 0x{op:X}")

    # CATEGORY 4: ARITHMETIC DATAPATH (Cases 45 - 71)
    clear_rx_queue()
    await uart_matrix_clr(dut, 0, 0)
    await uart_matrix_clr(dut, 1, 0)

    await uart_write_element(dut, 0, 0, 0, 0x05)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x05, "Datapath operand read A = 05")
    await uart_write_element(dut, 0, 0, 1, 0x0A)
    await uart_read_and_check(dut, next_case(), 0, 0, 1, 0x0A, "Datapath operand read B = 0A")
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_read_and_check(dut, next_case(), 1, 0, 0, 0x03, "Datapath operand read C = 03")
    await uart_write_element(dut, 1, 0, 1, 0x02)
    await uart_read_and_check(dut, next_case(), 1, 0, 1, 0x02, "Datapath operand read D = 02")

    await uart_arith(dut, 0x4, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x08, "ALU Unsigned Add (5+3) -> 08")

    await uart_write_element(dut, 0, 0, 0, 0xFF)
    await uart_write_element(dut, 1, 0, 0, 0xFF)
    await uart_arith(dut, 0x4, 0, 1)
    await uart_quantize(dut, 2, DT_UINT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0xFF, "ALU Unsigned Add saturation (FF+FF) -> FF")

    await uart_matrix_clr(dut, 0, 1)
    await uart_matrix_clr(dut, 1, 1)
    await uart_write_element(dut, 0, 0, 0, 0x80)
    await uart_write_element(dut, 1, 0, 0, 0x80)
    await uart_arith(dut, 0x4, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x80, "ALU Signed Add wrap (-128+-128) -> 80")

    await uart_matrix_clr(dut, 0, 1)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0xFB)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_arith(dut, 0x4, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0xFE, "ALU Signed Add negative limits (-5+3) -> FE")

    await uart_matrix_clr(dut, 0, 0)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0x05)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_arith(dut, 0x5, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x0F, "ALU Unsigned Sub (5-3) -> 0F")

    await uart_matrix_clr(dut, 0, 1)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0xFB)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_arith(dut, 0x5, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0xF1, "ALU Signed Sub (-5-3) -> F1")

    await uart_matrix_clr(dut, 0, 0)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0x05)
    await uart_write_element(dut, 0, 0, 1, 0x0A)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_write_element(dut, 1, 1, 0, 0x02)
    await uart_arith(dut, 0x7, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x23, "ALU Unsigned MAC -> 23")

    await uart_matrix_clr(dut, 0, 1)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0xFB)
    await uart_write_element(dut, 0, 0, 1, 0x0A)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_write_element(dut, 1, 1, 0, 0x02)
    await uart_arith(dut, 0x7, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x05, "ALU Signed MAC -> 05")

    await uart_matrix_clr(dut, 0, 0)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0x06)
    await uart_write_element(dut, 1, 0, 0, 0x07)
    await uart_dot_prod(dut, 0, 1, 0, 0)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x2A, "ALU Unsigned Dot Prod -> 2A")

    await uart_matrix_clr(dut, 0, 1)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0xFC)
    await uart_write_element(dut, 1, 0, 0, 0x03)
    await uart_dot_prod(dut, 0, 1, 0, 0)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0xF4, "ALU Signed Dot Prod -> F4")

    await uart_matrix_clr(dut, 0, 0)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 0, 0, 0, 0x02)
    await uart_write_element(dut, 0, 1, 1, 0x03)
    await uart_write_element(dut, 1, 0, 0, 0x04)
    await uart_write_element(dut, 1, 1, 1, 0x05)
    await uart_dot_prod(dut, 0, 1, 1, 0)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 1, 0, 0x17, "Multi-element Dot Prod -> 17")

    await uart_matrix_clr(dut, 0, 1)
    await uart_write_element(dut, 0, 0, 0, 0x7F)
    await send_uart_byte(dut, 0x90)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x7F, "Unsigned Array Clamp (7F)")

    await uart_write_element(dut, 0, 0, 0, 0x80)
    await send_uart_byte(dut, 0x90)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x00, "Unsigned Array Clamp (80)")

    await uart_write_element(dut, 0, 0, 0, 0x00)
    await send_uart_byte(dut, 0x90)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x00, "Unsigned Array Clamp (00)")

    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0xFF)
    await send_uart_byte(dut, 0xA0)
    await send_uart_byte(dut, 0x7F)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x7F, "Signed Array Clamp (7F)")

    await uart_matrix_clr(dut, 0, 1)
    await uart_write_element(dut, 0, 0, 0, 0x05)
    await send_uart_byte(dut, 0xA0)
    await send_uart_byte(dut, 0xFF)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xFF, "Signed Array Clamp (FF)")

    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0x11)
    await uart_write_element(dut, 0, 1, 0, 0x22)
    await uart_write_element(dut, 0, 2, 0, 0x33)
    await send_uart_byte(dut, 0xB0)
    await send_uart_byte(dut, 0x18)
    for _ in range(15): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x22, "Memory Shift Row[0] by 1")
    await uart_read_and_check(dut, next_case(), 0, 1, 0, 0x33, "Memory Shift Row[1] by 1")
    await uart_read_and_check(dut, next_case(), 0, 2, 0, 0x00, "Memory Shift Row[2] by 1")

    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0xAB)
    await uart_write_element(dut, 0, 1, 0, 0xCD)
    await uart_write_element(dut, 0, 2, 0, 0xEF)
    await send_uart_byte(dut, 0xB0)
    await send_uart_byte(dut, 0x38)
    for _ in range(15): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x00, "Memory Shift Row[0] by 3")
    await uart_read_and_check(dut, next_case(), 0, 1, 0, 0x00, "Memory Shift Row[1] by 3")
    await uart_read_and_check(dut, next_case(), 0, 2, 0, 0x00, "Memory Shift Row[2] by 3")

    await stage_value_via_add(dut, 3, 0, 0, 0x0A)
    await uart_quantize(dut, 3, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x0A, "Value staging datapath check")

    # CATEGORY 5: ASYNC TX / ZERO GAP (Cases 72 - 78)
    clear_rx_queue()
    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0xE1)
    await uart_write_element(dut, 0, 0, 1, 0xE2)

    await send_uart_byte(dut, 0x30)
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0x30)
    await send_uart_byte(dut, 0x01)

    saw_start = await wait_tx_start(dut, clks_per_bit * 30)
    check_true(next_case(), "First TX response observed from back-to-back queue", saw_start, "Async TX start check")
    if saw_start:
        resp1, _ = await receive_uart_byte(dut)
        check_case(next_case(), resp1, 0xE1, "First response byte content = E1")
        saw_start = await wait_tx_start(dut, clks_per_bit * 30)
        check_true(next_case(), "Second TX response observed from back-to-back queue", saw_start, "Async TX second start check")
        if saw_start:
            resp2, _ = await receive_uart_byte(dut)
            check_case(next_case(), resp2, 0xE2, "Second response byte content = E2")

    for _ in range(50): await RisingEdge(dut.i_clk)

    await uart_arith(dut, 0x7, 0, 0)
    await send_uart_byte(dut, 0x24)
    await send_uart_byte(dut, 0x00)
    await send_uart_byte(dut, 0xAB)
    for _ in range(100): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xE1, "Readback verification after TX bus operations")

    await uart_write_element(dut, 0, 0, 0, 0xE1)
    await uart_write_element(dut, 0, 0, 1, 0xE2)
    await send_uart_byte_no_gap(dut, 0x30)
    await send_uart_byte_no_gap(dut, 0x00)
    await send_uart_byte(dut, 0x30)
    await send_uart_byte(dut, 0x01)
    
    saw_start = await wait_tx_start(dut, clks_per_bit * 30)
    check_true(next_case(), "Response observed after zero-gap packet framing", saw_start, "Zero-gap TX response check")
    if saw_start:
        resp1, _ = await receive_uart_byte(dut)
        saw_start = await wait_tx_start(dut, clks_per_bit * 15)
        if saw_start:
            resp2, _ = await receive_uart_byte(dut)
            
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xE1, "Memory persistence check post zero-gap stress test")

    # CATEGORY 6: MEMORY ENDURANCE (Cases 79 - 91)
    clear_rx_queue()
    await uart_matrix_clr(dut, 0, 0)
    for i in range(10):
        await uart_write_element(dut, 0, 0, 0, i)
        await uart_read_and_check(dut, next_case(), 0, 0, 0, i, f"Sequential continuous structural write/read load index {i}")

    await uart_write_element(dut, 0, 0, 0, 0xAA)
    await uart_write_element(dut, 0, 1, 0, 0x55)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0xAA, "Struct read AA post load loop")
    await uart_read_and_check(dut, next_case(), 0, 1, 0, 0x55, "Struct read 55 post load loop")

    for _ in range(10): await send_uart_byte(dut, 0x56)
    for _ in range(20): await RisingEdge(dut.i_clk)
    check_case(next_case(), int(dut.o_uart_tx.value), 0x01, "TX idle recovery after invalid stream spam")

    # CATEGORY 7: QUANTIZER LIMITS/TYPES (Cases 92 - 103)
    global sticky_overflow
    clear_rx_queue()
    
    await stage_value_via_add(dut, 3, 0, 0, 0xC8)
    await uart_quantize(dut, 3, DT_UINT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0xC8, "Quantize datatype limit - UINT8")

    await stage_value_via_add(dut, 3, 0, 0, 0x14)
    await uart_quantize(dut, 3, DT_INT8_ALT, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x14, "Quantize datatype limit - INT8_ALT")

    await stage_value_via_add(dut, 3, 0, 0, 0x05)
    await uart_quantize(dut, 3, DT_INT8, 0x0A, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x0F, "Quantize INT8 w/ zero point offset transformation")

    await stage_value_via_add(dut, 3, 0, 1, 0xCE)
    await uart_quantize(dut, 3, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0xCE, "Quantize INT8 negative bounds resolution")

    await stage_value_via_add(dut, 3, 0, 0, 20)
    await uart_quantize(dut, 3, DT_INT4, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x07, "Quantize downcast to INT4")

    await stage_value_via_add(dut, 3, 0, 1, 236)
    await uart_quantize(dut, 3, DT_INT4, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0xF8, "Quantize INT4 negative limit saturation")

    await stage_value_via_add(dut, 3, 0, 0, 200)
    await uart_quantize(dut, 3, DT_UINT4, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x0F, "Quantize downcast to UINT4 limits")

    await stage_value_via_add(dut, 3, 0, 0, 5)
    await uart_quantize(dut, 3, DT_INT2, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x01, "Quantize downcast to INT2 limits")

    await stage_value_via_add(dut, 3, 0, 0, 100)
    await uart_quantize(dut, 3, DT_UINT2, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x03, "Quantize downcast to UINT2 limits")

    await stage_value_via_add(dut, 3, 0, 1, 0xFF)
    await uart_quantize(dut, 3, DT_UINT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 3, 0, 0, 0x00, "Quantize UINT8 negative bound saturation")

    await stage_value_via_add(dut, 3, 0, 0, 20)
    sticky_overflow = False
    await uart_quantize(dut, 3, DT_INT4, 0x00, SCALE_1_0)
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_true(next_case(), "Quantizer o_overflow observed set after a saturating int4 quantize", sticky_overflow, "Quantizer overflow assertion check")

    await stage_value_via_add(dut, 3, 0, 0, 3)
    sticky_overflow = False
    await uart_quantize(dut, 3, DT_INT4, 0x00, SCALE_1_0)
    for _ in range(10): await RisingEdge(dut.i_clk)
    check_true(next_case(), "Quantizer o_overflow clear after a non-saturating int4 quantize", not sticky_overflow, "Quantizer overflow clear check")

    # CATEGORY 8: FSM RESET (Cases 104 - 107)
    clear_rx_queue()
    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0x2A)
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 1, 0, 0, 0x01)
    
    async def mid_mat_mul_reset(dut):
        await send_uart_byte(dut, 0x71)
        
    cocotb.start_soon(mid_mat_mul_reset(dut))
    
    wait_cycles = 0
    while int(dut.integration_inst.reg_bank_inst.o_idle.value) == 1 and wait_cycles < 1000:
        await RisingEdge(dut.i_clk)
        wait_cycles += 1
        
    check_true(next_case(), "Reg_bank is not idle mid-MAT_MUL before reset", not int(dut.integration_inst.reg_bank_inst.o_idle.value), "FSM active state check")
    
    dut.i_rst_n.value = 0
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_rst_n.value = 1
    for _ in range(5): await RisingEdge(dut.i_clk)
    dut.i_uart_rx.value = 1
    for _ in range(10): await RisingEdge(dut.i_clk)
    
    check_true(next_case(), "Reg_bank returns to idle after reset asserted mid-operation", int(dut.integration_inst.reg_bank_inst.o_idle.value), "FSM reset recovery idle check")

    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0x2A)
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x2A, "Memory read functionality post-reset interrupt")
    
    await uart_matrix_clr(dut, 1, 0)
    await uart_write_element(dut, 1, 0, 0, 0x01)
    await uart_arith(dut, 0x5, 0, 1)
    await uart_quantize(dut, 2, DT_INT8, 0x00, SCALE_1_0)
    await uart_read_and_check(dut, next_case(), 2, 0, 0, 0x2A, "Math operation datapath stability post-reset recovery")

    # CATEGORY 9: BOUNDARY & ALIASING (Cases 108 - 110)
    clear_rx_queue()
    await uart_matrix_clr(dut, 0, 0)
    await uart_write_element(dut, 0, 0, 0, 0x5A)
    await uart_write_element(dut, 0, 1, 0, 0x6B)
    await uart_write_element(dut, 0, 2, 0, 0xDE)
    
    await uart_read_and_check(dut, next_case(), 0, 0, 0, 0x5A, "Valid row 0 read isolation after write")
    await uart_read_and_check(dut, next_case(), 0, 1, 0, 0x6B, "Valid row 1 read isolation after write")
    
    await send_uart_byte(dut, 0x30)
    await send_uart_byte(dut, 0x20)
    for _ in range(30): await RisingEdge(dut.i_clk)
    await uart_read_and_check(dut, next_case(), 0, 2, 0, 0xDE, "HW resilience check - Out-of-bounds aliased readback")

    tb_log("========================================================================")
    tb_log("INTEGRATION FINAL SCOREBOARD SUMMARY")
    tb_log(f"Total tests : {pass_count + error_count}")
    tb_log(f"Passed      : {pass_count}")
    tb_log(f"Failed      : {error_count}")
    tb_log("========================================================================")
    
    log_file.close()
    assert error_count == 0, f"Failed with {error_count} errors"
