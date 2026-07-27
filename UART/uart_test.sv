`timescale 1ns / 1ps

module uart_test_full;
parameter baudRate = 115200;
parameter clkFreq = 180633650; // 10 times the baud frequency to ensure proper timing
bit clr = 1;                           // global reset input
bit clk = 1;                            // global clock input
bit serIn = 1;                          // serial data input
bit serOut;                         // serial data output
bit [7:0] txData;                   // data byte to transmit
bit newTxData = 1;                      // asserted to indicate new data byte for transmission
bit txBusy;                         // transmitter busy flag
bit [7:0] rxData;                   // data byte received
bit newRxData;                      // asserted to indicate new received data byte
integer baudFreq = 16 * baudRate / gcd(clkFreq, 16 * baudRate);                // baud frequency inputx = ser.read(bytesWaiting)--baudFreq = 16 * baudRate / gcd(clkFreq, 16 * baudRate)--in this baudrate is 9600  gcd_value(25600)
integer baudLimit = clkFreq / gcd(clkFreq, 16 * baudRate);               //baudLimit = clkFreq / gcd(clkFreq, 16 * baudRate) - baudFreq
bit baudClk;                         // baud clock output
// bit clk_100m = 0;

// Loop back serial input and output to easily check tx and rx correctness 
// When loopback is true ser_in will be assigned serOut 
parameter loopback = 1; 

bit ser_In; 
assign ser_In = (loopback) ? serOut : serIn;
uartTopBaseExt dut(
    .clr      (clr),
    .clk      (clk),
    .serIn    (ser_In),
    .serOut   (serOut),
    .txData   (txData),
    .newTxData(newTxData),
    .txBusy   (txBusy),
    .rxData   (rxData),
    .newRxData(newRxData),
    .baudFreq (baudFreq),
    .baudLimit(baudLimit),
    .baudClk  (baudClk)
);

// baud_base_clk main_clk(
//     .clk_out1(clk),
//     .clk_in1(clk_100m)
// );

 
always #(1E9/(2*clkFreq)) clk <= ~clk;

integer i, j;
bit [7:0] send, send_r;
realtime period = 1E9/baudRate;
logic [0:9] sending_data;

realtime drifted_bit_period = period * 1.03; 
realtime drifted_tick_step  = drifted_bit_period / 16.0;

initial #2500 clr = 0;


// Generate Random Serial Input when not using loop back 
initial begin
    for(j = 0; j < 10000; j = j + 1) begin
        send = $random;
        for (int k = 0; k < 8; k = k + 1) begin
            send_r[k] = send[7-k];
        end
        sending_data = {1'b0, send_r, 1'b1};
        foreach (sending_data[i]) begin
            serIn = sending_data[i];
            #(drifted_tick_step * 16);
        end
        repeat(j%6) @(posedge baudClk) ;
    end
     @(posedge baudClk) ;
end



// Generate Random bytes to transmit 
initial begin
    for(i = 0; i < 100; i = i + 1) begin
        txData = $random;
        #(period) ;
        newTxData = 0;
        repeat(10) #(period) ;
        newTxData = 1;
    end
    if (i == 100) #(period) $finish; 
end


// Verify byte sent was received correctly 
logic rx_match;
always @(posedge clk) begin
    if (newRxData) begin
        rx_match <= (rxData == (loopback ? txData : send));
        $display(" Time: %t | Sent Byte: 0x%h | Received byte: 0x%h", $time, (loopback ? txData : send), rxData);
    end
end

// Waveform Dump 
initial begin
    $dumpfile("simulation_waves.vcd"); 
    $dumpvars(0, uart_test_full);      
end


endmodule

function integer gcd(input integer a, b);
    integer g, l, m;
    g = b;
    l = a;
    if(a > b) begin
        g = a;
        l = b;
    end
    do begin
        m = g % l;
        g = l;
        l = m;
    end while(m != 0);
    return g;

endfunction