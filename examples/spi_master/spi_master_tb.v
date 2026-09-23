`timescale 1ns/1ps

module spi_master_tb;

    reg clk;
    reg rst_n;
    reg start;
    reg [7:0] tx_data;
    reg miso;
    wire sclk;
    wire mosi;
    wire cs_n;
    wire [7:0] rx_data;
    wire busy;

    spi_master dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .tx_data(tx_data),
        .miso(miso),
        .sclk(sclk),
        .mosi(mosi),
        .cs_n(cs_n),
        .rx_data(rx_data),
        .busy(busy)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        start = 0;
        tx_data = 8'h00;
        miso = 0;

        #20;
        rst_n = 1;
        #20;

        // Initiate SPI transaction with byte 0xAA
        @(posedge clk);
        tx_data = 8'hAA;
        start = 1;
        miso = 1'b1;
        @(posedge clk);
        start = 0;

        // Run until transaction finishes
        repeat (40) @(posedge clk);

        // Verification check
        if (busy !== 1'b0) begin
            $display("[FAIL] SPI bus still reported busy");
        end else begin
            $display("[PASS] SPI transaction cycle completed. RX data = %h", rx_data);
        end

        #20;
        $finish;
    end

endmodule
