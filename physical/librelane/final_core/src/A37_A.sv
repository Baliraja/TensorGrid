`default_nettype none

// Suppress Verilator strict checks for the unassigned physical power/ground pins
/* verilator lint_off UNUSED */
/* verilator lint_off UNDRIVEN */

module A37_A #(
    parameter GRID_SIZE      = 3,
    parameter UART_BAUD_RATE = 500000,
    parameter CLK_FREQ       = 10000000,
    parameter BAUD_FREQ      = 4,
    parameter BAUD_LIMIT     = 1
)(
`ifdef USE_POWER_PINS
    inout wire VDD,
    inout wire VSS,
`endif
    // ============================================================
    // CLOCK
    // ============================================================
    input  logic i_clk,
    output logic i_clk_PU,
    output logic i_clk_PD,

    // ============================================================
    // RESET
    // ============================================================
    input  logic i_rst_n,
    output logic i_rst_n_PU,
    output logic i_rst_n_PD,

    // ============================================================
    // UART RX
    // ============================================================
    input  logic i_uart_rx,
    output logic i_uart_rx_PU,
    output logic i_uart_rx_PD,

    // ============================================================
    // UART TX
    // ============================================================
    output logic o_uart_tx_CS,
    output logic o_uart_tx_SL,
    output logic o_uart_tx_IE,
    output logic o_uart_tx_OE,
    output logic o_uart_tx_PU,
    output logic o_uart_tx_PD,
    output logic o_uart_tx_OUT,
    output logic o_uart_tx_PDRV0,
    output logic o_uart_tx_PDRV1,
        input  logic o_uart_tx_IN,

);

    // ============================================================
    // PAD TIE-OFFS
    // ============================================================
    
    assign i_clk_PU = 1'b0;
    assign i_clk_PD = 1'b0;

    assign i_rst_n_PU = 1'b1;
    assign i_rst_n_PD = 1'b0;

    assign i_uart_rx_PU = 1'b0;
    assign i_uart_rx_PD = 1'b0;

    assign o_uart_tx_OE    = 1'b1;
    assign o_uart_tx_SL    = 1'b0;
    assign o_uart_tx_IE    = 1'b0;
    assign o_uart_tx_PU    = 1'b0;
    assign o_uart_tx_PD    = 1'b0;
    assign o_uart_tx_PDRV0 = 1'b1;
    assign o_uart_tx_PDRV1 = 1'b0;

    // ============================================================
    // THE SINK (Fixes RSZ-0074 1-pin crash)
    // ============================================================
    // We capture the unused IN pad in a flop and drive the unused CS pad.
    // This creates two legal 2-pin nets (pad->flop, flop->pad) instead of 
    // a dangling pad or an illegal feedthrough.
    logic dummy_reg;
    always_ff @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n)
            dummy_reg <= 1'b0;
        else
            dummy_reg <= o_uart_tx_IN;
    end
    
    assign o_uart_tx_CS = dummy_reg;

    // ============================================================
    // CORE INSTANTIATION
    // ============================================================
    integration_final #(
        .GRID_SIZE      (GRID_SIZE),
        .UART_BAUD_RATE (UART_BAUD_RATE),
        .CLK_FREQ       (CLK_FREQ),
        .BAUD_FREQ      (BAUD_FREQ),
        .BAUD_LIMIT     (BAUD_LIMIT)
    ) u_integration_final (
        .i_clk     (i_clk),
        .i_rst_n   (i_rst_n),
        .i_uart_rx (i_uart_rx),
        .o_uart_tx (o_uart_tx_OUT)
    );

endmodule

/* verilator lint_on UNDRIVEN */
/* verilator lint_on UNUSED */
`default_nettype wire
