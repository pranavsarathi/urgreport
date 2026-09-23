// SPI Master Controller (Mode 0: CPOL=0, CPHA=0)
module spi_master (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       start,
    input  wire [7:0] tx_data,
    input  wire       miso,
    output reg        sclk,
    output reg        mosi,
    output reg        cs_n,
    output reg  [7:0] rx_data,
    output reg        busy
);

    localparam IDLE  = 2'b00;
    localparam LOAD  = 2'b01;
    localparam SHIFT = 2'b10;
    localparam DONE  = 2'b11;

    reg [1:0] state;
    reg [2:0] bit_cnt;
    reg [7:0] shift_reg;
    reg       sclk_en;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state     <= IDLE;
            cs_n      <= 1'b1;
            sclk      <= 1'b0;
            mosi      <= 1'b0;
            rx_data   <= 8'd0;
            busy      <= 1'b0;
            bit_cnt   <= 3'd0;
            shift_reg <= 8'd0;
            sclk_en   <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    cs_n    <= 1'b1;
                    busy    <= 1'b0;
                    sclk    <= 1'b0;
                    sclk_en <= 1'b0;
                    if (start) begin
                        state     <= LOAD;
                        shift_reg <= tx_data;
                        busy      <= 1'b1;
                    end
                end

                LOAD: begin
                    cs_n    <= 1'b0;
                    mosi    <= shift_reg[7];
                    bit_cnt <= 3'd7;
                    state   <= SHIFT;
                end

                SHIFT: begin
                    sclk <= ~sclk;
                    if (sclk) begin
                        // Falling edge: shift out next bit
                        if (bit_cnt == 3'd0) begin
                            state <= DONE;
                        end else begin
                            bit_cnt   <= bit_cnt - 1'b1;
                            shift_reg <= {shift_reg[6:0], miso};
                            mosi      <= shift_reg[6];
                        end
                    end else begin
                        // Rising edge: sample MISO
                        rx_data <= {rx_data[6:0], miso};
                    end
                end

                DONE: begin
                    sclk  <= 1'b0;
                    cs_n  <= 1'b1;
                    busy  <= 1'b0;
                    state <= IDLE;
                end

                default: state <= IDLE;
            endcase
        end
    end

endmodule
