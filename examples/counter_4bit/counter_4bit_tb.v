// Testbench for 4-bit Counter
// Intentionally tests only up-counting; down-counting and rollover checking omitted.
`timescale 1ns/1ps

module counter_4bit_tb;

    reg clk;
    reg rst_n;
    reg enable;
    reg up_down;
    wire [3:0] count;
    wire rollover;

    counter_4bit u_dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .up_down(up_down),
        .count(count),
        .rollover(rollover)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0; // Assert active-low reset
        enable = 0;
        up_down = 1;

        #20;
        rst_n = 1; // Release reset
        #10;

        enable = 1;
        up_down = 1; // Count up only

        repeat (8) begin
            #10;
            $display("Time=%0t count=%d", $time, count);
        end

        // Note: up_down is never set to 0 (down counting untested)
        // Note: rollover is never checked with assert or if-condition

        #20;
        $finish;
    end

endmodule
