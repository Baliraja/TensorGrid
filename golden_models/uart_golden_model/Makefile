# Simulator setup
SIM ?= icarus
TOPLEVEL_LANG ?= verilog

# RTL Source Files
VERILOG_SOURCES += $(PWD)/uart_baud_gen.v
VERILOG_SOURCES += $(PWD)/uart_tx.v
VERILOG_SOURCES += $(PWD)/uart_rx.v
VERILOG_SOURCES += $(PWD)/uart_top.v
COMPILE_ARGS += -g2012
# Top module & Python Testbench module name
TOPLEVEL = uartTopBaseExt 
MODULE   = test_uart

include $(shell cocotb-config --makefiles)/makefile.sim