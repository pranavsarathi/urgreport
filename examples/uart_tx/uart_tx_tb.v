`timescale 1ns/1ps

module uart_tx_tb;

    reg clk;
    reg rst_n;
    reg tx_start;
    reg [7:0] tx_data;
    wire tx_out;
    wire tx_busy;
    wire tx_done;

    uart_tx #(.CLKS_PER_BIT(4)) dut (
        .clk(clk),
        .rst_n(rst_n),
        .tx_start(tx_start),
        .tx_data(tx_data),
        .tx_out(tx_out),
        .tx_busy(tx_busy),
        .tx_done(tx_done)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        tx_start = 0;
        tx_data = 8'h00;

        #20;
        rst_n = 1;
        #20;

        // Send byte 0x55
        @(posedge clk);
        tx_data = 8'h55;
        tx_start = 1;
        @(posedge clk);
        tx_start = 0;

        // Wait for transmission to complete
        repeat (50) @(posedge clk);

        // Verification check on tx_done
        if (tx_done !== 1'b1) begin
            $display("[FAIL] tx_done flag not asserted at end of transmission");
        end else begin
            $display("[PASS] UART byte transmitted successfully");
        end

        #20;
        $finish;
    end

endmodule
