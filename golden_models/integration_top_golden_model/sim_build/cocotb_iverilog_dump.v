module cocotb_iverilog_dump();
initial begin
    $dumpfile("sim_build/integration_final.fst");
    $dumpvars(0, integration_final);
end
endmodule
