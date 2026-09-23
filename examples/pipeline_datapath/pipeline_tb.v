`timescale 1ns/1ps

module pipeline_tb;

    reg clk;
    reg rst_n;
    reg stall;
    reg [31:0] instr;
    reg [31:0] reg_data1;
    wire [31:0] pc;
    wire [31:0] alu_out;
    wire zero;

    pipeline_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .stall(stall),
        .instr(instr),
        .reg_data1(reg_data1),
        .pc(pc),
        .alu_out(alu_out),
        .zero(zero)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        stall = 0;
        instr = 32'd0;
        reg_data1 = 32'd0;

        #20;
        rst_n = 1;
        #10;

        // Feed ADDI x1, x2, 15 (instr = 32'h00F10093), reg_data1 = 25
        @(posedge clk);
        instr = 32'h00F10093;
        reg_data1 = 32'd25;

        repeat (4) @(posedge clk);

        // Verification check on ALU output
        if (alu_out !== 32'd40) begin
            $display("[FAIL] Expected ALU result 40 (25 + 15), got %d", alu_out);
        end else begin
            $display("[PASS] Hierarchical pipeline execution verified: %d", alu_out);
        end

        #20;
        $finish;
    end

endmodule
