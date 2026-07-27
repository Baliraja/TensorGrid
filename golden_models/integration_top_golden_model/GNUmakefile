SIM ?= icarus
TOPLEVEL_LANG ?= verilog

COMPILE_ARGS += -g2012

VERILOG_SOURCES += $(PWD)/integration_final.sv
VERILOG_SOURCES += $(PWD)/command_parser.sv
VERILOG_SOURCES += $(PWD)/int_MAC.sv
VERILOG_SOURCES += $(PWD)/MAC_grid.sv
VERILOG_SOURCES += $(PWD)/quantizer.sv
VERILOG_SOURCES += $(PWD)/reg_bank.sv
VERILOG_SOURCES += $(PWD)/integration_minus_UART.sv
VERILOG_SOURCES += $(PWD)/uart_baud_gen.v
VERILOG_SOURCES += $(PWD)/uart_rx.v
VERILOG_SOURCES += $(PWD)/uart_tx.v
VERILOG_SOURCES += $(PWD)/uartTopBaseExt.v

TOPLEVEL = integration_final
#python test module
MODULE = integration_final_TB

export COCOTB_HDL_TIMEUNIT = 1ns
export COCOTB_HDL_TIMEPRECISION = 1ps

WAVES = 1

include $(shell cocotb-config --makefiles)/Makefile.sim