// Hierarchical 3-Stage Pipeline Datapath Top Module
// Instantiates: fetch (u_fetch), decode (u_decode), execute (u_execute)
module pipeline_top (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        stall,
    input  wire [31:0] instr,
    input  wire [31:0] reg_data1,
    output wire [31:0] pc,
    output wire [31:0] alu_out,
    output wire        zero
);

    wire [2:0]  alu_ctrl;
    wire [31:0] imm;

    // Stage 1 Instance: Fetch
    fetch u_fetch (
        .clk(clk),
        .rst_n(rst_n),
        .stall(stall),
        .pc(pc)
    );

    // Stage 2 Instance: Decode
    decode u_decode (
        .clk(clk),
        .rst_n(rst_n),
        .instr(instr),
        .alu_op(alu_ctrl),
        .imm_val(imm)
    );

    // Stage 3 Instance: Execute
    execute u_execute (
        .clk(clk),
        .rst_n(rst_n),
        .alu_op(alu_ctrl),
        .op_a(reg_data1),
        .op_b(imm),
        .alu_result(alu_out),
        .zero_flag(zero)
    );

endmodule
