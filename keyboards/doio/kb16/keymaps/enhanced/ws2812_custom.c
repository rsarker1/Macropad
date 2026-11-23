// LED data driver: QMK's bitbang driver with exact pulse widths.
//
// Why: the board leaves QMK on its default bitbang driver, which times each
// bit with a NOP loop. The compiled loop takes branches inside the pulse, so
// a "0" bit stayed high for ~400-500 ns. That's at or past where these LEDs
// start reading it as a "1". Dim colors are mostly 0 bits, and one misread
// high bit turns a dim coral into a bright random color, which is what showed
// up during fades.
//
// Here each pulse is a straight run of NOPs (wait_cpuclock) with no branch
// in it, so the widths below are what the LEDs get. They sit
// in the middle of the WS2812B and SK6812 ranges.
//
// The PWM driver would time this in hardware, but TIM1's DMA request (the
// only timer on pin A10) shares DMA1 channel 5 with the OLED's I2C2 driver.

#include "ws2812.h"
#include "gpio.h"
#include "wait.h"

#define NS_TO_CLK(ns) ((ns) * (CPU_CLOCK / 1000000) / 1000)

#define T0H_CLK NS_TO_CLK(300) // high time of a "0"
#define T1H_CLK NS_TO_CLK(700) // high time of a "1"
#define T1L_CLK NS_TO_CLK(550) // low time after a "1" (a "0" gets 400 ns more)

ws2812_led_t ws2812_leds[WS2812_LED_COUNT];

void ws2812_init(void) {
    gpio_set_pin_output_push_pull(WS2812_DI_PIN);
    gpio_write_pin_low(WS2812_DI_PIN);
}

void ws2812_set_color(int index, uint8_t red, uint8_t green, uint8_t blue) {
    ws2812_leds[index].r = red;
    ws2812_leds[index].g = green;
    ws2812_leds[index].b = blue;
#if defined(WS2812_RGBW)
    ws2812_rgb_to_rgbw(&ws2812_leds[index]);
#endif
}

void ws2812_set_color_all(uint8_t red, uint8_t green, uint8_t blue) {
    for (int i = 0; i < WS2812_LED_COUNT; i++) {
        ws2812_set_color(i, red, green, blue);
    }
}

// Most significant bit first, with no branch anywhere in a pulse: every bit
// goes high, at T0H the pin drops only if the bit is 0 (a BSRR write of 0
// changes nothing), and at T1H it drops for good. Writing BSRR's upper half
// resets the pin.
static void send_byte(uint8_t byte) {
    ioportid_t     port = PAL_PORT(WS2812_DI_PIN);
    const uint32_t set  = 1u << PAL_PAD(WS2812_DI_PIN);
    const uint32_t rst  = set << 16;

    for (uint8_t bit = 0; bit < 8; bit++) {
        uint32_t rst_if_zero = (byte & 0x80) ? 0 : rst;
        port->BSRR           = set;
        wait_cpuclock(T0H_CLK);
        port->BSRR = rst_if_zero;
        wait_cpuclock(T1H_CLK - T0H_CLK);
        port->BSRR = rst;
        wait_cpuclock(T1L_CLK);
        byte <<= 1;
    }
}

void ws2812_flush(void) {
    // Timing-critical: keep interrupts out, as the stock driver does.
    chSysLock();

    for (int i = 0; i < WS2812_LED_COUNT; i++) {
#if (WS2812_BYTE_ORDER == WS2812_BYTE_ORDER_GRB)
        send_byte(ws2812_leds[i].g);
        send_byte(ws2812_leds[i].r);
        send_byte(ws2812_leds[i].b);
#elif (WS2812_BYTE_ORDER == WS2812_BYTE_ORDER_RGB)
        send_byte(ws2812_leds[i].r);
        send_byte(ws2812_leds[i].g);
        send_byte(ws2812_leds[i].b);
#elif (WS2812_BYTE_ORDER == WS2812_BYTE_ORDER_BGR)
        send_byte(ws2812_leds[i].b);
        send_byte(ws2812_leds[i].g);
        send_byte(ws2812_leds[i].r);
#endif
#ifdef WS2812_RGBW
        send_byte(ws2812_leds[i].w);
#endif
    }

    // Hold the line low so the LEDs latch the frame.
    wait_us(WS2812_TRST_US);

    chSysUnlock();
}
