# Usage:  make            (runs all tests, dumps waveform)
#         make clean       (wipe sim_build)

SIM            = icarus
TOPLEVEL_LANG  = verilog

#  RTL sources (reg_bank.sv + the waveform-dump helper module) 
VERILOG_SOURCES = $(PWD)/reg_bank.sv $(PWD)/waves_dump.sv

#  top-level module names 
TOPLEVEL = reg_bank

COMPILE_ARGS += -s waves_dump

#  parameters (GRID_SIZE=3, matching run.py) 
COMPILE_ARGS += -Preg_bank.GRID_SIZE=3

#  Python test module (test_reg_bank.py) 
MODULE = test_reg_bank

#  waveform dumping 
WAVES = 1

include $(shell cocotb-config --makefiles)/Makefile.sim