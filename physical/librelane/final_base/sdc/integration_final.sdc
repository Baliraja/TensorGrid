###############################################################################
# Created by write_sdc
###############################################################################
current_design integration_final
###############################################################################
# Timing Constraints
###############################################################################
create_clock -name i_clk -period 50.0000 [get_ports {i_clk}]
set_clock_transition 0.1500 [get_clocks {i_clk}]
set_clock_uncertainty -setup 0.5000 i_clk
set_clock_uncertainty -hold 0.1000 i_clk
set_propagated_clock [get_clocks {i_clk}]
set_input_delay 0.5000 -clock [get_clocks {i_clk}] -min -add_delay [get_ports {i_rst_n}]
set_input_delay 1.5000 -clock [get_clocks {i_clk}] -max -add_delay [get_ports {i_rst_n}]
set_input_delay 0.5000 -clock [get_clocks {i_clk}] -min -add_delay [get_ports {i_uart_rx}]
set_input_delay 1.5000 -clock [get_clocks {i_clk}] -max -add_delay [get_ports {i_uart_rx}]
set_output_delay 0.5000 -clock [get_clocks {i_clk}] -min -add_delay [get_ports {o_uart_tx}]
set_output_delay 1.5000 -clock [get_clocks {i_clk}] -max -add_delay [get_ports {o_uart_tx}]
set_false_path\
    -from [get_ports {i_rst_n}]
###############################################################################
# Environment
###############################################################################
set_load -pin_load 0.0729 [get_ports {o_uart_tx}]
set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 -pin {ZN} -input_transition_rise 0.0000 -input_transition_fall 0.0000 [get_ports {i_rst_n}]
set_driving_cell -lib_cell gf180mcu_fd_sc_mcu7t5v0__inv_1 -pin {ZN} -input_transition_rise 0.0000 -input_transition_fall 0.0000 [get_ports {i_uart_rx}]
###############################################################################
# Design Rules
###############################################################################
set_max_transition 6.0000 [current_design]
