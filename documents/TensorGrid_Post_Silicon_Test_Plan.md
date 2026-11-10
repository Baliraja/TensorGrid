# TensorGrid — Test Plan

**Project:** TensorGrid (accuracy-aware parametrizable TPU) — IEEE SSCS Chipathon 2026, Team A37  
**Document owner:** Team A37

## 1. Scope

This document defines the post-silicon validation plan for the fabricated TensorGrid chip developed by Team A37 for the IEEE SSCS Chipathon 2026.

The objective is to validate the functionality of the fabricated device through its externally accessible interfaces. Testing will focus on power-up and reset behaviour, UART communication, command decoding, matrix storage and readback, arithmetic operations, quantization, boundary handling and operation recovery.

The implemented design is an accuracy-aware parametrizable TPU with a 3 × 3 MAC grid. The chip is controlled through a UART interface. A host sends byte-encoded commands to load matrix elements, initiate operations and read back results.

The validation plan covers the following functional areas:

- Chip power-up, reset and clock operation.
- UART receive and transmit functionality.
- Command parser and opcode handling.
- Matrix element loading, storage and readback.
- ADD, element-wise multiplication, matrix multiplication and dot-product operations.
- Quantization and supported datatype encodings.
- ReLU, clamp, clear and row/column shift operations.
- Response handling during consecutive commands and repeated transactions.
- Reset recovery and matrix-address boundary handling.

The plan is intended for testing on fabricated silicon. Pre-silicon simulation results are not treated as measurements of the fabricated device. Actual measured values, equipment settings and test outcomes will be recorded during the bench session.

## 2. Pin Map and Interfaces

### 2.1 Functional interface

The following signals are the functional top-level interface identified for `A37_A`.

| Signal | Direction | Description |
|---|---|---|
| `i_clk` | Input | System clock |
| `i_rst_n` | Input | Active-low reset |
| `i_uart_rx` | Input | UART receive input from the host |
| `o_uart_tx_OUT` | Output | UART transmit output to the host |
| `o_uart_tx_IN` | Input | Pad input side of the TX I/O cell; not part of the functional UART data path |
| `VDD` | Inout | Power pin, present when `USE_POWER_PINS` is enabled |
| `VSS` | Inout | Ground pin, present when `USE_POWER_PINS` is enabled |

The top-level wrapper also contains pad-control signals, including pull-up/pull-down controls and UART TX output-enable, slew-rate, input-enable and drive-strength controls. These are wrapper-level signals rather than host data interfaces.

### 2.2 Package pin assignment

The package pin numbers, bond-wire mapping, socket connections and PCB routing are not established in the supplied design material.

| Item | Status |
|---|---|
| Logical top-level signal names | Defined by the RTL interface |
| Package pin numbers | VDD: 7, VSS: 1, i_clk: 2, i_rst_n: 3, i_uart_rx: 4, o_uart_tx_OUT: 6, o_uart_tx_IN: 5|
| Die-to-package mapping | Direct wirebond to QFN-32 leadframe |
| Test PCB or evaluation-board routing | Routed to standard 2.54mm breakout headers on GF180 Evaluation Board |
| Power and ground connection details | VDD routed to 3.3V evaluation board power plane; VSS tied to common ground |

The final bench connection table must be completed using the package and board documentation before power is applied to the device.

## 3. Operating Conditions

### 3.1 Design configuration

The following configuration values are defined in the implemented top-level RTL.

| Parameter | Design value | Description |
|---|---:|---|
| `GRID_SIZE` | 3 | 3 × 3 compute grid |
| `UART_BAUD_RATE` | 500000 | UART baud rate |
| `CLK_FREQ` | 10000000 | Configured system clock frequency |
| `BAUD_FREQ` | 4 | UART baud-generator parameter |
| `BAUD_LIMIT` | 1 | UART baud-generator parameter |

The system clock and UART configuration used during bench testing must match the implemented design configuration unless a separate supported configuration is confirmed.

### 3.2 Electrical operating conditions

The supplied design material does not establish the final silicon operating limits for supply voltage, supply current, input voltage, output loading or operating temperature. These values must be taken from the applicable GF180MCU PDK information, final chip-level design documentation and packaging requirements before testing.

