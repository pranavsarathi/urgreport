// UART Transmitter Module with Configurable Baud Divider
// States: IDLE, START, DATA, STOP
module uart_tx #(
    parameter CLKS_PER_BIT = 16
)(
    input  wire       clk,
    input  wire       rst_n,
    input  wire       tx_start,
    input  wire [7:0] tx_data,
    output reg        tx_out,
    output reg        tx_busy,
    output reg        tx_done
);

    localparam STATE_IDLE  = 2'b00;
    localparam STATE_START = 2'b01;
    localparam STATE_DATA  = 2'b10;
    localparam STATE_STOP  = 2'b11;

    reg [1:0] state;
    reg [7:0] clk_count;
    reg [2:0] bit_index;
    reg [7:0] data_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= STATE_IDLE;
            tx_out    <= 1'b1;
            tx_busy   <= 1'b0;
            tx_done   <= 1'b0;
            clk_count <= 8'd0;
            bit_index <= 3'd0;
            data_reg  <= 8'd0;
        end else begin
            case (state)
                STATE_IDLE: begin
                    tx_done   <= 1'b0;
                    tx_busy   <= 1'b0;
                    tx_out    <= 1'b1;
                    clk_count <= 8'd0;
                    bit_index <= 3'd0;

                    if (tx_start) begin
                        data_reg <= tx_data;
                        tx_busy  <= 1'b1;
                        state    <= STATE_START;
                    end
                end

                STATE_START: begin
                    tx_out <= 1'b0; // Start bit
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1'b1;
                    end else begin
                        clk_count <= 8'd0;
                        state     <= STATE_DATA;
                    end
                end

                STATE_DATA: begin
                    tx_out <= data_reg[bit_index];
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1'b1;
                    end else begin
                        clk_count <= 8'd0;
                        if (bit_index < 3'd7) begin
                            bit_index <= bit_index + 1'b1;
                        end else begin
                            bit_index <= 3'd0;
                            state     <= STATE_STOP;
                        end
                    end
                end

                STATE_STOP: begin
                    tx_out <= 1'b1; // Stop bit
                    if (clk_count < CLKS_PER_BIT - 1) begin
                        clk_count <= clk_count + 1'b1;
                    end else begin
                        clk_count <= 8'd0;
                        tx_done   <= 1'b1;
                        tx_busy   <= 1'b0;
                        state     <= STATE_IDLE;
                    end
                end

                default: begin
                    state <= STATE_IDLE;
                end
            endcase
        end
    end

endmodule
