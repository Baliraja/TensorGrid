import struct
import math

class BaudGenExtModel:
    """Cycle-accurate model of baudGenExt.v[cite: 10]."""
    def __init__(self, baud_freq, baud_limit):
        self.baud_freq = baud_freq
        self.baud_limit = baud_limit
        self.counter = 0
        self.ce16 = False

    def reset(self):
        self.counter = 0
        self.ce16 = False

    def step(self):
        if self.counter >= self.baud_limit:
            self.counter -= self.baud_limit
            self.ce16 = True
        else:
            self.counter += self.baud_freq
            self.ce16 = False
        return self.ce16


class UartRxModel:
    """Cycle-accurate model of uartRx.v[cite: 11]."""
    def __init__(self):
        self.inSync = 0b11
        self.count16 = 0
        self.rxBusy = False
        self.bitCount = 0
        self.dataBuf = 0
        self.rxData = 0
        self.newRxData = False

    def reset(self):
        self.inSync = 0b11
        self.count16 = 0
        self.rxBusy = False
        self.bitCount = 0
        self.dataBuf = 0
        self.rxData = 0
        self.newRxData = False

    def step(self, serIn, ce16):
        # 2-stage synchronizer[cite: 11]
        self.inSync = ((self.inSync & 0b01) << 1) | serIn

        ce1 = (self.count16 == 15) and ce16
        ce1Mid = (self.count16 == 7) and ce16

        # ce16 Counter[cite: 11]
        if ce16:
            if self.rxBusy or not ((self.inSync >> 1) & 1):
                self.count16 = (self.count16 + 1) & 0xF
            else:
                self.count16 = 0

        # rxBusy FSM[cite: 11]
        if not self.rxBusy and ce1Mid:
            self.rxBusy = True
        elif self.rxBusy and self.bitCount == 8 and ce1Mid:
            self.rxBusy = False

        # Bit Counter[cite: 11]
        if self.rxBusy and ce1Mid:
            self.bitCount = (self.bitCount + 1) & 0xF
        elif not self.rxBusy:
            self.bitCount = 0

        # Shift Register[cite: 11]
        if self.rxBusy and ce1Mid:
            sync_bit = (self.inSync >> 1) & 1
            self.dataBuf = (sync_bit << 7) | (self.dataBuf >> 1)

        # Output Register[cite: 11]
        if self.rxBusy and self.bitCount == 8 and ce1:
            self.rxData = self.dataBuf
            self.newRxData = True
        else:
            self.newRxData = False

        return self.rxData, self.newRxData


class UartTxModel:
    """Cycle-accurate model representing typical uartTx.v behavior."""
    def __init__(self):
        self.serOut = 1
        self.txBusy = False
        self.count16 = 0
        self.bitCount = 0
        self.dataBuf = 0

    def reset(self):
        self.serOut = 1
        self.txBusy = False
        self.count16 = 0
        self.bitCount = 0
        self.dataBuf = 0

    def step(self, ce16, txData, newTxData):
        ce1 = (self.count16 == 15) and ce16
        
        if newTxData and not self.txBusy:
            self.txBusy = True
            self.dataBuf = txData
            self.count16 = 0
            self.bitCount = 0
            self.serOut = 0 # Start bit
            
        elif self.txBusy:
            if ce16:
                self.count16 = (self.count16 + 1) & 0xF
            if ce1:
                self.bitCount += 1
                if self.bitCount <= 8:
                    self.serOut = (self.dataBuf >> (self.bitCount - 1)) & 1
                elif self.bitCount == 9:
                    self.serOut = 1 # Stop bit
                else:
                    self.txBusy = False
                    self.serOut = 1
        return self.serOut