| Parameter | Bench value / limit |
|---|---|
| Supply voltage | 3.3V |
| Supply current limit | 50mA max compliance limit on bench supply|
| System clock amplitude and frequency | 10 MHz configured clock; 0-3.3V CMOS logic levels |
| Reset voltage levels and timing | Active-low, 0V to 3.3V logic, min 1 ms hold time on power-up |
| UART logic voltage levels | 3.3V TTL/CMOS logic |
| Nominal test temperature | 25 °C |
| Output loading | Max 15 pF capacitive load on UART TX |

No device should be powered until the supply rails, polarity, current limits and pin connections have been confirmed.

### 3.3 Power-up and reset preparation

1. Confirm the package pinout and board connections against the approved connection table.
2. Check continuity between the relevant supply, ground and signal connections.
3. Configure the power supply to the approved voltage and current limit.
4. Ensure the active-low reset input is asserted before starting the clock and releasing the device into operation.
5. Apply power and check the supply current for unexpected behaviour.
6. Apply the configured system clock.
7. Release reset and confirm that the UART interface can communicate with the host.

The final power-up sequence and reset timing must follow the electrical requirements of the packaged device and test board.

## 4. Required Equipment

The following equipment is expected to be required. The exact board type, instrument models and electrical settings will be entered once the bench setup is finalised.

| Equipment | Purpose | Status |
|---|---|---|
| Fabricated TensorGrid chip | Device under test | Required |
| Test PCB, socket or evaluation/test board | Mechanical mounting, power and signal access | GF180 Evaluation Board |
| Regulated DC power supply | Supplies the chip power rails and monitors current | Required |
| Clock source | Provides the system clock | Required; External 10 MHz Function Generator (5Vpp square wave) |
| Host computer | Sends commands and records responses | Required |
| UART-to-USB interface or equivalent | Connects host UART signals to the chip | Required; 3.3V FTDI adapter |
| Oscilloscope | Checks clock, reset and signal integrity | As required |
| Logic analyser | Observes UART traffic and timing | As required |
| Multimeter | Checks supply voltage, continuity and static levels | Recommended |
| Jumper wires, probes and suitable cables | Bench connections | As required |

The test setup must provide access to the chip clock, reset, UART RX, UART TX, power and ground connections. Signal voltage compatibility must be checked before connecting external equipment.

## 5. Hardware Setup and Operation

This section defines the physical execution and operational flow to prepare the evaluation board and host interface before beginning functional test cases.

### 5.1 Physical Wiring, Mounting, and Capacitance Management

1. **SMD Socket Mounting:** The evaluation board will be fitted with a QFN-32 Clamshell ZIF (Zero Insertion Force) socket. *(Note: If a ZIF socket is unavailable, the chip is reflow-soldered to a QFN-to-DIP breakout board prior to testing).*
2. **Power Configuration:** A regulated DC bench supply will be connected to the VDD (3.3V) and VSS (GND) header pins. The power supply will be configured to output strictly 3.3V with a hardware compliance limit of 50 mA to protect against latch-up conditions.
3. **Clock Injection:** An external function generator will be connected to pin 2 (`i_clk`) and the board's common ground. The generator output will be configured for a 10.0 MHz square wave with High-Z output impedance, sweeping from 0V to 3.3V (3.3Vpp amplitude, 1.65V offset). The output remains disabled during this initial setup phase.
4. **Host Communication & Capacitance Management:** A 3.3V-configured FTDI USB-to-UART adapter will be connected to the board, routing adapter TX to pin 5 (`i_uart_rx`), adapter RX to pin 6 (`o_uart_tx_OUT`), and adapter GND to the board's VSS plane. 
   - **CRITICAL:** To satisfy the strict **15 pF maximum capacitive load** limit on the `o_uart_tx_OUT` pin, the connecting wire to the FTDI adapter is kept as short as physically possible (under 5 cm). Standard passive oscilloscope probes (~15 pF) are strictly prohibited on this pin during data transmission to prevent signal edge degradation. If waveform inspection is required on the TX line, an active probe or a 10x/100x low-capacitance probe will be attached.

### 5.2 Power-On Sequencing

