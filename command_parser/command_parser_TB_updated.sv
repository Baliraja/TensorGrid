`timescale 1ns / 1ps

module command_parser_TB;
    // Clock and reset signals
    logic clk;
    logic rst_n;

    // Input signals
    logic [7:0] uart_rx_data;
    logic uart_rx_new;

    // Output signals
    logic [7:0] uart_tx_data;
    logic uart_tx_new;

    // Interface to registers
    logic matrix_config;
    logic matrix_signed;
    logic data_load;
    logic data_read;
    logic shift_row;
    logic shift_col;
    logic arithmetic_op;
    logic [1:0] arithmetic_op_type;
    logic quantization_op;
    logic relu_op;
    logic clamp_op;
    logic [7:0] clamp_max;
    logic [1:0] matrix_1;
    logic [1:0] matrix_2;
    logic [1:0] matrix_rows;
    logic [1:0] matrix_cols;
    logic [7:0] data_out;
    logic [7:0] data_in;
    logic [31:0] quantizer_scale;
    logic [7:0] quantizer_zero_point;
    logic [2:0] quantizer_target_dtype;

    // Instantiate the command_parser module
    command_parser parser_inst (
        .i_clk(clk),
        .i_rst_n(rst_n),
        .i_uart_rx_data(uart_rx_data),
        .i_uart_rx_new(uart_rx_new),
        .o_uart_tx_data(uart_tx_data),
        .o_uart_tx_new(uart_tx_new),
        .o_matrix_config(matrix_config),
        .o_matrix_signed(matrix_signed),
        .o_data_load(data_load),
        .o_data_read(data_read),
        .o_shift_row(shift_row),
        .o_shift_col(shift_col),
        .o_arithmetic_op(arithmetic_op),
        .o_arithmetic_op_type(arithmetic_op_type),
        .o_quantization_op(quantization_op),
        .o_relu_op(relu_op),
        .o_clamp_op(clamp_op),
        .o_clamp_max(clamp_max),
        .o_matrix_1(matrix_1),
        .o_matrix_2(matrix_2),
        .o_matrix_rows(matrix_rows),
        .o_matrix_cols(matrix_cols),
        .o_data(data_out),
        .i_data_rd(data_in),
        .i_idle(1'b0),
        .o_quantizer_scale(quantizer_scale),
        .o_quantizer_zero_point(quantizer_zero_point),
        .o_quantizer_target_dtype(quantizer_target_dtype)
    );

    task send_byte(input logic [7:0] tx_byte);
        begin
            uart_rx_data <= tx_byte;
            uart_rx_new <= 1'b1;
            @(posedge clk);
            uart_rx_new <= 1'b0;
            repeat (10) @(posedge clk); // Wait for a few clock cycles before sending the next byte
        end
    endtask

    // Clock generation
    initial clk <= 0;
    always #5 clk <= ~clk; // 100MHz clock

    // Testbench procedure
    logic [55:0] command;

    initial begin
    
    	$dumpfile("cp_sim.vcd");
        $dumpvars(0, command_parser_TB);
        
        rst_n <= 0;
        uart_rx_data <= 8'd0;
        uart_rx_new <= 1'b0;
        data_in <= 8'd0;
        // Wait for a few clock cycles
        repeat (5) @(posedge clk);
        rst_n <= 1;
        // Wait for a few clock cycles after reset
        repeat (5) @(posedge clk);
        // QUANTIZE command test
        // Syntax: 4'b0001, 2'b (destination matrix), 2'b (unused), 3'b(datatype), 5'b(unused), 8'b(zero_point), 32'b(scale)
        // datatypes: 0, 6: int8, 1, 7: uint8, 2: int4, 3: uint4, 4: int2, 5: uint2
        command[55:52] = 4'b0001; // QUANTIZE command
        command[51:50] = $urandom_range(0, 3); // Random destination matrix
        command[49:48] = 2'b00; // Unused
        command[47:45] = $urandom_range(0, 7); // Random datatype
        command[44:40] = 5'b00000; // Unused
        command[31] = 1'b0; // Sign bit for scale
        command[30:23] = $urandom_range(0, 254); // Random exponent for scale
        command[22:0] = $urandom_range(0, 2**23 - 1); // Random mantissa for scale
        command[39:32] = $urandom_range(0, 255); // Random zero point
        // Send the command bytes
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // LOAD_ELEMENT command test
        // Syntax: 4'h2, 2'b (destination matrix), 2'b (unused), 4'b (row), 4'b (col), 8'b (data)
        command = 56'd0;
        command[23:20] = 4'h2; // LOAD_ELEMENT command
        command[19:18] = $urandom_range(0, 3); // Random destination matrix
        command[17:16] = 2'b00; // Unused
        command[15:12] = $urandom_range(0, 3); // Random row
        command[11:8] = $urandom_range(0, 3); // Random column
        command[7:0] = $urandom_range(0, 255); // Random data
        // Send the command bytes
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // READ_ELEMENT command test
        // Syntax: 4'h3, 2'b (source matrix), 2'b (unused), 4'b (row), 4'b (col)
        command = 56'd0;
        command[15:12] = 4'h3; // READ_ELEMENT command
        command[11:10] = $urandom_range(0, 3); // Random source matrix
        command[9:8] = 2'b00; // Unused
        command[7:4] = $urandom_range(0, 3); // Random row
        command[3:0] = $urandom_range(0, 3); // Random column
        // Send the command bytes
        send_byte(command[15 -: 8]);
        fork
            send_byte(command[7 -: 8]);
            begin
                repeat (2) @(posedge clk); // Wait for a few clock cycles before sending the next byte
                data_in <= $urandom_range(0, 255); // Random data to be read
            end
        join
        // ADD command test
        // Syntax: 4'h4, 2'b (source matrix 1), 2'b (source matrix 2)
        command = 56'd0;
        command[7:4] = 4'h4; // ADD command
        command[3:2] = $urandom_range(0, 3); // Random source matrix 1
        command[1:0] = $urandom_range(0, 3); // Random source matrix 2
        // Send the command bytes
        for (int i = 7; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // EL_MUL command test
        // Syntax: 4'h5, 2'b (source matrix 1), 2'b (source matrix 2)
        command = 56'd0;
        command[7:4] = 4'h5; // EL_MUL command
        command[3:2] = $urandom_range(0, 3); // Random source matrix 1
        command[1:0] = $urandom_range(0, 3); // Random source matrix 2
        // Send the command bytes
        for (int i = 7; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // MAT_MUL command test
        // Syntax: 4'h7, 2'b (source matrix 1), 2'b (source matrix 2)
        command = 56'd0;
        command[7:4] = 4'h7; // MAT_MUL command
        command[3:2] = $urandom_range(0, 3); // Random source matrix 1
        command[1:0] = $urandom_range(0, 3); // Random source matrix 2
        // Send the command bytes
        for (int i = 7; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // DOT_PROD command test
        // Syntax: 4'h6, 2'b (source matrix 1), 2'b (source matrix 2), 4'b (destination row), 4'b (destination col)
        command = 56'd0;
        command[15:12] = 4'h6; // DOT_PROD command
        command[11:10] = $urandom_range(0, 3); // Random source matrix 1
        command[9:8] = $urandom_range(0, 3); // Random source matrix 2
        command[7:4] = $urandom_range(0, 3); // Random destination row
        command[3:0] = $urandom_range(0, 3); // Random destination column
        // Send the command bytes
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // CLEAR_MATRIX command test
        // Syntax: 4'h8, 2'b (matrix to clear), 1'b (signed/unsigned), 1'b (unused)
        command = 56'd0;
        command[7:4] = 4'h8; // CLEAR_MATRIX command
        command[3:2] = $urandom_range(0, 3); // Random matrix to clear
        command[1] = $urandom_range(0, 1); // Random signed/unsigned
        command[0] = 1'b0; // Unused
        // Send the command bytes
        for (int i = 7; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // RELU command test
        // Syntax: 4'h9, 2'b (matrix to apply RELU), 2'b (unused)
        command = 56'd0;
        command[7:4] = 4'h9; // RELU command
        command[3:2] = $urandom_range(0, 3); // Random matrix to apply RELU
        command[1:0] = 2'b00; // Unused
        // Send the command bytes
        for (int i = 7; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // CLAMP command test
        // Syntax: 4'hA, 2'b (matrix to apply CLAMP), 2'b (unused), 8'b (max value)
        command = 56'd0;
        command[15:12] = 4'hA; // CLAMP command
        command[11:10] = $urandom_range(0, 3); // Random matrix to apply CLAMP
        command[9:8] = 2'b00; // Unused
        command[7:0] = $urandom_range(0, 255); // Random max value
        // Send the command bytes
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
        // SHIFT_ROW_COL command test
        // Syntax: 4'hB, 2'b (matrix to shift), 2'b (unused), 4'b (shifts), 1'b (direction: 1 for row, 0 for column), 3'b (unused)
        command = 56'd0;
        command[15:12] = 4'hB; // SHIFT_ROW_COL command
        command[11:10] = $urandom_range(0, 3); // Random matrix to shift
        command[9:8] = 2'b00; // Unused
        command[7:4] = $urandom_range(0, 3); // Random shifts
        command[3] = $urandom_range(0, 1); // Random direction
        command[2:0] = 3'b000; // Unused
        // Send the command bytes
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
        

        // ADDITIONAL QUANTIZE CORNER CASES

        // QUANTIZE minimum-value test
        // Tests matrix 0, datatype 0, zero point 0, and scale 0x00000000
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd0;
        command[49:48] = 2'b00;
        command[47:45] = 3'd0;
        command[44:40] = 5'b00000;
        command[39:32] = 8'h00;
        command[31:0] = 32'h00000000;
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // QUANTIZE maximum raw-value test
        // Tests matrix 3, datatype 7, zero point 255, and scale 0xFFFFFFFF
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd3;
        command[49:48] = 2'b00;
        command[47:45] = 3'd7;
        command[44:40] = 5'b00000;
        command[39:32] = 8'hFF;
        command[31:0] = 32'hFFFFFFFF;
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // QUANTIZE all datatype encodings
        // Uses scale 1.0 (0x3F800000) and rotates through all four matrices
        for (int dtype = 0; dtype < 8; dtype++) begin
            command = 56'd0;
            command[55:52] = 4'h1;
            command[51:50] = dtype % 4;
            command[49:48] = 2'b00;
            command[47:45] = dtype;
            command[44:40] = 5'b00000;
            command[39:32] = 8'h80;
            command[31:0] = 32'h3F800000;
            for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);
        end

        // QUANTIZE negative-scale bit-pattern test
        // -1.0 in IEEE-754 single precision is 0xBF800000
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd2;
        command[49:48] = 2'b00;
        command[47:45] = 3'd0;
        command[44:40] = 5'b00000;
        command[39:32] = 8'h80;
        command[31:0] = 32'hBF800000;
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // QUANTIZE byte-order test
        // Each scale byte is different so byte ordering is easy to inspect in GTKWave
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd3;
        command[49:48] = 2'b00;
        command[47:45] = 3'd6;
        command[44:40] = 5'b00000;
        command[39:32] = 8'hA6;
        command[31:0] = 32'h12345678;
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // QUANTIZE reserved-bit test
        // All unused bits are set to 1; the meaningful fields should still parse normally
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd1;
        command[49:48] = 2'b11;
        command[47:45] = 3'd4;
        command[44:40] = 5'b11111;
        command[39:32] = 8'h55;
        command[31:0] = 32'h3F000000;
        for (int i = 55; i >= 0; i -= 8) send_byte(command[i -: 8]);


        // ADDITIONAL LOAD_ELEMENT CORNER CASES

        // LOAD_ELEMENT minimum address and minimum data
        command = 56'd0;
        command[23:20] = 4'h2;
        command[19:18] = 2'd0;
        command[17:16] = 2'b00;
        command[15:12] = 4'd0;
        command[11:8] = 4'd0;
        command[7:0] = 8'h00;
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // LOAD_ELEMENT maximum valid address and maximum data
        command = 56'd0;
        command[23:20] = 4'h2;
        command[19:18] = 2'd3;
        command[17:16] = 2'b00;
        command[15:12] = 4'd3;
        command[11:8] = 4'd3;
        command[7:0] = 8'hFF;
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // LOAD_ELEMENT repeated-address test, first value
        command = 56'd0;
        command[23:20] = 4'h2;
        command[19:18] = 2'd1;
        command[17:16] = 2'b00;
        command[15:12] = 4'd2;
        command[11:8] = 4'd2;
        command[7:0] = 8'hAA;
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // LOAD_ELEMENT repeated-address test, replacement value
        command = 56'd0;
        command[23:20] = 4'h2;
        command[19:18] = 2'd1;
        command[17:16] = 2'b00;
        command[15:12] = 4'd2;
        command[11:8] = 4'd2;
        command[7:0] = 8'h55;
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);

        // LOAD_ELEMENT reserved-bit test
        command = 56'd0;
        command[23:20] = 4'h2;
        command[19:18] = 2'd2;
        command[17:16] = 2'b11;
        command[15:12] = 4'd1;
        command[11:8] = 4'd3;
        command[7:0] = 8'hA5;
        for (int i = 23; i >= 0; i -= 8) send_byte(command[i -: 8]);


        // ADDITIONAL READ_ELEMENT CORNER CASES

        // READ_ELEMENT minimum address with returned data 0x00
        command = 56'd0;
        command[15:12] = 4'h3;
        command[11:10] = 2'd0;
        command[9:8] = 2'b00;
        command[7:4] = 4'd0;
        command[3:0] = 4'd0;
        send_byte(command[15 -: 8]);
        fork
            send_byte(command[7 -: 8]);
            begin
                repeat (2) @(posedge clk);
                data_in <= 8'h00;
            end
        join

        // READ_ELEMENT maximum valid address with returned data 0xFF
        command = 56'd0;
        command[15:12] = 4'h3;
        command[11:10] = 2'd3;
        command[9:8] = 2'b00;
        command[7:4] = 4'd3;
        command[3:0] = 4'd3;
        send_byte(command[15 -: 8]);
        fork
            send_byte(command[7 -: 8]);
            begin
                repeat (2) @(posedge clk);
                data_in <= 8'hFF;
            end
        join

        // READ_ELEMENT reserved-bit test
        command = 56'd0;
        command[15:12] = 4'h3;
        command[11:10] = 2'd2;
        command[9:8] = 2'b11;
        command[7:4] = 4'd1;
        command[3:0] = 4'd2;
        send_byte(command[15 -: 8]);
        fork
            send_byte(command[7 -: 8]);
            begin
                repeat (2) @(posedge clk);
                data_in <= 8'h5A;
            end
        join


        // EXHAUSTIVE SOURCE-MATRIX TESTS FOR ONE-BYTE ARITHMETIC COMMANDS

        // ADD: test every possible pair of source matrices
        for (int source_1 = 0; source_1 < 4; source_1++) begin
            for (int source_2 = 0; source_2 < 4; source_2++) begin
                command = 56'd0;
                command[7:4] = 4'h4;
                command[3:2] = source_1;
                command[1:0] = source_2;
                send_byte(command[7:0]);
            end
        end

        // EL_MUL: test every possible pair of source matrices
        for (int source_1 = 0; source_1 < 4; source_1++) begin
            for (int source_2 = 0; source_2 < 4; source_2++) begin
                command = 56'd0;
                command[7:4] = 4'h5;
                command[3:2] = source_1;
                command[1:0] = source_2;
                send_byte(command[7:0]);
            end
        end

        // MAT_MUL: test every possible pair of source matrices
        for (int source_1 = 0; source_1 < 4; source_1++) begin
            for (int source_2 = 0; source_2 < 4; source_2++) begin
                command = 56'd0;
                command[7:4] = 4'h7;
                command[3:2] = source_1;
                command[1:0] = source_2;
                send_byte(command[7:0]);
            end
        end


        // ADDITIONAL DOT_PROD CORNER CASES

        // DOT_PROD: test every source-matrix pair at destination [0,0]
        for (int source_1 = 0; source_1 < 4; source_1++) begin
            for (int source_2 = 0; source_2 < 4; source_2++) begin
                command = 56'd0;
                command[15:12] = 4'h6;
                command[11:10] = source_1;
                command[9:8] = source_2;
                command[7:4] = 4'd0;
                command[3:0] = 4'd0;
                for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
            end
        end

        // DOT_PROD maximum destination row and column
        command = 56'd0;
        command[15:12] = 4'h6;
        command[11:10] = 2'd3;
        command[9:8] = 2'd0;
        command[7:4] = 4'd3;
        command[3:0] = 4'd3;
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);


        // EXHAUSTIVE CLEAR_MATRIX AND RELU MATRIX-SELECTION TESTS

        // CLEAR_MATRIX: test all four matrices as unsigned and signed
        for (int matrix_number = 0; matrix_number < 4; matrix_number++) begin
            for (int signed_mode = 0; signed_mode < 2; signed_mode++) begin
                command = 56'd0;
                command[7:4] = 4'h8;
                command[3:2] = matrix_number;
                command[1] = signed_mode;
                command[0] = 1'b0;
                send_byte(command[7:0]);
            end
        end

        // RELU: test all four matrices
        for (int matrix_number = 0; matrix_number < 4; matrix_number++) begin
            command = 56'd0;
            command[7:4] = 4'h9;
            command[3:2] = matrix_number;
            command[1:0] = 2'b00;
            send_byte(command[7:0]);
        end

        // RELU reserved-bit test
        command = 56'd0;
        command[7:4] = 4'h9;
        command[3:2] = 2'd2;
        command[1:0] = 2'b11;
        send_byte(command[7:0]);


        // ADDITIONAL CLAMP CORNER CASES

        // CLAMP: test minimum and maximum clamp values on every matrix
        for (int matrix_number = 0; matrix_number < 4; matrix_number++) begin
            command = 56'd0;
            command[15:12] = 4'hA;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:0] = 8'h00;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);

            command = 56'd0;
            command[15:12] = 4'hA;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:0] = 8'hFF;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
        end

        // CLAMP reserved-bit test
        command = 56'd0;
        command[15:12] = 4'hA;
        command[11:10] = 2'd1;
        command[9:8] = 2'b11;
        command[7:0] = 8'h7F;
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);


        // ADDITIONAL SHIFT_ROW_COL CORNER CASES

        // SHIFT_ROW_COL: test both directions and shift counts 0 and 3 on every matrix
        for (int matrix_number = 0; matrix_number < 4; matrix_number++) begin
            // Column shift by 0
            command = 56'd0;
            command[15:12] = 4'hB;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:4] = 4'd0;
            command[3] = 1'b0;
            command[2:0] = 3'b000;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);

            // Column shift by 3
            command = 56'd0;
            command[15:12] = 4'hB;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:4] = 4'd3;
            command[3] = 1'b0;
            command[2:0] = 3'b000;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);

            // Row shift by 0
            command = 56'd0;
            command[15:12] = 4'hB;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:4] = 4'd0;
            command[3] = 1'b1;
            command[2:0] = 3'b000;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);

            // Row shift by 3
            command = 56'd0;
            command[15:12] = 4'hB;
            command[11:10] = matrix_number;
            command[9:8] = 2'b00;
            command[7:4] = 4'd3;
            command[3] = 1'b1;
            command[2:0] = 3'b000;
            for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);
        end

        // SHIFT_ROW_COL reserved-bit test
        command = 56'd0;
        command[15:12] = 4'hB;
        command[11:10] = 2'd2;
        command[9:8] = 2'b11;
        command[7:4] = 4'd2;
        command[3] = 1'b1;
        command[2:0] = 3'b111;
        for (int i = 15; i >= 0; i -= 8) send_byte(command[i -: 8]);


        // INVALID OPCODE TESTS

        // Send opcode 0 and undefined opcodes C through F
        // These should not start any supported parser operation
        command = 56'd0;
        command[7:0] = 8'h00;
        send_byte(command[7:0]);

        command[7:0] = 8'hC0;
        send_byte(command[7:0]);

        command[7:0] = 8'hD5;
        send_byte(command[7:0]);

        command[7:0] = 8'hEA;
        send_byte(command[7:0]);

        command[7:0] = 8'hFF;
        send_byte(command[7:0]);


        // RESET DURING A PARTIAL MULTI-BYTE COMMAND

        // Start a QUANTIZE command, reset before all seven bytes arrive,
        // and then send a valid ADD command to test parser recovery
        command = 56'd0;
        command[55:52] = 4'h1;
        command[51:50] = 2'd1;
        command[49:48] = 2'b00;
        command[47:45] = 3'd2;
        command[44:40] = 5'b00000;
        command[39:32] = 8'h20;
        command[31:0] = 32'h3F800000;
        send_byte(command[55 -: 8]);
        send_byte(command[47 -: 8]);
        send_byte(command[39 -: 8]);

        rst_n <= 1'b0;
        repeat (3) @(posedge clk);
        rst_n <= 1'b1;
        repeat (3) @(posedge clk);

        // Valid command after reset recovery
        command = 56'd0;
        command[7:4] = 4'h4;
        command[3:2] = 2'd0;
        command[1:0] = 2'd3;
        send_byte(command[7:0]);


        // UART DATA CHANGES WHILE uart_rx_new IS LOW

        // No new command is indicated during these data-bus changes.
        // Command-trigger outputs should not pulse merely because the data changes.
        uart_rx_new <= 1'b0;
        uart_rx_data <= 8'hFF;
        repeat (3) @(posedge clk);
        uart_rx_data <= 8'h00;
        repeat (3) @(posedge clk);

        // Finish simulation after some time
        repeat(10) @(posedge clk);
        $finish;
    end

endmodule
