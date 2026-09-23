`timescale 1ns/1ps

module riscv_decoder_tb;

    reg [31:0] instr;
    wire is_rtype;
    wire is_itype;
    wire is_load;
    wire is_store;
    wire is_branch;
    wire is_jal;
    wire is_lui;
    wire illegal_instr;
    wire [4:0] rd;
    wire [4:0] rs1;
    wire [4:0] rs2;
    wire [2:0] funct3;
    wire [6:0] funct7;
    wire [6:0] opcode;

    riscv_decoder dut (
        .instr(instr),
        .is_rtype(is_rtype),
        .is_itype(is_itype),
        .is_load(is_load),
        .is_store(is_store),
        .is_branch(is_branch),
        .is_jal(is_jal),
        .is_lui(is_lui),
        .illegal_instr(illegal_instr),
        .rd(rd),
        .rs1(rs1),
        .rs2(rs2),
        .funct3(funct3),
        .funct7(funct7),
        .opcode(opcode)
    );

    initial begin
        instr = 32'h00000000;
        #10;

        // Test 1: R-type ADD x1, x2, x3 -> opcode 7'b0110011
        instr = 32'h003100B3;
        #10;
        if (is_rtype !== 1'b1) $display("[FAIL] Expected is_rtype=1");
        else $display("[PASS] R-type decoded properly");

        // Test 2: I-type ADDI x1, x2, 10 -> opcode 7'b0010011
        instr = 32'h00A10093;
        #10;
        if (is_itype !== 1'b1) $display("[FAIL] Expected is_itype=1");
        else $display("[PASS] I-type decoded properly");

        // Test 3: Load LW x1, 4(x2) -> opcode 7'b0000011
        instr = 32'h00412083;
        #10;
        if (is_load !== 1'b1) $display("[FAIL] Expected is_load=1");
        else $display("[PASS] Load decoded properly");

        // Note: Store, Branch, JAL, LUI, and illegal_instr opcodes are left untested!
        #20;
        $finish;
    end

endmodule
