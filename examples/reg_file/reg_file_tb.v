`timescale 1ns/1ps

module reg_file_tb;

    reg clk;
    reg rst_n;
    reg wr_en;
    reg [4:0] rd_addr1;
    reg [4:0] rd_addr2;
    reg [4:0] wr_addr;
    reg [31:0] wr_data;
    wire [31:0] rd_data1;
    wire [31:0] rd_data2;

    reg_file dut (
        .clk(clk),
        .rst_n(rst_n),
        .wr_en(wr_en),
        .rd_addr1(rd_addr1),
        .rd_addr2(rd_addr2),
        .wr_addr(wr_addr),
        .wr_data(wr_data),
        .rd_data1(rd_data1),
        .rd_data2(rd_data2)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        wr_en = 0;
        rd_addr1 = 5'd0;
        rd_addr2 = 5'd0;
        wr_addr = 5'd0;
        wr_data = 32'd0;

        #20;
        rst_n = 1;
        #10;

        // Write to reg 1
        @(posedge clk);
        wr_en = 1;
        wr_addr = 5'd1;
        wr_data = 32'hDEADBEEF;
        @(posedge clk);
        wr_en = 0;

        // Read reg 1 via port 1 and reg 0 via port 2
        rd_addr1 = 5'd1;
        rd_addr2 = 5'd0;
        #10;

        if (rd_data1 !== 32'hDEADBEEF) $display("[FAIL] Read reg 1 mismatch");
        else $display("[PASS] Reg 1 read verified: %h", rd_data1);

        if (rd_data2 !== 32'd0) $display("[FAIL] Reg 0 should always be 0");
        else $display("[PASS] Reg 0 hardwired to zero verified");

        #30;
        $finish;
    end

endmodule