1. The reset state is manually asserted by tying pin 3 (`i_rst_n`) to ground (0V) utilizing the board's reset jumper or switch.
2. The 3.3V DC power supply output is enabled. The current draw on the bench supply meter is monitored and must remain below 50 mA (typically <10 mA leakage).
3. The 10 MHz output on the function generator is enabled.
4. A minimum stabilization period of 1 millisecond is observed.
5. Reset is released by pulling pin 3 (`i_rst_n`) up to 3.3V, transitioning the chip into active execution.

### 5.3 Host Interaction Scripting

Because commands utilize raw hex bytes, standard ASCII terminals are bypassed. Testing is executed using a host PC Python script (utilizing `pyserial`) configured for `500000 baud`, `8 data bits`, `No parity`, and `1 stop bit`.

- **Command Transmission:** The script writes byte arrays directly to the serial buffer (e.g., `serial.write(b'\x30')` for a `READ_ELEMENT` command).
- **Response Recording:** The script reads the specified number of incoming bytes and logs the hexadecimal values for automated or manual comparison against expected arithmetic outcomes.


## 6. Post-Silicon Test Procedures

### 6.1 General test procedure

The following procedure applies to each functional test unless a test case specifies otherwise:

1. Verify that the chip is connected according to the approved pin map.
2. Apply the approved power and clock conditions.
3. Assert and release reset using the defined reset procedure.
4. Establish UART communication with the configured baud rate of 500000.
5. Send the command sequence specified in the test case.
6. Capture the UART response and any relevant electrical measurements.
7. Compare the observed behaviour with the expected behaviour.
8. Record the test result and any deviations.
9. Repeat the test where repeatability or stress behaviour is being evaluated.

### 6.2 UART command protocol reference

The command opcode is encoded in the upper nibble of the first byte. The following command definitions are identified in the implemented RTL.

| Opcode | Command | Number of bytes | Function |
|---|---|---:|---|
| `0x1` | QUANTIZE | 7 | Quantizes the internal accumulator results and writes them to the destination matrix |
| `0x2` | LOAD_ELEMENT | 3 | Writes an 8-bit value to a selected matrix element |
| `0x3` | READ_ELEMENT | 2 | Reads a selected matrix element and returns one byte over UART |
| `0x4` | ADD | 1 | Performs element-wise matrix addition |
| `0x5` | EL_MUL | 1 | Performs element-wise multiplication |
| `0x6` | DOT_PROD | 2 | Performs a dot product and stores the result at the specified accumulator position |
| `0x7` | MAT_MUL | 1 | Performs matrix multiplication |
| `0x8` | CLEAR_MATRIX | 1 | Clears a matrix and configures whether it uses signed or unsigned values |
| `0x9` | RELU | 1 | Applies ReLU to a signed matrix |
| `0xA` | CLAMP | 2 | Clamps matrix elements to the specified maximum |
| `0xB` | SHIFT_ROW_COL | 2 | Shifts matrix rows or columns, zero-filling vacated positions |

The quantizer datatype field is encoded as follows:

| Encoding | Datatype |
|---:|---|
| `0` | INT8 |
| `1` | UINT8 |
| `2` | INT4 |
| `3` | UINT4 |
| `4` | INT2 |
| `5` | UINT2 |
| `6` | INT8_ALT |
| `7` | Decoded as UINT8 by the implemented RTL |

Arithmetic operation results are held in the internal 23-bit accumulator. They are made externally observable by issuing a QUANTIZE command to write the results into a matrix, followed by READ_ELEMENT commands to retrieve the matrix elements.

### 6.3 TC-01 — Reset and TX Recovery

**Objective:** Verify initial reset behaviour and confirm that the UART transmitter becomes operational after reset.

**Procedure:**
1. Apply power and the system clock with reset asserted.
2. Release reset according to the approved reset procedure.
3. Send a valid READ_ELEMENT command for a known matrix location.
4. Capture the UART TX response.
5. Repeat the reset sequence and issue another valid command.
6. Confirm that the transmitter returns to its idle state between transactions.

**Expected behaviour:**
- The device enters its reset state when active-low reset is asserted.
- After reset release, the device accepts UART commands.
- A valid read request produces a UART response.
- The UART TX line returns to its idle logic level after transmission.

