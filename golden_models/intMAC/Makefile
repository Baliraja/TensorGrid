SIM ?= icarus
TOPLEVEL_LANG ?= verilog
WAVES ?= 1
 
VERILOG_SOURCES += $(PWD)/int_MAC.sv
 
TOPLEVEL = int_MAC
MODULE = test_int_mac
 
COMPILE_ARGS += -g2012
 
include $(shell cocotb-config --makefiles)/Makefile.sim
