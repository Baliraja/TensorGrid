SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES = $(PWD)/quantizer.sv
TOPLEVEL = quantizer
MODULE = test_quantizer

COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
