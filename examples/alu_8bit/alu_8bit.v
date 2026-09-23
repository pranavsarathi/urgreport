// 8-bit Arithmetic Logic Unit (ALU)
// Pre-Simulation RTL Reference Design
`timescale 1ns/1ps

module alu_8bit (
    input clk,
    input reset,
    input [7:0] A,
    input [7:0] B,
    input [2:0] opcode,
    output reg [7:0] result,
    output reg carry,
    output reg zero,
    output reg overflow
);

    reg [8:0] temp_sum;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            result   <= 8'h00;
            carry    <= 1'b0;
            zero     <= 1'b0;
            overflow <= 1'b0;
        end else begin
            case (opcode)
                3'b000: begin // ADD
                    temp_sum = A + B;
                    result   <= temp_sum[7:0];
                    carry    <= temp_sum[8];
                    overflow <= (A[7] == B[7]) && (result[7] != A[7]);
                end

                3'b001: begin // SUB
                    result   <= A - B;
                    carry    <= (A < B);
                    overflow <= (A[7] != B[7]) && (result[7] != A[7]);
                end

                3'b010: begin // AND
                    result   <= A & B;
                    carry    <= 1'b0;
                    overflow <= 1'b0;
                end

                3'b011: begin // OR
                    result   <= A | B;
                    carry    <= 1'b0;
                    overflow <= 1'b0;
                end

                3'b100: begin // XOR
                    result   <= A ^ B;
                    carry    <= 1'b0;
                    overflow <= 1'b0;
                end

                3'b101: begin // NOT
                    result   <= ~A;
                    carry    <= 1'b0;
                    overflow <= 1'b0;
                end

                3'b110: begin // SHL
                    result   <= A << 1;
                    carry    <= A[7];
                    overflow <= 1'b0;
                end

                3'b111: begin // SHR (Unstimulated in testbench)
                    result   <= A >> 1;
                    carry    <= A[0];
                    overflow <= 1'b0;
                end

                default: begin
                    result   <= 8'h00;
                    carry    <= 1'b0;
                    overflow <= 1'b0;
                end
            endcase

            zero <= (result == 8'h00);
        end
    end

endmodule
