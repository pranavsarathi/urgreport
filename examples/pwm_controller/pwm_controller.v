// Pulse Width Modulation (PWM) Controller
module pwm_controller (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       enable,
    input  wire [7:0] period,
    input  wire [7:0] duty,
    output reg        pwm_out,
    output reg        cycle_done
);

    reg [7:0] counter;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            counter    <= 8'd0;
            pwm_out    <= 1'b0;
            cycle_done <= 1'b0;
        end else if (enable) begin
            if (counter < period) begin
                counter    <= counter + 1'b1;
                cycle_done <= 1'b0;
            end else begin
                counter    <= 8'd0;
                cycle_done <= 1'b1;
            end

            // Compare duty threshold
            if (counter < duty) begin
                pwm_out <= 1'b1;
            end else begin
                pwm_out <= 1'b0;
            end
        end else begin
            counter    <= 8'd0;
            pwm_out    <= 1'b0;
            cycle_done <= 1'b0;
        end
    end

endmodule
