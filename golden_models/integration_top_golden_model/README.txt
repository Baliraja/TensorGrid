# Integration Final - Cocotb Hardware Verification Suite

A comprehensive Cocotb-driven testbench designed to verify the complete integration datapath, command parser, register bank, ALU, quantizer, and UART protocol interfaces.

---

## 1. Prerequisites & Version Requirements

To run this verification environment successfully, ensure your system meets the following software dependencies and version compatibilities:

* Operating System: 
  * Cross-compatible with Linux (Ubuntu, RHEL, etc.) and Windows (via MSYS2 / MinGW64).
* Python: 
  * Version 3.8 up to 3.14+ (Tested and compatible with Python 3.14.6).
* Cocotb & Cocotb-Tools: 
  * Version v2.0.1 or newer installed within your active Python virtual environment.
* Simulator: 
  * Icarus Verilog (iverilog / vvp): Version v13.0 (stable) or later. Full support for VPI and Verilog/SystemVerilog structural modeling.
* Waveform Viewer (Optional): 
  * GTKWave: Latest stable release (compatible with .fst and .vcd trace outputs).

---

## 2. File Hierarchy

Organize your project directory as follows to ensure the build system correctly locates the RTL sources, Python testbench, and output logs:

~./integration_final/
├── integration_final_TB.py       # Main Cocotb testbench script (110 test cases)
├── GNUmakefile                   # Default build automation file for make
├── integration_final_golden_model.py # Golden model
├── integration_final.v
├── uart.v
├── reg_bank.v
├── command_parser.sv
├── ...
└── sim_build/                    # (Auto-generated) Compiled simulation binaries & traces
    ├── sim.vvp
    └── integration_final.fst     # Generated when WAVES=1 is enabled

---

### Standard Run
Simply open your terminal in the project directory and run:
make

## 4. Viewing Waveforms

Once a simulation finishes an integration_final.fst waveform file is compiled directly into the sim_build/ directory.

To open and inspect the waves using GTKWave:
gtkwave sim_build/integration_final.fst

---

## 5. Outputs & Logs

* Terminal Output: Displays real-time test execution progress, matching hardware time steps in nanoseconds (ns), along with the final score summary (Passed: 110 | Failed: 0).
* Log File (golden_model_integration_final.log): Automatically generated in your project root directory during the run, providing a permanent, timestamped record of all simulation logs and pass/fail states.