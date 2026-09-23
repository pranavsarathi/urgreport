// Stage 1: Instruction Fetch
module fetch (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        stall,
    output reg  [31:0] pc
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc <= 32'd0;
        end else if (!stall) begin
            pc <= pc + 32'd4;
        end
    end

endmodule
