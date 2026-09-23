// Testbench for Traffic Light FSM
// Intentionally never exercises 'emergency' input.
`timescale 1ns/1ps

module fsm_traffic_tb;

    reg clk;
    reg reset;
    reg sensor;
    reg emergency;
    wire [1:0] light;

    fsm_traffic u_dut (
        .clk(clk),
        .reset(reset),
        .sensor(sensor),
        .emergency(emergency),
        .light(light)
    );

    always #5 clk = ~clk;

    initial begin
        clk = 0;
        reset = 1;
        sensor = 0;
        emergency = 0; // Emergency kept at 0

        #20;
        reset = 0;
        #10;

        // Transition: IDLE -> RED
        #10;
        if (light !== 2'b01) $display("[FAIL] Expected RED");

        // Transition: RED -> GREEN
        sensor = 1;
        #10;
        if (light !== 2'b10) $display("[FAIL] Expected GREEN");

        // Transition: GREEN -> YELLOW
        #10;
        if (light !== 2'b11) $display("[FAIL] Expected YELLOW");

        // Transition: YELLOW -> RED
        #10;
        if (light !== 2'b01) $display("[FAIL] Expected RED");

        // Note: 'emergency' is never asserted (EMERGENCY state untested)
        #50;
        $finish;
    end

endmodule
