// RISC-V 32I Instruction Decoder (Combinational Control Logic)
module riscv_decoder (
    input  wire [31:0] instr,
    output reg         is_rtype,
    output reg         is_itype,
    output reg         is_load,
    output reg         is_store,
    output reg         is_branch,
    output reg         is_jal,
    output reg         is_lui,
    output reg         illegal_instr,
    output wire [4:0]  rd,
    output wire [4:0]  rs1,
    output wire [4:0]  rs2,
    output wire [2:0]  funct3,
    output wire [6:0]  funct7,
    output wire [6:0]  opcode
);

    assign opcode = instr[6:0];
    assign rd     = instr[11:7];
    assign funct3 = instr[14:12];
    assign rs1    = instr[19:15];
    assign rs2    = instr[24:20];
    assign funct7 = instr[31:25];

    always @(*) begin
        is_rtype      = 1'b0;
        is_itype      = 1'b0;
        is_load       = 1'b0;
        is_store      = 1'b0;
        is_branch     = 1'b0;
        is_jal        = 1'b0;
        is_lui        = 1'b0;
        illegal_instr = 1'b0;

        case (opcode)
            7'b0110011: is_rtype  = 1'b1; // R-type ALU (ADD, SUB, AND, OR)
            7'b0010011: is_itype  = 1'b1; // I-type ALU (ADDI, ANDI)
            7'b0000011: is_load   = 1'b1; // Load (LW, LH, LB)
            7'b0100011: is_store  = 1'b1; // Store (SW, SH, SB)
            7'b1100011: is_branch = 1'b1; // Branch (BEQ, BNE, BLT)
            7'b1101111: is_jal    = 1'b1; // JAL
            7'b0110111: is_lui    = 1'b1; // LUI
            default:    illegal_instr = 1'b1;
        endcase
    end

endmodule
