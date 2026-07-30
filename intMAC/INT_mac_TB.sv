`timescale 1ns / 1ps

module INT_mac_TB;
    // input
    logic clk;
    logic rst_n;
    logic valid;
    logic signed [8:0] a;
    logic signed [8:0] b;

    // output
    logic out_valid;
    logic signed [22:0] result;
    logic overflow;

  
    int_MAC mac_inst (
        .i_clk(clk),
        .i_rst_n(rst_n),
        .i_valid(valid),
        .i_a(a),
        .i_b(b),
        .o_valid(out_valid),
        .o_result(result),
        .o_overflow(overflow)
    );


    initial begin
        $dumpfile("mac.vcd");
        $dumpvars(0, INT_mac_TB);
    end


    initial clk = 0;
    always #5 clk = ~clk; // 100 MHz clock

    //localparam logic [1:0] VALID_SIGNS [0:2] = '{2'b00, 2'b01, 2'b11};

    initial begin
        $display("Time\tValid\tA\tB\tResult\tOut_Valid\tOverflow");
    end

    always @(posedge clk) begin
        $display("%0t\t%b\t%0d\t%0d\t%0d\t%b\t\t%b",
                 $time, valid, a, b, result, out_valid, overflow);
    end

    initial begin
        rst_n <= 0;
        valid <= 0;
        a <= 0;
        b <= 0;

        repeat (2) @(posedge clk);
        rst_n <= 1;

        // Directed test cases
        @(posedge clk) valid <= 1; a <= 9'sd100;  b <= 9'sd50;
        @(posedge clk) valid <= 1; a <= -9'sd100; b <= 9'sd50;
        @(posedge clk) valid <= 1; a <= 9'sd100;  b <= -9'sd100;
        @(posedge clk) valid <= 1; a <= -9'sd100; b <= -9'sd50;
        @(posedge clk) valid <= 1; a <= 9'sd50;   b <= 9'sd50;
        @(posedge clk) valid <= 1; a <= 9'sd50;   b <= 9'sd25;
        @(posedge clk) valid <= 1; a <= -9'sd50;  b <= -9'sd25;

        // Invalid inputs
        @(posedge clk) valid <= 0; a <= 9'sd20; b <= 9'sd30;
        @(posedge clk) valid <= 0; a <= 9'sd10; b <= 9'sd10;
        @(posedge clk) valid <= 0; a <= 9'sd5;  b <= 9'sd15;
        @(posedge clk) valid <= 0; a <= 9'sd0;  b <= 9'sd0;

        // Overflow test
        repeat (66) begin
            @(posedge clk)
            valid <= 1;
            a <= 9'sd255;
            b <= 9'sd255;
        end

        @(posedge clk)
        valid <= 0;
        a <= 0;
        b <= 0;

        // Reset
        @(posedge clk) rst_n <= 0;
        @(posedge clk) rst_n <= 1;

        // Random test cases
	repeat (100) begin
	    @(posedge clk);
	    valid <= 1;
	    a <= $urandom_range(-256,255);
	    b <= $urandom_range(-256,255);
	end

        repeat (4) @(posedge clk);
        $finish;
    end

endmodule
