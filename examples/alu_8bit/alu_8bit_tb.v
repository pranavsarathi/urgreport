// Testbench for 8-bit Arithmetic Logic Unit (ALU)
// Note: Intentionally omits opcode 3'b111 (SHR) and never checks 'overflow' output.
`timescale 1ns/1ps

module alu_8bit_tb;

    reg clk;
    reg reset;
    reg [7:0] A;
    reg [7:0] B;
    reg [2:0] opcode;
    wire [7:0] result;
    wire carry;
    wire zero;
    wire overflow;

    // Instantiate Device Under Test (DUT)
    alu_8bit u_dut (
        .clk(clk),
        .reset(reset),
        .A(A),
        .B(B),
        .opcode(opcode),
        .result(result),
        .carry(carry),
        .zero(zero),
        .overflow(overflow)
    );

    // Clock generator (100MHz, 10ns period)
    always #5 clk = ~clk;

    initial begin
        // 1. Initialize and assert reset
        clk = 0;
        reset = 1;
        A = 8'h00;
        B = 8'h00;
        opcode = 3'b000;

        #20;
        reset = 0; // Release reset
        #10;

        // 2. Test ADD (3'b000)
        A = 8'h25;
        B = 8'h13;
        opcode = 3'b000;
        #10;
        if (result !== 8'h38) begin
            $display("[FAIL] ADD test failed! Expected: 8'h38, Got: %h", result);
        end else begin
            $display("[PASS] ADD test passed: %h", result);
        end

        // 3. Test SUB (3'b001)
        A = 8'h50;
        B = 8'h20;
        opcode = 3'b001;
        #10;
        if (result !== 8'h30) begin
            $display("[FAIL] SUB test failed! Expected: 8'h30, Got: %h", result);
        end

        // 4. Test AND (3'b010)
        A = 8'hAA;
        B = 8'h55;
        opcode = 3'b010;
        #10;
        if (result !== 8'h00) begin
            $display("[FAIL] AND test failed!");
        end

        // 5. Test OR (3'b011)
        A = 8'hF0;
        B = 8'h0F;
        opcode = 3'b011;
        #10;
        if (result !== 8'hFF) begin
            $display("[FAIL] OR test failed!");
        end

        // 6. Test XOR (3'b100)
        A = 8'hFF;
        B = 8'hAA;
        opcode = 3'b100;
        #10;
        if (result !== 8'h55) begin
            $display("[FAIL] XOR test failed!");
        end

        // 7. Test NOT (3'b101)
        A = 8'h0F;
        opcode = 3'b101;
        #10;
        if (result !== 8'hF0) begin
            $display("[FAIL] NOT test failed!");
        end

        // 8. Test SHL (3'b110)
        A = 8'h01;
        opcode = 3'b110;
        #10;
        if (result !== 8'h02) begin
            $display("[FAIL] SHL test failed!");
        end

        // NOTE: opcode 3'b111 (SHR) is intentionally omitted!
        // NOTE: 'overflow' output is NEVER verified or checked in this testbench!

        #20;
        $display("ALU Pre-Simulation Test completed.");
        $finish;
    end

endmodule
