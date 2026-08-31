set_units -time 1.0ns
set_units -capacitance 1.0pF

# ============================================================
# CLOCK
# ============================================================

if { [info exists ::env(CLOCK_PORT)] } {
    set EXTCLK1 $::env(CLOCK_PORT)
} else {
    set EXTCLK1 "i_clk"
}

if { [info exists ::env(CLOCK_PERIOD)] } {
    set EXTCLK1_PERIOD $::env(CLOCK_PERIOD)
} else {
    set EXTCLK1_PERIOD 100
}

create_clock \
    -name "$EXTCLK1" \
    -period "$EXTCLK1_PERIOD" \
    -waveform "0 [expr $EXTCLK1_PERIOD / 2]" \
    [get_ports $EXTCLK1]


# ============================================================
# RESET
# ============================================================

set_false_path \
    -from [get_ports i_rst_n]


# ============================================================
# CLOCK UNCERTAINTY
# ============================================================

set_clock_uncertainty \
    -setup 0.5 \
    [get_clocks $EXTCLK1]

set_clock_uncertainty \
    -hold 0.1 \
    [get_clocks $EXTCLK1]

set_clock_transition \
    0.15 \
    [get_clocks $EXTCLK1]


# ============================================================
# FUNCTIONAL INPUTS
# ============================================================

set DATA_INPUTS [get_ports {
    i_uart_rx
    i_rst_n
}]

set_input_delay \
    -clock [get_clocks $EXTCLK1] \
    -max 1.50 \
    $DATA_INPUTS

set_input_delay \
    -clock [get_clocks $EXTCLK1] \
    -min 0.50 \
    $DATA_INPUTS


# ============================================================
# FUNCTIONAL UART OUTPUT
# ============================================================

set_output_delay \
    -clock [get_clocks $EXTCLK1] \
    -max 1.50 \
    [get_ports o_uart_tx_OUT]

set_output_delay \
    -clock [get_clocks $EXTCLK1] \
    -min 0.50 \
    [get_ports o_uart_tx_OUT]


# ============================================================
# STATIC PAD CONFIGURATION (FALSE PATHS)
# ============================================================

set_false_path \
    -to [get_ports { \
        i_clk_PU i_clk_PD i_rst_n_PU i_rst_n_PD i_uart_rx_PU i_uart_rx_PD \
        o_uart_tx_CS o_uart_tx_SL o_uart_tx_IE o_uart_tx_OE o_uart_tx_PU \
        o_uart_tx_PD o_uart_tx_PDRV0 o_uart_tx_PDRV1 \
    }]

set_false_path \
    -from [get_ports o_uart_tx_IN]


# ============================================================
# INPUT DRIVE
# ============================================================

set_driving_cell \
    -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 \
    -pin ZN \
    $DATA_INPUTS


# ============================================================
# OUTPUT LOAD
# ============================================================

set_load \
    0.0729 \
    [get_ports o_uart_tx_OUT]


# ============================================================
# MAX TRANSITION
# ============================================================

set_max_transition \
    6.0 \
    [current_design]

