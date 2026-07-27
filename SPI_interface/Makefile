SHELL := /bin/bash

OBJ_DIR ?= Vspi_tb

VERILATOR_FLAGS = \
    -ISPI_interface\
	-ITest

IVERILOG  := iverilog
VVP       := vvp
FLAGS     := -g2012

SRC_DIR   := UART
TEST_DIR  := UART
OUT_DIR   := Test

# Output executable target
TARGET    := $(OUT_DIR)/uart_test.vvp

# Source files list
SRCS      := $(SRC_DIR)/uart_baud_gen.v \
             $(SRC_DIR)/uart_rx.v \
			 $(SRC_DIR)/uart_tx.v \
			 $(SRC_DIR)/uart_top.v \
             $(SRC_DIR)/uart_test.sv


# Default target runs the simulation
all: run

# Ensure output directory exists and compile sources
compile: $(TARGET)

$(TARGET): $(SRCS)
	@mkdir -p $(OUT_DIR)
	@echo "Compiling Verilog..."
	$(IVERILOG) $(FLAGS) -o $(TARGET) $(SRCS)

# Execute the simulation
run: compile
	@echo "Running simulation..."
	@echo ""
	@echo "--- SIMULATION OUTPUT ---"
	$(VVP) $(TARGET)

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf $(OUT_DIR)





# Lint only mode to check for errors and warnings 
lint_spi:
	verilator --lint-only $(VERILATOR_FLAGS) -f verilator.f

# Running the Simulation 
run_spi: 
	verilator --binary $(VERILATOR_FLAGS) -f verilator.f 
	./obj_dir/Vspi_tb

# Pulling up Waveforms with saved scopes 
wave_spi: 
	gtkwave spi_tb.vcd 

# Clean workspace 
clean_spi:
	rm -rf obj_dir run.log



.PHONY: all compile run clean

