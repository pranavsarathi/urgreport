// Stage 3: Execution / ALU
module execute (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [2:0]  alu_op,
    input  wire [31:0] op_a,
    input  wire [31:0] op_b,
    output reg  [31:0] alu_result,
    output wire        zero_flag
);

    assign zero_flag = (alu_result == 32'd0);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            alu_result <= 32'd0;
        end else begin
            case (alu_op)
                3'b000:  alu_result <= op_a + op_b;
                3'b001:  alu_result <= op_a - op_b;
                3'b010:  alu_result <= op_a & op_b;
                3'b011:  alu_result <= op_a | op_b;
                3'b100:  alu_result <= op_a ^ op_b;
                default: alu_result <= 32'd0;
            endcase
        end
    end

endmodule
