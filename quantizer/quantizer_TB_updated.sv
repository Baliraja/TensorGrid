`timescale 1ns / 1ps

module quantizer_TB;

    // Clock and reset signals
    logic clk;
    logic rst_n;

    // Input signals
    logic signed [22:0] i_data;
    logic [31:0] i_scale;
    logic [7:0] i_zero_point;
    logic [2:0] i_target_dtype;

    // Output signals
    logic [7:0] o_quantized_data;
    logic o_overflow;

    // Instantiate the quantizer module
    quantizer quantizer_inst (
        .i_clk(clk),
        .i_rst_n(rst_n),
        .i_data(i_data),
        .i_scale(i_scale),
        .i_zero_point(i_zero_point),
        .i_target_dtype(i_target_dtype),
        .o_quantized_data(o_quantized_data),
        .o_overflow(o_overflow)
    );

    // Clock generation
    initial clk <= 0;
    always #5 clk <= ~clk; // 100 MHz clock

    // Testbench procedure
    initial begin
        $dumpfile("dump.vcd");
        $dumpvars(0, quantizer_TB);

        rst_n <= 0;
        i_data <= 23'sd0;
        i_scale <= 32'd0;
        i_zero_point <= 8'd0;
        i_target_dtype <= 3'd0;

        repeat (2) @(posedge clk);
        rst_n <= 1;

        // Normal path: round-to-nearest-even(i_data * i_scale) + i_zero_point, followed by saturation to the target dtype.
        // For a nonzero product with scale exponent > 134, the RTL performs early saturation, asserts overflow, and bypasses i_zero_point.

        // int8 tests, i_target_dtype = 0
        begin i_target_dtype <= 3'd0; i_data <= 23'sd162574; i_scale <= 32'h391C68A3; i_zero_point <= 8'd41; end // case 1: normal positive, expected 65
        @(posedge clk) begin i_data <= 23'sd147; i_scale <= 32'h3E7182C0; i_zero_point <= -8'sd12; end // case 2: negative zero point, expected 23
        @(posedge clk) begin i_data <= -23'sd9; i_scale <= 32'h415AAAAB; i_zero_point <= 8'd108; end // case 3: negative data, expected -15 = 8'hF1
        @(posedge clk) begin i_data <= 23'sd0; i_scale <= 32'h45841234; i_zero_point <= 8'd124; end // case 4: zero data, expected 124
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h45841234; i_zero_point <= 8'd124; end // case 5: large positive overflow, expected 127, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd124; end // case 6: positive overflow, expected 127, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd124; end // case 7: exponent > 134 causes negative early saturation; zero point is bypassed, expected -128 = 8'h80, overflow
        @(posedge clk) begin i_data <= 23'sd127; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 8: exact positive edge, expected 127
        @(posedge clk) begin i_data <= 23'sd128; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 9: one above positive edge, expected 127, overflow
        @(posedge clk) begin i_data <= -23'sd128; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 10: exact negative edge, expected -128 = 8'h80
        @(posedge clk) begin i_data <= -23'sd129; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 11: one below negative edge, expected -128, overflow
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // case 12: +0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // case 13: +1.5 tie, expected 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // case 14: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // case 15: -1.5 tie, expected -2 = 8'hFE


        // uint8 tests, i_target_dtype = 1
        @(posedge clk) begin i_target_dtype <= 3'd1; i_data <= 23'sd0; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 16: exact low edge, expected 0
        @(posedge clk) begin i_data <= 23'sd255; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 17: exact high edge, expected 255
        @(posedge clk) begin i_data <= 23'sd256; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 18: one above high edge, expected 255, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 19: below low edge, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd250; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 20: 250 + 5 = 255, expected 255
        @(posedge clk) begin i_data <= 23'sd251; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 21: 251 + 5 = 256, expected 255, overflow
        @(posedge clk) begin i_data <= -23'sd5; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 22: -5 + 5 = 0, expected 0
        @(posedge clk) begin i_data <= -23'sd6; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 23: -6 + 5 = -1, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 24: 0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 25: 1.5 tie, expected 2
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 26: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 27: -1.5 tie, expected 0, overflow


        // int4 tests, i_target_dtype = 2
        @(posedge clk) begin i_target_dtype <= 3'd2; i_data <= -23'sd8; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 28: exact negative edge, expected -8 = 8'hF8
        @(posedge clk) begin i_data <= -23'sd9; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 29: one below negative edge, expected -8, overflow
        @(posedge clk) begin i_data <= 23'sd7; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 30: exact positive edge, expected 7
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 31: one above positive edge, expected 7, overflow
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F800000; i_zero_point <= 8'd4; end // case 32: 3 + 4 = 7, expected 7
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3F800000; i_zero_point <= 8'd4; end // case 33: 4 + 4 = 8, expected 7, overflow
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F800000; i_zero_point <= -8'sd5; end // case 34: -3 - 5 = -8, expected -8
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3F800000; i_zero_point <= -8'sd5; end // case 35: -4 - 5 = -9, expected -8, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 36: 0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 37: 1.5 tie, expected 2
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 38: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 39: -1.5 tie, expected -2 = 8'hFE


        // uint4 tests, i_target_dtype = 3
        @(posedge clk) begin i_target_dtype <= 3'd3; i_data <= 23'sd0; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 40: exact low edge, expected 0
        @(posedge clk) begin i_data <= 23'sd15; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 41: exact high edge, expected 15 = 8'h0F
        @(posedge clk) begin i_data <= 23'sd16; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 42: one above high edge, expected 15, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 43: below low edge, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd10; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 44: 10 + 5 = 15, expected 15
        @(posedge clk) begin i_data <= 23'sd11; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 45: 11 + 5 = 16, expected 15, overflow
        @(posedge clk) begin i_data <= -23'sd5; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 46: -5 + 5 = 0, expected 0
        @(posedge clk) begin i_data <= -23'sd6; i_scale <= 32'h3F800000; i_zero_point <= 8'd5; end // case 47: -6 + 5 = -1, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 48: 0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 49: 1.5 tie, expected 2
        @(posedge clk) begin i_data <= 23'sd31; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 50: 15.5 tie -> 16, expected 15, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 51: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 52: -1.5 tie, expected 0, overflow


        // int2 tests, i_target_dtype = 4
        @(posedge clk) begin i_target_dtype <= 3'd4; i_data <= -23'sd2; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 53: exact negative edge, expected -2 = 8'hFE
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 54: one below negative edge, expected -2, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 55: exact positive edge, expected 1
        @(posedge clk) begin i_data <= 23'sd2; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 56: one above positive edge, expected 1, overflow
        @(posedge clk) begin i_data <= 23'sd2; i_scale <= 32'h3F800000; i_zero_point <= -8'sd1; end // case 57: 2 - 1 = 1, expected 1
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F800000; i_zero_point <= -8'sd1; end // case 58: 3 - 1 = 2, expected 1, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= -8'sd1; end // case 59: -1 - 1 = -2, expected -2
        @(posedge clk) begin i_data <= -23'sd2; i_scale <= 32'h3F800000; i_zero_point <= -8'sd1; end // case 60: -2 - 1 = -3, expected -2, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 61: 0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 62: 1.5 tie -> 2, expected 1, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 63: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 64: -1.5 tie, expected -2
        @(posedge clk) begin i_data <= -23'sd7; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 65: -3.5 tie -> -4, expected -2, overflow


        // uint2 tests, i_target_dtype = 5
        @(posedge clk) begin i_target_dtype <= 3'd5; i_data <= 23'sd0; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 66: exact low edge, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 67: exact high edge, expected 3
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 68: one above high edge, expected 3, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 69: below low edge, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd2; i_scale <= 32'h3F800000; i_zero_point <= 8'd1; end // case 70: 2 + 1 = 3, expected 3
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F800000; i_zero_point <= 8'd1; end // case 71: 3 + 1 = 4, expected 3, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd1; end // case 72: -1 + 1 = 0, expected 0
        @(posedge clk) begin i_data <= -23'sd2; i_scale <= 32'h3F800000; i_zero_point <= 8'd1; end // case 73: -2 + 1 = -1, expected 0, overflow
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 74: 0.5 tie, expected 0
        @(posedge clk) begin i_data <= 23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 75: 1.5 tie, expected 2
        @(posedge clk) begin i_data <= 23'sd7; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 76: 3.5 tie -> 4, expected 3, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 77: -0.5 tie, expected 0
        @(posedge clk) begin i_data <= -23'sd3; i_scale <= 32'h3F000000; i_zero_point <= 8'd0; end // case 78: -1.5 tie, expected 0, overflow



        // Full rounding-boundary tests for all dtypes
        // int8
        @(posedge clk) begin i_target_dtype <= 3'd0; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int8 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int8 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int8 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int8 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int8 round P1b: = +1.5 -> 2, tie to even
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int8 round P1c: > +1.5 -> 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int8 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int8 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int8 round N0c: < -0.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int8 round N1a: > -1.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int8 round N1b: = -1.5 -> -2 = 8'hFE, tie to even
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int8 round N1c: < -1.5 -> -2 = 8'hFE

        // uint8 
        @(posedge clk) begin i_target_dtype <= 3'd1; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint8 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint8 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint8 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint8 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint8 round P1b: = +1.5 -> 2, tie to even
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint8 round P1c: > +1.5 -> 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint8 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint8 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint8 round N0c: < -0.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint8 round N1a: > -1.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint8 round N1b: = -1.5 -> -2, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint8 round N1c: < -1.5 -> -2, clip to 0, overflow

        // int4 
        @(posedge clk) begin i_target_dtype <= 3'd2; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int4 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int4 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int4 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int4 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int4 round P1b: = +1.5 -> 2, tie to even
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int4 round P1c: > +1.5 -> 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int4 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int4 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int4 round N0c: < -0.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int4 round N1a: > -1.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int4 round N1b: = -1.5 -> -2 = 8'hFE, tie to even
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int4 round N1c: < -1.5 -> -2 = 8'hFE

        // uint4 
        @(posedge clk) begin i_target_dtype <= 3'd3; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint4 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint4 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint4 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint4 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint4 round P1b: = +1.5 -> 2, tie to even
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint4 round P1c: > +1.5 -> 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint4 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint4 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint4 round N0c: < -0.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint4 round N1a: > -1.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint4 round N1b: = -1.5 -> -2, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint4 round N1c: < -1.5 -> -2, clip to 0, overflow

        // int2 
        @(posedge clk) begin i_target_dtype <= 3'd4; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int2 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int2 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int2 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int2 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int2 round P1b: = +1.5 -> 2, clip to 1, overflow
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int2 round P1c: > +1.5 -> 2, clip to 1, overflow
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'sd0; end // int2 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'sd0; end // int2 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'sd0; end // int2 round N0c: < -0.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'sd0; end // int2 round N1a: > -1.5 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'sd0; end // int2 round N1b: = -1.5 -> -2 = 8'hFE, tie to even
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'sd0; end // int2 round N1c: < -1.5 -> -2 = 8'hFE

        // uint2 
        @(posedge clk) begin i_target_dtype <= 3'd5; i_data <= 23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint2 round P0a: < +0.5 -> 0
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint2 round P0b: = +0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= 23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint2 round P0c: > +0.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint2 round P1a: < +1.5 -> 1
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint2 round P1b: = +1.5 -> 2, tie to even
        @(posedge clk) begin i_data <= 23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint2 round P1c: > +1.5 -> 2
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D7FFFFF; i_zero_point <= 8'd0; end // uint2 round N0a: > -0.5 -> 0
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800000; i_zero_point <= 8'd0; end // uint2 round N0b: = -0.5 -> 0, tie to even
        @(posedge clk) begin i_data <= -23'sd8; i_scale <= 32'h3D800001; i_zero_point <= 8'd0; end // uint2 round N0c: < -0.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EBFFFFF; i_zero_point <= 8'd0; end // uint2 round N1a: > -1.5 -> -1, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00000; i_zero_point <= 8'd0; end // uint2 round N1b: = -1.5 -> -2, clip to 0, overflow
        @(posedge clk) begin i_data <= -23'sd4; i_scale <= 32'h3EC00001; i_zero_point <= 8'd0; end // uint2 round N1c: < -1.5 -> -2, clip to 0, overflow



        // Shift tests
        @(posedge clk) begin i_target_dtype <= 3'd1; i_data <= 23'sd4194303; i_scale <= 32'h32FFFFFF; i_zero_point <= 8'd44; end // case 79: shifts=101, below supported shift range, expected 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd44; end // case 80: shifts=102, smallest supported shift, product still rounds to 0, expected 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd44; end // case 81: shifts=104 with large mantissa, product rounds to 1, expected 45
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34800000; i_zero_point <= 8'd44; end // case 82: shifts=105, scale=2^-22, product rounds to 1, expected 45
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F000000; i_zero_point <= 8'd44; end // case 83: shifts=126, scale=0.5, tie rounds to 0, expected 44
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd44; end // case 84: shifts=127, scale=1.0, expected 45
        @(posedge clk) begin i_data <= 23'sd64; i_scale <= 32'h40000000; i_zero_point <= 8'd44; end // case 85: shifts=128, scale=2.0, 64*2+44=172, expected 172
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h43000000; i_zero_point <= 8'd0; end // case 86: shifts=134, largest normal shift, 1*128=128, expected 128, no overflow for uint8
        @(posedge clk) begin i_data <= 23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd44; end // case 87: shifts=135, above normal range, expected 255, overflow; zero point is bypassed on overflow_1
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd44; end // case 88: shifts=135 negative, expected 0, overflow for uint8

        @(posedge clk) begin i_target_dtype <= 3'd0; i_data <= 23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd44; end // case 89: shifts=135 positive, expected 127, overflow for int8
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h43800000; i_zero_point <= 8'd44; end // case 90: shifts=135 negative, expected -128 = 8'h80, overflow for int8



        // Small-scale shift sweep
        

        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd0; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd44; end // sweep P1: 128 + 44 = 172 -> 127, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd44; end // sweep P2: 64 + 44 = 108
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd44; end // sweep P3: 32 + 44 = 76
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd44; end // sweep P4: 16 + 44 = 60
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd44; end // sweep P5: 8 + 44 = 52
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd44; end // sweep P6: 4 + 44 = 48
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd44; end // sweep P7: 2 + 44 = 46
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd44; end // sweep P8: 1 + 44 = 45
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd44; end // sweep P9: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd44; end // sweep P10: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h32FFFFFF; i_zero_point <= 8'd44; end // sweep P11: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h327FFFFF; i_zero_point <= 8'd44; end // sweep P12: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h31FFFFFF; i_zero_point <= 8'd44; end // sweep P13: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h317FFFFF; i_zero_point <= 8'd44; end // sweep P14: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h30FFFFFF; i_zero_point <= 8'd44; end // sweep P15: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h307FFFFF; i_zero_point <= 8'd44; end // sweep P16: 0 + 44 = 44

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd44; end // sweep N1: -128 + 44 = -84 = 8'hAC
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd44; end // sweep N2: -64 + 44 = -20 = 8'hEC
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd44; end // sweep N3: -32 + 44 = 12
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd44; end // sweep N4: -16 + 44 = 28
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd44; end // sweep N5: -8 + 44 = 36
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd44; end // sweep N6: -4 + 44 = 40
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd44; end // sweep N7: -2 + 44 = 42
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd44; end // sweep N8: -1 + 44 = 43
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd44; end // sweep N9: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd44; end // sweep N10: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h32FFFFFF; i_zero_point <= 8'd44; end // sweep N11: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h327FFFFF; i_zero_point <= 8'd44; end // sweep N12: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h31FFFFFF; i_zero_point <= 8'd44; end // sweep N13: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h317FFFFF; i_zero_point <= 8'd44; end // sweep N14: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h30FFFFFF; i_zero_point <= 8'd44; end // sweep N15: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h307FFFFF; i_zero_point <= 8'd44; end // sweep N16: 0 + 44 = 44



        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd1; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep P1: 128 + 44 = 172
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd44; end // uint8 sweep P2: 64 + 44 = 108
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep P3: 32 + 44 = 76
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd44; end // uint8 sweep P4: 16 + 44 = 60
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep P5: 8 + 44 = 52
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd44; end // uint8 sweep P6: 4 + 44 = 48
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep P7: 2 + 44 = 46
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd44; end // uint8 sweep P8: 1 + 44 = 45
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep P9: 0 + 44 = 44
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd44; end // uint8 sweep P10: 0 + 44 = 44

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep N1: -128 + 44 = -84 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd44; end // uint8 sweep N2: -64 + 44 = -20 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep N3: -32 + 44 = 12
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd44; end // uint8 sweep N4: -16 + 44 = 28
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep N5: -8 + 44 = 36
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd44; end // uint8 sweep N6: -4 + 44 = 40
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep N7: -2 + 44 = 42
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd44; end // uint8 sweep N8: -1 + 44 = 43
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd44; end // uint8 sweep N9: 0 + 44 = 44
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd44; end // uint8 sweep N10: 0 + 44 = 44

      

        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd2; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd4; end // int4 sweep P1: 128 + 4 = 132 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd4; end // int4 sweep P2: 64 + 4 = 68 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd4; end // int4 sweep P3: 32 + 4 = 36 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd4; end // int4 sweep P4: 16 + 4 = 20 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd4; end // int4 sweep P5: 8 + 4 = 12 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd4; end // int4 sweep P6: 4 + 4 = 8 -> 7, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd4; end // int4 sweep P7: 2 + 4 = 6
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd4; end // int4 sweep P8: 1 + 4 = 5
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd4; end // int4 sweep P9: 0 + 4 = 4
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd4; end // int4 sweep P10: 0 + 4 = 4

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd4; end // int4 sweep N1: -128 + 4 = -124 -> -8 = 8'hF8, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd4; end // int4 sweep N2: -64 + 4 = -60 -> -8 = 8'hF8, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd4; end // int4 sweep N3: -32 + 4 = -28 -> -8 = 8'hF8, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd4; end // int4 sweep N4: -16 + 4 = -12 -> -8 = 8'hF8, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd4; end // int4 sweep N5: -8 + 4 = -4 = 8'hFC
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd4; end // int4 sweep N6: -4 + 4 = 0
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd4; end // int4 sweep N7: -2 + 4 = 2
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd4; end // int4 sweep N8: -1 + 4 = 3
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd4; end // int4 sweep N9: 0 + 4 = 4
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd4; end // int4 sweep N10: 0 + 4 = 4



        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd3; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep P1: 128 + 4 = 132 -> 15, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd4; end // uint4 sweep P2: 64 + 4 = 68 -> 15, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep P3: 32 + 4 = 36 -> 15, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd4; end // uint4 sweep P4: 16 + 4 = 20 -> 15, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep P5: 8 + 4 = 12
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd4; end // uint4 sweep P6: 4 + 4 = 8
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep P7: 2 + 4 = 6
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd4; end // uint4 sweep P8: 1 + 4 = 5
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep P9: 0 + 4 = 4
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd4; end // uint4 sweep P10: 0 + 4 = 4

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep N1: -128 + 4 = -124 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd4; end // uint4 sweep N2: -64 + 4 = -60 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep N3: -32 + 4 = -28 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd4; end // uint4 sweep N4: -16 + 4 = -12 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep N5: -8 + 4 = -4 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd4; end // uint4 sweep N6: -4 + 4 = 0
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep N7: -2 + 4 = 2
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd4; end // uint4 sweep N8: -1 + 4 = 3
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd4; end // uint4 sweep N9: 0 + 4 = 4
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd4; end // uint4 sweep N10: 0 + 4 = 4



        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd4; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd0; end // int2 sweep P1: 128 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd0; end // int2 sweep P2: 64 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd0; end // int2 sweep P3: 32 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd0; end // int2 sweep P4: 16 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd0; end // int2 sweep P5: 8 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd0; end // int2 sweep P6: 4 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd0; end // int2 sweep P7: 2 -> 1, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd0; end // int2 sweep P8: 1 -> 1
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd0; end // int2 sweep P9: 0 -> 0
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd0; end // int2 sweep P10: 0 -> 0

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd0; end // int2 sweep N1: -128 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd0; end // int2 sweep N2: -64 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd0; end // int2 sweep N3: -32 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd0; end // int2 sweep N4: -16 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd0; end // int2 sweep N5: -8 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd0; end // int2 sweep N6: -4 -> -2 = 8'hFE, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd0; end // int2 sweep N7: -2 -> -2 = 8'hFE
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd0; end // int2 sweep N8: -1 -> -1 = 8'hFF
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd0; end // int2 sweep N9: 0 -> 0
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd0; end // int2 sweep N10: 0 -> 0



        // Positive sweep
        @(posedge clk) begin i_target_dtype <= 3'd5; i_data <= 23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep P1: 128 + 1 = 129 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd1; end // uint2 sweep P2: 64 + 1 = 65 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep P3: 32 + 1 = 33 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd1; end // uint2 sweep P4: 16 + 1 = 17 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep P5: 8 + 1 = 9 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd1; end // uint2 sweep P6: 4 + 1 = 5 -> 3, overflow
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep P7: 2 + 1 = 3
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd1; end // uint2 sweep P8: 1 + 1 = 2
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep P9: 0 + 1 = 1
        @(posedge clk) begin i_data <= 23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd1; end // uint2 sweep P10: 0 + 1 = 1

        // Negative sweep
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h37FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep N1: -128 + 1 = -127 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h377FFFFF; i_zero_point <= 8'd1; end // uint2 sweep N2: -64 + 1 = -63 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h36FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep N3: -32 + 1 = -31 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h367FFFFF; i_zero_point <= 8'd1; end // uint2 sweep N4: -16 + 1 = -15 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h35FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep N5: -8 + 1 = -7 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h357FFFFF; i_zero_point <= 8'd1; end // uint2 sweep N6: -4 + 1 = -3 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h34FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep N7: -2 + 1 = -1 -> 0, overflow
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h347FFFFF; i_zero_point <= 8'd1; end // uint2 sweep N8: -1 + 1 = 0
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h33FFFFFF; i_zero_point <= 8'd1; end // uint2 sweep N9: 0 + 1 = 1
        @(posedge clk) begin i_data <= -23'sd4194303; i_scale <= 32'h337FFFFF; i_zero_point <= 8'd1; end // uint2 sweep N10: 0 + 1 = 1

     
        // 6 should behave like int8, 7 should behave like uint8
        @(posedge clk) begin i_target_dtype <= 3'd6; i_data <= 23'sd127; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 91: dtype 6 behaves like int8, expected 127
        @(posedge clk) begin i_data <= 23'sd128; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 92: dtype 6 positive saturation, expected 127, overflow
        @(posedge clk) begin i_data <= -23'sd128; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 93: dtype 6 negative edge, expected -128 = 8'h80
        @(posedge clk) begin i_data <= -23'sd129; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 94: dtype 6 negative saturation, expected -128, overflow

        @(posedge clk) begin i_target_dtype <= 3'd7; i_data <= 23'sd255; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 95: dtype 7 behaves like uint8, expected 255
        @(posedge clk) begin i_data <= 23'sd256; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 96: dtype 7 positive saturation, expected 255, overflow
        @(posedge clk) begin i_data <= -23'sd1; i_scale <= 32'h3F800000; i_zero_point <= 8'd0; end // case 97: dtype 7 negative saturation, expected 0, overflow

        @(posedge clk); i_data <= 23'sd0; i_scale <= 32'd0; i_zero_point <= 8'd0; i_target_dtype <= 3'd0;

        repeat (3) @(posedge clk);
        #1;
        $finish;
    end

endmodule