**Acceptance criteria:**
- UART communication is established after reset release.
- The expected response is received for the selected valid read request.
- The TX line returns to idle after transmission.
- The device can perform another transaction following a repeated reset.

### 6.4 TC-02 — RX Glitch and Boundary

**Objective:** Evaluate UART receive behaviour under nominal and boundary input conditions.

**Procedure:**
1. Send valid UART command bytes at the configured baud rate.
2. Repeat reception with minimum permitted inter-byte spacing for the selected command sequence.
3. Apply malformed or incomplete UART frames where the test setup permits controlled generation of such signals.
4. Send a valid command after each malformed or incomplete sequence.
5. Observe whether the following valid transaction is received and processed correctly.

**Expected behaviour:**
- Valid UART frames are received and passed to the command parser.
- Malformed or incomplete frames should not be treated as valid command data.
- The receiver should recover sufficiently to accept a subsequent valid frame.

**Acceptance criteria:**
- Valid command sequences produce the expected device response.
- Malformed or incomplete input does not cause an unintended valid operation.
- A valid command sent after the test disturbance is received and handled correctly.

### 6.5 TC-03 — Parser and Opcode

**Objective:** Verify command decoding, command length handling and response behaviour for supported and unsupported opcodes.

**Procedure:**
1. Send each supported opcode using the correct number and order of bytes.
2. Verify the behaviour of commands that return UART data, particularly READ_ELEMENT.
3. Send unsupported one-byte opcode values, including upper nibbles `0x0` and `0xC` through `0xF`.
4. Send a valid command after each unsupported opcode.
5. Compare the observed response and resulting matrix behaviour with the command definition.

**Expected behaviour:**
- Supported opcodes initiate their corresponding operations.
- Multi-byte commands consume their defined command fields.
- Unsupported opcodes do not initiate a supported operation.
- Subsequent valid commands remain processable.

**Acceptance criteria:**
- Supported commands produce their specified observable behaviour.
- Unsupported opcodes do not cause unintended matrix modification or an incorrect valid response.
- The parser correctly handles a valid command following an unsupported opcode.

### 6.6 TC-04 — Datapath and ALU

**Objective:** Validate the implemented arithmetic and matrix-manipulation operations through externally observable matrix readback.

**Procedure:**
1. Clear the source matrices and configure them for signed or unsigned operation as required.
2. Load known operand values into the selected matrix locations using LOAD_ELEMENT.
3. Issue the required arithmetic command.
4. For arithmetic operations that produce accumulator results, issue QUANTIZE to write the results into a destination matrix.
5. Read the destination matrix elements using READ_ELEMENT.
6. Compare the returned values with independently calculated expected results.
7. Repeat with positive, zero and negative operands where supported by the data configuration.

**Operations to validate:**

| Test ID | Operation | Validation |
|---|---|---|
| TC-04.1 | ADD | Element-wise addition |
| TC-04.2 | EL_MUL | Element-wise multiplication |
| TC-04.3 | MAT_MUL | Matrix multiplication |
| TC-04.4 | DOT_PROD | Dot product at the selected accumulator position |
| TC-04.5 | CLEAR_MATRIX | Matrix contents are cleared and signed or unsigned data configuration is applied |
| TC-04.6 | RELU | Negative signed values are set to zero; non-negative values are retained |
| TC-04.7 | CLAMP | Values above the configured clamp maximum are limited |
| TC-04.8 | SHIFT_ROW_COL | Row and column shifts move values in the specified direction and zero-fill vacated positions |

**Expected behaviour:**
- Each operation produces the result defined by its command semantics.
- Quantized arithmetic results can be read back from the destination matrix.
- Clear, ReLU, clamp and shift operations modify matrix contents according to their defined behaviour.

**Acceptance criteria:**
- Read-back values match the independently calculated expected results after applying the configured quantization.
- Matrix operations do not modify unrelated locations.
- Signed and unsigned cases behave according to the selected data configuration.

### 6.7 TC-05 — TX Queueing

**Objective:** Verify response handling for consecutive read requests and readback following interleaved command activity.

