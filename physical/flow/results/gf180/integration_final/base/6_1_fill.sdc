###############################################################################
# Created by write_sdc
###############################################################################
current_design integration_final
###############################################################################
# Timing Constraints
###############################################################################
create_clock -name core_clock -period 40.0000 [get_ports {i_clk}]
set_propagated_clock [get_clocks {core_clock}]
create_clock -name vclk_core_clock -period 40.0000 
set_clock_latency 1.1200 [get_clocks {vclk_core_clock}]
set_input_delay 8.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {i_rst_n}]
set_input_delay 8.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {i_uart_rx}]
set_output_delay 8.0000 -clock [get_clocks {vclk_core_clock}] -add_delay [get_ports {o_uart_tx}]
set_false_path\
    -from [get_ports {i_rst_n}]
###############################################################################
# Environment
###############################################################################
###############################################################################
# Design Rules
###############################################################################
