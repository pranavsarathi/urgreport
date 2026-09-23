`timescale 1ns/1ps

module fifo_sync_tb;

    reg clk;
    reg rst_n;
    reg wr_en;
    reg rd_en;
    reg [7:0] data_in;
    wire [7:0] data_out;
    wire full;
    wire empty;
    wire [3:0] fifo_count;

    // Instantiate DUT
    fifo_sync dut (
        .clk(clk),
        .rst_n(rst_n),
        .wr_en(wr_en),
        .rd_en(rd_en),
        .data_in(data_in),
        .data_out(data_out),
        .full(full),
        .empty(empty),
        .fifo_count(fifo_count)
    );

    // Clock generator (100MHz)
    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        wr_en = 0;
        rd_en = 0;
        data_in = 8'h00;

        // Reset pulse
        #20;
        rst_n = 1;
        #10;

        // Write 3 elements (does NOT reach full boundary DEPTH=8)
        @(posedge clk);
        wr_en = 1; data_in = 8'hA1;
        @(posedge clk);
        data_in = 8'hB2;
        @(posedge clk);
        data_in = 8'hC3;
        @(posedge clk);
        wr_en = 0;

        // Read 1 element
        #20;
        @(posedge clk);
        rd_en = 1;
        @(posedge clk);
        rd_en = 0;

        #20;
        // Verify output read
        if (data_out !== 8'hA1) begin
            $display("[FAIL] Read data mismatch");
        end else begin
            $display("[PASS] Read data verified: %h", data_out);
        end

        // Note: Full flag, empty flag after drain, and overflow are untested in this TB!
        #50;
        $finish;
    end

endmodule