**Procedure:**
1. Load known values into two or more matrix locations.
2. Issue consecutive READ_ELEMENT requests with the minimum intended spacing between requests.
3. Capture the UART TX stream and record the number and order of responses.
4. Repeat with read requests separated by other valid command activity.
5. Read the original matrix locations again to confirm that stored values remain unchanged.

**Expected behaviour:**
- Each accepted read request produces the corresponding response.
- Responses that are transmitted are returned in the expected order.
- Read and transmit activity does not corrupt matrix contents.

**Acceptance criteria:**
- Returned bytes correspond to the requested matrix locations and preserve the expected order for accepted requests.
- Matrix contents remain unchanged by read transactions.
- The UART transmitter returns to idle and can handle subsequent requests.

If the transmitter cannot accept a new request while busy, the observed behaviour must be recorded and evaluated against the final interface specification. No TX FIFO behaviour is assumed by this plan.

### 6.8 TC-06 — Load Stress

**Objective:** Validate matrix loading and readback over repeated transactions and evaluate parser recovery under repeated unsupported input.

**Procedure:**
1. Select a valid matrix location.
2. Perform repeated LOAD_ELEMENT and READ_ELEMENT transactions using a sequence of known data values.
3. Compare every returned byte with the corresponding written value.
4. Load and read additional matrix locations after the repeated transaction sequence.
5. Send a sequence of unsupported opcode bytes.
6. Send a valid read request after the unsupported input sequence.

**Expected behaviour:**
- Repeated writes update the selected matrix element.
- Readback returns the most recently written value.
- Other matrix locations retain their stored values.
- Unsupported input does not prevent later valid commands from being processed.

**Acceptance criteria:**
- All tested write/read pairs return matching values.
- Additional locations retain their expected contents.
- A valid command is processed after the unsupported-input sequence.
- No unintended matrix corruption is observed.

### 6.9 TC-07 — Quantizer

**Objective:** Validate quantization behaviour for the supported datatype encodings, including signed and unsigned data formats, zero-point adjustment and datatype boundary conditions.

**Procedure:**
1. Prepare known arithmetic results in the internal accumulator using the supported datapath operations.
2. Configure the quantizer destination matrix, datatype, zero point and scale.
3. Issue QUANTIZE.
4. Read the resulting destination matrix elements.
5. Compare the returned values with an independent quantization reference calculation.
6. Repeat for the datatype encodings and boundary conditions listed below.

**Test coverage:**

| Test ID | Test condition | Validation objective |
|---|---|---|
| TC-07.1 | UINT8 boundary | Validate unsigned 8-bit output range |
| TC-07.2 | INT8_ALT encoding | Characterise the implemented encoding-6 behaviour |
| TC-07.3 | Non-zero zero point | Verify zero-point adjustment |
| TC-07.4 | INT8 negative boundary | Validate signed 8-bit lower-bound handling |
| TC-07.5 | INT4 down-conversion | Validate conversion to signed 4-bit range |
| TC-07.6 | INT4 negative saturation | Validate saturation at the negative limit |
| TC-07.7 | UINT4 down-conversion | Validate conversion to unsigned 4-bit range |
| TC-07.8 | INT2 down-conversion | Validate conversion to signed 2-bit range |
| TC-07.9 | UINT2 down-conversion | Validate conversion to unsigned 2-bit range |
| TC-07.10 | UINT8 negative input | Validate handling of a negative input for unsigned output |

**Expected behaviour:**
- The quantizer applies the configured scale and zero-point operation.
- The output is represented according to the selected datatype encoding.
- Values outside the representable range are handled according to the implemented saturation behaviour.

**Acceptance criteria:**
- Read-back values match the independent reference calculation for the selected input, scale, zero point and datatype.
- Boundary cases produce values within the representable range.
- Encoding `6` is measured and documented separately; it is not assumed to have behaviour distinct from INT8 unless confirmed by the implemented design specification.

### 6.10 TC-08 — Reset During Operation

**Objective:** Verify reset behaviour when reset is asserted while an arithmetic operation is in progress, and confirm that the device can resume normal operation afterwards.

