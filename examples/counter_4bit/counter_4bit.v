// 4-bit Synchronous Up/Down Counter with Active-Low Reset
`timescale 1ns/1ps

module counter_4bit (
    input clk,
    input rst_n,
    input enable,
    input up_down,
    output reg [3:0] count,
    output reg rollover
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count    <= 4'b0000;
            rollover <= 1'b0;
        end else if (enable) begin
            if (up_down) begin
                if (count == 4'b1111) begin
                    count    <= 4'b0000;
                    rollover <= 1'b1;
                end else begin
                    count    <= count + 1'b1;
                    rollover <= 1'b0;
                end
            end else begin
                if (count == 4'b0000) begin
                    count    <= 4'b1111;
                    rollover <= 1'b1;
                end else begin
                    count    <= count - 1'b1;
                    rollover <= 1'b0;
                end
            end
        end else begin
            rollover <= 1'b0;
        end
    end

endmodule
