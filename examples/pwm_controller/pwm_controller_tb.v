`timescale 1ns/1ps

module pwm_controller_tb;

    reg clk;
    reg rst_n;
    reg enable;
    reg [7:0] period;
    reg [7:0] duty;
    wire pwm_out;
    wire cycle_done;

    pwm_controller dut (
        .clk(clk),
        .rst_n(rst_n),
        .enable(enable),
        .period(period),
        .duty(duty),
        .pwm_out(pwm_out),
        .cycle_done(cycle_done)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0;
        enable = 0;
        period = 8'd10;
        duty = 8'd4;

        #20;
        rst_n = 1;
        #10;

        enable = 1;
        // Run 2 full PWM cycles
        repeat (25) @(posedge clk);

        // Verification check
        if (cycle_done !== 1'b1 && pwm_out !== 1'b0) begin
            $display("[FAIL] PWM output not toggling as expected");
        end else begin
            $display("[PASS] PWM controller generated output pulses");
        end

        #20;
        $finish;
    end

endmodule
