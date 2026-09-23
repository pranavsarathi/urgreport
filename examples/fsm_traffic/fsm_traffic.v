// Traffic Light Finite State Machine (FSM)
`timescale 1ns/1ps

module fsm_traffic (
    input clk,
    input reset,
    input sensor,
    input emergency,
    output reg [1:0] light // 2'b00: OFF, 2'b01: RED, 2'b10: GREEN, 2'b11: YELLOW
);

    parameter IDLE      = 3'b000;
    parameter RED       = 3'b001;
    parameter GREEN     = 3'b010;
    parameter YELLOW    = 3'b011;
    parameter EMERGENCY = 3'b100;

    reg [2:0] state;

    always @(posedge clk or posedge reset) begin
        if (reset) begin
            state <= IDLE;
            light <= 2'b00;
        end else begin
            case (state)
                IDLE: begin
                    light <= 2'b00;
                    if (emergency)
                        state <= EMERGENCY;
                    else
                        state <= RED;
                end

                RED: begin
                    light <= 2'b01;
                    if (emergency)
                        state <= EMERGENCY;
                    else if (sensor)
                        state <= GREEN;
                end

                GREEN: begin
                    light <= 2'b10;
                    if (emergency)
                        state <= EMERGENCY;
                    else
                        state <= YELLOW;
                end

                YELLOW: begin
                    light <= 2'b11;
                    if (emergency)
                        state <= EMERGENCY;
                    else
                        state <= RED;
                end

                EMERGENCY: begin
                    light <= 2'b01; // Flashing red
                    if (!emergency)
                        state <= IDLE;
                end

                default: begin
                    state <= IDLE;
                    light <= 2'b00;
                end
            endcase
        end
    end

endmodule
