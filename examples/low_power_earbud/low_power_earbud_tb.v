// Initial Testbench for Low-Power Wireless Earbud VAD
// Note: Intentionally provides only 8 sample cycles (< WINDOW_SIZE - 1 = 15).
// Note: Omits WAKE transition and never checks 'wake_irq' output.
`timescale 1ns/1ps

module low_power_earbud_tb;

    reg clk;
    reg rst_n;
    reg pdm_data;
    reg power_down;
    wire wake_irq;
    wire audio_valid;
    wire [1:0] power_state;

    // Instantiate Device Under Test (DUT)
    low_power_earbud #(
        .WINDOW_SIZE(16),
        .ACTIVITY_THRESHOLD(4)
    ) u_dut (
        .clk(clk),
        .rst_n(rst_n),
        .pdm_data(pdm_data),
        .power_down(power_down),
        .wake_irq(wake_irq),
        .audio_valid(audio_valid),
        .power_state(power_state)
    );

    // Clock generator (100MHz)
    always #5 clk = ~clk;

    initial begin
        clk = 0;
        rst_n = 0; // Assert reset
        pdm_data = 0;
        power_down = 0;

        #20;
        rst_n = 1; // Release reset
        #10;

        // Drive 8 PDM pulses (Window is 16, so sample_count == 15 is NOT reached!)
        repeat (8) begin
            @(posedge clk);
            pdm_data = 1;
            #2;
            pdm_data = 0;
        end

        // Only audio_valid is monitored
        if (audio_valid !== 1'b1) begin
            $display("[FAIL] Expected audio_valid high during active mode");
        end else begin
            $display("[PASS] Audio streaming active");
        end

        // NOTE: 'wake_irq' output is NEVER verified or checked in this testbench!
        // NOTE: 'sample_count == WINDOW_SIZE - 1' is never reached!
        // NOTE: Transition to STATE_WAKE is never exercised!

        #50;
        $finish;
    end

endmodule