class IntegrationFinalFullModel:
    """
    Top-Level 1:1 Hardware Twin matching integration_final.sv exactly[cite: 4].
    Combines cycle-accurate UART physical layer with transaction-level core math.
    """
    def __init__(self, grid_size=3, baud_freq=1, baud_limit=2):
        self.grid_size = grid_size
        
        # Instantiate UART sub-modules[cite: 4, 10, 11]
        self.baud_gen = BaudGenExtModel(baud_freq, baud_limit)
        self.uart_rx = UartRxModel()
        self.uart_tx = UartTxModel()
        
        # Core datapath state (reg_bank.sv and MAC arrays)[cite: 9]
        self.mat_arr = [[[0 for _ in range(grid_size)] for _ in range(grid_size)] for _ in range(4)]
        self.matrix_signed = [False] * 4
        self.accum = [[0 for _ in range(grid_size)] for _ in range(grid_size)]
        self.last_overflow = False
        
        # Internal TX FIFO/Queuing (hardware handles READ ops back to TX)
        self.tx_queue = []

        # Command Parser State Machine tracking variables[cite: 2]
        self.byte_count = 0
        self.target_length = 0
        self.command_buffer = []

    def reset(self):
        """Simulates i_rst_n assertion."""
        self.baud_gen.reset()
        self.uart_rx.reset()
        self.uart_tx.reset()
        self.tx_queue.clear()
        
        for m in range(4):
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    self.mat_arr[m][i][j] = 0
            self.matrix_signed[m] = False
            
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                self.accum[i][j] = 0
                
        self.last_overflow = False
        self.byte_count = 0
        self.target_length = 0
        self.command_buffer.clear()

    def clock_cycle(self, i_uart_rx):
        """
        Executes one hardware clock cycle (i_clk) of the entire top-level wrapper[cite: 4].
        """
        # Step Baud Generator[cite: 10]
        ce16 = self.baud_gen.step()
        
        # Step UART RX[cite: 11]
        rx_byte, rx_new = self.uart_rx.step(i_uart_rx, ce16)
        
        # Route new byte to Command Parser State Machine[cite: 2]
        if rx_new:
            self._process_rx_byte(rx_byte)
                
        # Pop queue to feed TX module
        tx_data = 0
        tx_new = False
        if len(self.tx_queue) > 0 and not self.uart_tx.txBusy:
            tx_data = self.tx_queue.pop(0)
            tx_new = True
            
        # Step UART TX
        o_uart_tx = self.uart_tx.step(ce16, tx_data, tx_new)
        
        return o_uart_tx

    # =========================================================================
    # COMMAND PARSER FSM[cite: 2]
    # =========================================================================
    def _expected_bytes(self, op):
        """Maps opcode to expected packet length matching SystemVerilog[cite: 2]."""
        if op == 0x1: return 7       # OP_QUANTIZE
        elif op == 0x2: return 3     # OP_LOAD_ELEMENT
        elif op == 0x3: return 2     # OP_READ_ELEMENT
        elif op == 0x6: return 2     # OP_DOT_PROD
        elif op == 0xA: return 2     # OP_CLAMP
        elif op == 0xB: return 2     # OP_SHIFT_ROW_COL
        else: return 1               # ADD, EL_MUL, MAT_MUL, MATRIX_CLR, RELU

    def _process_rx_byte(self, rx_byte):
        """Assembles multi-byte packets cycle-by-cycle matching command_parser.sv[cite: 2]."""
        if self.byte_count == 0:
            self.command_buffer = [rx_byte]
            op = (rx_byte >> 4) & 0x0F
            self.target_length = self._expected_bytes(op)
            
            if self.target_length == 1:
                self._execute_command()
                self.byte_count = 0
            else:
                self.byte_count = 1
        else:
            self.command_buffer.append(rx_byte)
            self.byte_count += 1
            
            if self.byte_count == self.target_length:
                self._execute_command()
                self.byte_count = 0

    def _execute_command(self):
        """Executes fully formed packets (mapped directly to reg_bank.sv/MAC_grid.sv actions)[cite: 2, 9]."""
        header = self.command_buffer[0]
        op = (header >> 4) & 0x0F
        mask = (1 << math.ceil(math.log2(self.grid_size))) - 1
        
        if op == 0x8:  # OP_MATRIX_CLR[cite: 2]
            mat_idx = (header >> 2) & 0x03
            is_signed = bool((header >> 1) & 0x01)
            self.matrix_signed[mat_idx] = is_signed
            for r in range(self.grid_size):
                for c in range(self.grid_size):
                    self.mat_arr[mat_idx][r][c] = 0
                    
        elif op == 0x2:  # OP_LOAD_ELEMENT[cite: 2]
            mat_idx = (header >> 2) & 0x03
            row_col_byte = self.command_buffer[1]
            row = (row_col_byte >> 6) & 0x03  # Matching SV extract
            col = row_col_byte & 0x03
            data = self.command_buffer[2]
            if row < self.grid_size and col < self.grid_size:
                self.mat_arr[mat_idx][row][col] = data
                
        elif op == 0x3:  # OP_READ_ELEMENT[cite: 2]
            mat_idx = (header >> 2) & 0x03
            row_col_byte = self.command_buffer[1]
            row = (row_col_byte >> 6) & 0x03
            col = row_col_byte & 0x03
            val = 0
            if row < self.grid_size and col < self.grid_size:
                val = self.mat_arr[mat_idx][row][col]
            self.tx_queue.append(val)
            
        elif op in [0x4, 0x5, 0x7]:  # OP_ADD, OP_EL_MUL, OP_MAT_MUL[cite: 2]
            mat_a = (header >> 2) & 0x03
            mat_b = header & 0x03
            self._run_arithmetic(op, mat_a, mat_b)
            
        elif op == 0x6:  # OP_DOT_PROD[cite: 2]
            mat_a = (header >> 2) & 0x03
            mat_b = header & 0x03
            dest_byte = self.command_buffer[1]
            dest_row = (dest_byte >> 4) & 0x03
            dest_col = dest_byte & 0x03
            self._run_dot_prod(mat_a, mat_b, dest_row, dest_col)
            
        elif op == 0x1:  # OP_QUANTIZE[cite: 2]
            dest_mat = (header >> 2) & 0x03
            dtype = (self.command_buffer[1] >> 5) & 0x07
            zero_point = self.command_buffer[2]
            scale_bytes = self.command_buffer[3:7]
            self._run_quantization(dest_mat, dtype, zero_point, scale_bytes)
            
        elif op == 0x9:  # OP_RELU[cite: 2]
            mat_idx = (header >> 2) & 0x03
            self._run_relu(mat_idx)
            
        elif op == 0xA:  # OP_CLAMP[cite: 2]
            mat_idx = (header >> 2) & 0x03
            max_val = self.command_buffer[1]
            self._run_clamp(mat_idx, max_val)
            
        elif op == 0xB:  # OP_SHIFT_ROW_COL[cite: 2]
            mat_idx = (header >> 2) & 0x03
            shift_byte = self.command_buffer[1]
            is_row = bool((shift_byte >> 3) & 0x01)
            shift_amt = shift_byte & 0x07
            self._run_shift(mat_idx, is_row, shift_amt)

    # =========================================================================
    # CORE MATH & DATAPATH LOGIC[cite: 3, 9]
    # =========================================================================
    def _to_signed(self, val, bits):
        mask = (1 << bits) - 1
        val = val & mask
        if val & (1 << (bits - 1)):
            val -= (1 << bits)
        return val

    def _to_unsigned(self, val, bits):
        mask = (1 << bits) - 1
        return val & mask

    def _get_val(self, mat_idx, r, c):
        """Fetches value considering if the matrix bank is configured as signed[cite: 9]."""
        val = self.mat_arr[mat_idx][r][c]
        if self.matrix_signed[mat_idx]:
            return self._to_signed(val, 8)
        return val

    def _accumulate(self, res):
        """Truncates and wraps MAC sums into the hardware's 23-bit signed accumulator boundaries[cite: 3, 9]."""
        return self._to_signed(res, 23)

    def _run_arithmetic(self, op, mat_a, mat_b):
        """Matrix Math operations matching reg_bank and MAC_grid functionality[cite: 7, 9]."""
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if op == 0x4:  # ADD
                    val_a = self._get_val(mat_a, i, j)
                    val_b = self._get_val(mat_b, i, j)
                    self.accum[i][j] = self._accumulate(val_a + val_b)
                elif op == 0x5:  # EL_MUL
                    val_a = self._get_val(mat_a, i, j)
                    val_b = self._get_val(mat_b, i, j)
                    self.accum[i][j] = self._accumulate(val_a * val_b)
                elif op == 0x7:  # MAT_MUL
                    dot_sum = 0
                    for k in range(self.grid_size):
                        dot_sum += self._get_val(mat_a, i, k) * self._get_val(mat_b, k, j)
                    self.accum[i][j] = self._accumulate(dot_sum)

    def _run_dot_prod(self, mat_a, mat_b, dest_row, dest_col):
        """Accumulates products across whole array into a single target coordinate cell[cite: 9]."""
        dot_sum = 0
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                dot_sum += self._get_val(mat_a, r, c) * self._get_val(mat_b, r, c)
        
        # Zero out accumulators
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                self.accum[r][c] = 0
                
        # Store result in destination index
        if dest_row < self.grid_size and dest_col < self.grid_size:
            self.accum[dest_row][dest_col] = self._accumulate(dot_sum)

    def _run_relu(self, mat_idx):
        """In-place IDLE state operation: zeros out negative elements if bank is signed[cite: 9]."""
        if self.matrix_signed[mat_idx]:
            for i in range(self.grid_size):
                for j in range(self.grid_size):
                    if self._get_val(mat_idx, i, j) < 0:
                        self.mat_arr[mat_idx][i][j] = 0

    def _run_clamp(self, mat_idx, max_val):
        """In-place IDLE state operation: bounding matrices against o_clamp_max[cite: 9]."""
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                if self.matrix_signed[mat_idx]:
                    curr = self._get_val(mat_idx, i, j)
                    s_max = self._to_signed(max_val, 8)
                    if curr > s_max:
                        self.mat_arr[mat_idx][i][j] = max_val
                else:
                    if self.mat_arr[mat_idx][i][j] > max_val:
                        self.mat_arr[mat_idx][i][j] = max_val

    def _run_shift(self, mat_idx, is_row, amt):
        """In-place IDLE state operation: Re-indexes arrays, padding with zero[cite: 9]."""
        temp = [row[:] for row in self.mat_arr[mat_idx]]
        for i in range(self.grid_size):
            for j in range(self.grid_size):
                self.mat_arr[mat_idx][i][j] = 0
        
        if is_row:
            for i in range(self.grid_size):
                new_i = i - amt
                if 0 <= new_i < self.grid_size:
                    for j in range(self.grid_size):
                        self.mat_arr[mat_idx][new_i][j] = temp[i][j]
        else:
            for j in range(self.grid_size):
                new_j = j - amt
                if 0 <= new_j < self.grid_size:
                    for i in range(self.grid_size):
                        self.mat_arr[mat_idx][i][new_j] = temp[i][j]

    # =========================================================================
    # MULTI-CYCLE QUANTIZER PIPELINE[cite: 8]
    # =========================================================================
    def _run_quantization(self, dest_mat, dtype, zero_point, scale_bytes):
        """
        Replicates the IEEE-754 float32 shift multipliers, exponents, and saturation 
        bounding limits exactly as implemented in quantizer.sv[cite: 8].
        """
        scale_int = (scale_bytes[0] << 24) | (scale_bytes[1] << 16) | (scale_bytes[2] << 8) | scale_bytes[3]
        shifts = (scale_int >> 23) & 0xFF
        mantissa = scale_int & 0x7FFFFF
        mult = (1 << 23) | mantissa
        
        is_unsigned_dtype = dtype in [1, 3, 5, 7]
        zp = zero_point
        self.last_overflow = False
        
        for r in range(self.grid_size):
            for c in range(self.grid_size):
                acc_val = self.accum[r][c]
                scaled_data = acc_val * mult
                overflow_1 = bool(scaled_data != 0 and shifts > 134)
                
                # Exponent shift calculations handling 80-bit scaling buffers[cite: 8]
                if scaled_data == 0:
                    shifted_data = 0
                elif shifts <= 134:
                    if shifts >= (150 - 48):
                        shift_amt = 150 - shifts
                        extended = scaled_data << 32
                        shifted_val = extended >> shift_amt
                        
                        truncated = shifted_val >> 32
                        bit31 = (shifted_val >> 31) & 1
                        bit32 = (shifted_val >> 32) & 1
                        lower31 = shifted_val & 0x7FFFFFFF
                        round_bit = bit31 & (bit32 | (1 if lower31 != 0 else 0))
                        
                        shifted_data = truncated + round_bit
                    else:
                        shifted_data = 0
                else:
                    shifted_data = ((1 << 47) - 1) if scaled_data > 0 else -(1 << 47)
                
                # Zero-point offset adding[cite: 8]
                if overflow_1:
                    added_data = shifted_data
                else:
                    if is_unsigned_dtype:
                        added_data = shifted_data + zp
                    else:
                        zp_signed = self._to_signed(zp, 8)
                        added_data = shifted_data + zp_signed
                
                # Saturation bounding and Datatype Casting[cite: 8]
                q_val, ovf_flag = self._cast_to_dtype(added_data, dtype)
                if ovf_flag or overflow_1:
                    self.last_overflow = True
                
                self.mat_arr[dest_mat][r][c] = q_val

    def _cast_to_dtype(self, val, dtype):
        """Mirrors the specific target datatypes, min/max clipping, and bit padding in quantizer.sv[cite: 8]."""
        if dtype in [0, 6]:  # int8
            if val > 127: return 0x7F, True
            if val < -128: return 0x80, True
            return self._to_unsigned(val, 8), False
            
        elif dtype in [1, 7]:  # uint8
            if val > 255: return 0xFF, True
            if val < 0: return 0x00, True
            return self._to_unsigned(val, 8), False
            
        elif dtype == 2:  # int4 (-8 to 7, padded to 8 bits)[cite: 8]
            if val > 7: return 0x07, True
            if val < -8: return 0xF8, True
            padded_val = (val & 0x0F) | (0xF0 if (val & 0x08) else 0)
            return padded_val, False
            
        elif dtype == 3:  # uint4 (0 to 15, padded to 8 bits)[cite: 8]
            if val > 15: return 0x0F, True
            if val < 0: return 0x00, True
            return (val & 0x0F), False
            
        elif dtype == 4:  # int2 (-2 to 1, padded to 8 bits)[cite: 8]
            if val > 1: return 0x01, True
            if val < -2: return 0xFE, True
            padded_val = (val & 0x03) | (0xFC if (val & 0x02) else 0)
            return padded_val, False
            
        elif dtype == 5:  # uint2 (0 to 3, padded to 8 bits)[cite: 8]
            if val > 3: return 0x03, True
            if val < 0: return 0x00, True
            return (val & 0x03), False
            
        return self._to_unsigned(val, 8), False