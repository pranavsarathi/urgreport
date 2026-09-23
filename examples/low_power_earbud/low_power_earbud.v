// Low-Power Wireless Earbud Voice Activity Detector (VAD)
// Features: PDM Accumulator, Power State Machine, and Wake Interrupt Generator.
`timescale 1ns/1ps

module low_power_earbud #(
    parameter WINDOW_SIZE        = 16,
    parameter ACTIVITY_THRESHOLD = 4
) (
    input clk,
    input rst_n,
    input pdm_data,
    input power_down,
    output reg wake_irq,
    output reg audio_valid,
    output reg [1:0] power_state
);

    // State definitions
    parameter STATE_ACTIVE    = 2'b00;
    parameter STATE_LOW_POWER = 2'b01;
    parameter STATE_WAKE      = 2'b10;

    reg [1:0] state;
    reg [4:0] sample_count;
    reg [4:0] pdm_count;
    reg activity_detected;

    // 1. Digital PDM Accumulator & Window Counter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sample_count      <= 5'd0;
            pdm_count         <= 5'd0;
            activity_detected <= 1'b0;
        end else begin
            if (pdm_data) begin
                pdm_count <= pdm_count + 1'b1;
            end

            // Check boundary limit of evaluation window
            if (sample_count == WINDOW_SIZE - 1) begin
                sample_count      <= 5'd0;
                activity_detected <= (pdm_count >= ACTIVITY_THRESHOLD);
                pdm_count         <= 5'd0;
            end else begin
                sample_count <= sample_count + 1'b1;
            end
        end
    end

    // 2. Power Management Finite State Machine (FSM)
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state       <= STATE_ACTIVE;
            wake_irq    <= 1'b0;
            audio_valid <= 1'b0;
        end else begin
            case (state)
                STATE_ACTIVE: begin
                    audio_valid <= 1'b1;
                    wake_irq    <= 1'b0;
                    if (power_down) begin
                        state <= STATE_LOW_POWER;
                    end
                end

                STATE_LOW_POWER: begin
                    audio_valid <= 1'b0;
                    wake_irq    <= 1'b0;
                    if (activity_detected) begin
                        state <= STATE_WAKE;
                    end
                end

                STATE_WAKE: begin
                    audio_valid <= 1'b1;
                    wake_irq    <= 1'b1; // Trigger host wakeup interrupt
                    state       <= STATE_ACTIVE;
                end

                default: begin
                    state       <= STATE_ACTIVE;
                    wake_irq    <= 1'b0;
                    audio_valid <= 1'b0;
                end
            endcase
        end
    end

    // Continuous status assignment
    always @* begin
        power_state = state;
    end

endmodule
