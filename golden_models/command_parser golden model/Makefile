SIM ?= icarus
TOPLEVEL_LANG ?= verilog

VERILOG_SOURCES += $(PWD)/command_parser_updated.sv
COCOTB_TOPLEVEL = command_parser
COCOTB_TEST_MODULES = test_command_parser

COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