**Procedure:**
1. Load known values into the operand matrices.
2. Issue a matrix operation that requires multiple clock cycles, such as MAT_MUL.
3. Assert active-low reset while the operation is in progress.
4. Release reset using the approved reset procedure.
5. Check that the UART interface returns to an idle and usable state.
6. Perform a matrix write/read transaction.
7. Perform a new arithmetic operation and read back its result.

**Expected behaviour:**
- Reset returns the device to its reset state.
- The UART interface can accept new commands after reset release.
- Matrix access and arithmetic operations can be performed after reset.

**Acceptance criteria:**
- The device responds to a valid command after reset release.
- A post-reset write/read operation returns the expected value.
- A post-reset arithmetic operation produces the expected quantized result.
- No unintended response or persistent busy condition prevents normal operation.

## 7. Failure Diagnosis Matrix

If a test fails, the following matrix directs the immediate troubleshooting steps before a chip is binned.

| Symptom | Primary Suspect | Next Action |
|---|---|---|
| Hard short (Current limit hit instantly) | Die mounting or package internal short | Remove die, check socket for debris. Check bare board. |
| 0 mA current draw at 3.3V | VDD/VSS bond wires broken | Verify board voltages at the socket pins using multimeter. |
| `o_uart_tx_OUT` stuck low (0V) after reset | Reset failure or missing Clock | Probe `i_clk` and `i_rst_n` directly at socket headers. |
| UART returns garbage data (Hex mismatch) | Baud rate mismatch or capacitive rounding | Verify Host PC is strictly at 500k Baud. Remove any oscilloscope probes from the TX line. |
| Commands ignored intermittently | 5V vs 3.3V Logic level mismatch | Verify FTDI adapter is outputting 3.3V logic, not 5V. |
| Occasional ALU/Math mismatch | Voltage droop during heavy logic switching | Probe VDD dynamically. Ensure bench supply lines are thick and short. |

## 8. Results Recording and Publishing

A test record must be maintained for every post-silicon test performed. Results must represent measurements and observations from the fabricated device and must not be substituted with pre-silicon simulation results.

For each test, record:

| Record field | Description |
|---|---|
| Test ID | Test case identifier, TC-01 to TC-09 |
| Test date and time | Date and time of the bench session |
| Device identification | Chip identifier, lot or package marking, if available |
| Test setup | Evaluation-board configuration |
| Equipment | Instrument make and model |
| Instrument settings | Supply settings, clock settings, UART configuration and measurement settings |
| Test conditions | Reset state, input data, commands and operating conditions |
| Expected behaviour | Expected response for the test |
| Observed behaviour | Measured UART data, waveforms, supply readings or other observations |
| Result | Pass, fail, blocked or not run |
| Notes | Deviations, anomalies and follow-up actions |

Store raw measurement files, UART logs, captured waveforms and result summaries with the corresponding test record. Any test that cannot be performed because of unavailable package information, board access or equipment must be marked as **Not Run** or **Blocked**, with the reason recorded.

## 9. Known Limitations and Validation Gaps

The following items must be resolved or accounted for during test preparation:

- Arithmetic results are not directly exposed as a parallel output; they must be quantized into a matrix and read through the UART interface.
- Internal signals such as MAC-grid valid and overflow indicators are not available as top-level functional outputs.
- The implemented RTL decodes quantizer datatype encoding `6` in the same branch as encoding `0`; its behaviour should be characterised rather than assumed to be a separate datatype implementation.
- The implemented UART transmitter does not expose a TX FIFO interface. Back-to-back request behaviour must therefore be measured without assuming that every request can be queued while transmission is busy.
- Out-of-range address behaviour must be characterised on silicon and compared with the final interface specification.

No silicon measurements or pass/fail results are included in this plan. These will be populated only after the corresponding tests have been performed.

The testplan is still a work in progress. More robust instructions, tests, and procedures will be progressively introduced over time.

## 10. Future Validation Work

After completion of the initial functional validation, the team may extend testing to include:

- Repeated operation over longer durations.
- Operation across the approved supply and temperature ranges.
- Clock-frequency margin testing, subject to the final chip operating specification.
- UART communication margin testing.
- Power-consumption measurements under idle and active workloads.
- Additional arithmetic and quantization patterns.
- Repeatability testing across multiple packaged devices, if available.

These activities are additional validation work and are not assumed to be part of the initial bench session.