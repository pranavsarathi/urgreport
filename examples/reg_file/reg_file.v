// Dual-Read, Single-Write 32x32 Register File (x0 hardwired to 0)
module reg_file (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        wr_en,
    input  wire [4:0]  rd_addr1,
    input  wire [4:0]  rd_addr2,
    input  wire [4:0]  wr_addr,
    input  wire [31:0] wr_data,
    output wire [31:0] rd_data1,
    output wire [31:0] rd_data2
);

    reg [31:0] registers [0:31];
    integer i;

    // Asynchronous read with x0 tied to zero
    assign rd_data1 = (rd_addr1 == 5'd0) ? 32'd0 : registers[rd_addr1];
    assign rd_data2 = (rd_addr2 == 5'd0) ? 32'd0 : registers[rd_addr2];

    // Synchronous write
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 32; i = i + 1) begin
                registers[i] <= 32'd0;
            end
        end else if (wr_en && (wr_addr != 5'd0)) begin
            registers[wr_addr] <= wr_data;
        end
    end

endmodule
