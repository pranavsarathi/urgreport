// Stage 2: Instruction Decode
module decode (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [31:0] instr,
    output reg  [2:0]  alu_op,
    output reg  [31:0] imm_val
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            alu_op  <= 3'd0;
            imm_val <= 32'd0;
        end else begin
            case (instr[6:0])
                7'b0110011: begin // R-type
                    alu_op  <= instr[14:12];
                    imm_val <= 32'd0;
                end
                7'b0010011: begin // I-type
                    alu_op  <= instr[14:12];
                    imm_val <= {{20{instr[31]}}, instr[31:20]};
                end
                default: begin
                    alu_op  <= 3'd0;
                    imm_val <= 32'd0;
                end
            endcase
        end
    end

endmodule
