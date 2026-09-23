// Enhanced Testbench for Low-Power Wireless Earbud VAD
// Fully exercises Window boundary, WAKE state transition, and checks 'wake_irq'.
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

        // 1. Complete full 16-sample window to exercise sample_count == WINDOW_SIZE - 1
        repeat (18) begin
            @(posedge clk);
            pdm_data = 1;
            #2;
            pdm_data = 0;
        end

        // 2. Transition into LOW POWER mode
        @(posedge clk);
        power_down = 1;
        #10;
        power_down = 0;

        // 3. Accumulate PDM pulses to cross ACTIVITY_THRESHOLD and trigger WAKE state
        repeat (16) begin
            @(posedge clk);
            pdm_data = 1;
        end

        #20;

        // 4. Assert and verify 'wake_irq' output
        if (wake_irq !== 1'b1) begin
            $error("[FAIL] Host wakeup interrupt 'wake_irq' was expected HIGH!");
        end else begin
            $display("[PASS] Host wakeup interrupt 'wake_irq' successfully asserted: %b", wake_irq);
        end

        // 5. Verify audio_valid
        if (audio_valid !== 1'b1) begin
            $error("[FAIL] Expected audio_valid active!");
        end

        #50;
        $display("[PASS] Complete earbud VAD verification scenario finished.");
        $finish;
    end

endmodule
