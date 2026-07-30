import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotbext.uart import UartSource, UartSink

# --- Baud Rate & Clock Configuration ---
CLK_FREQ_HZ = 100_000_000  # 100 MHz System Clock
BAUD_RATE   = 9600         # Target Baud Rate

# For 100MHz clock and 9600 baud, GCD(100M, 153.6k) = 5120
BAUD_FREQ   = 30
BAUD_LIMIT  = 19501


async def reset_dut(dut):
    """Resets the DUT."""
    dut.clr.value = 1
    dut.serIn.value = 1
    dut.newTxData.value = 0
    dut.txData.value = 0
    dut.baudFreq.value = BAUD_FREQ
    dut.baudLimit.value = BAUD_LIMIT
    
    await Timer(100, unit="ns")
    dut.clr.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)


@cocotb.test()
async def test_uart_tx_golden(dut):
    """Golden Model Test: Verifies RTL Transmitter against a Python UART Sink."""
    
    # 1. Start the System Clock (100 MHz -> 10 ns period)
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # 2. Instantiate Golden Model Receiver (Sink) listening on serOut
    golden_tx_sink = UartSink(
        data=dut.serOut,
        baud=BAUD_RATE,
        bits=8,
        stop_bits=1
    )

    test_bytes = [0x55, 0xA5, 0xFF, 0x00, 0xDE]

    for byte_to_send in test_bytes:
        # Wait until transmitter is not busy
        while dut.txBusy.value == 1:
            await RisingEdge(dut.clk)

        # Drive data into RTL Transmitter
        dut.txData.value = byte_to_send
        dut.newTxData.value = Immediate(1)
        await RisingEdge(dut.clk)
        dut.newTxData.value = 0

        # Golden Model captures and checks serial transmission automatically
        received_data = await golden_tx_sink.read(1)
        received_byte = received_data[0]

        # Verification Assertion
        assert received_byte == byte_to_send, \
            f"[TX Mismatch] Golden Model received 0x{received_byte:02X}, expected 0x{byte_to_send:02X}"
        
        dut._log.info(f"[TX PASS] Transmitted and verified byte: 0x{byte_to_send:02X}")


@cocotb.test()
async def test_uart_rx_golden(dut):
    """Golden Model Test: Drives RTL Receiver using a Python UART Source."""
    
    # 1. Start Clock & Reset
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await reset_dut(dut)

    # 2. Instantiate Golden Model Transmitter (Source) driving serIn
    golden_rx_source = UartSource(
        data=dut.serIn,
        baud=BAUD_RATE,
        bits=8,
        stop_bits=1
    )

    test_bytes = [0x12, 0x34, 0xBE, 0xEF]

    for byte_to_send in test_bytes:
        # Send byte from Golden Source into DUT's serIn line
        await golden_rx_source.write(bytes([byte_to_send]))

        # Wait for DUT to assert newRxData signal
        while dut.newRxData.value == 0:
            await RisingEdge(dut.clk)

        # Let the signals settle for 1 clock cycle to ensure the register data is stable
        await RisingEdge(dut.clk)

        # Sample the DUT received output
        rtl_rx_byte = dut.rxData.value.to_unsigned()

        # Verification Assertion
        assert rtl_rx_byte == byte_to_send, \
            f"[RX Mismatch] RTL captured 0x{rtl_rx_byte:02X}, expected 0x{byte_to_send:02X}"
            
        dut._log.info(f"[RX PASS] Received and verified byte: 0x{byte_to_send:02X}")