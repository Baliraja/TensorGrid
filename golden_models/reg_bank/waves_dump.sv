`timescale 1ns / 1ps

module waves_dump();
    initial begin
        $dumpfile("reg_bank_waves.fst");
        $dumpvars(0, reg_bank);
    end
endmodule
