#include <Arduino.h>
#include <U8x8lib.h>
#include <Wire.h>
#include <esp_task_wdt.h>
#include "pins.h"
#include "radio.h"

#if SKYWAVE_SH1106
U8X8_SH1106_128X64_NONAME_HW_I2C display(U8X8_PIN_NONE, pins::OLED_SCL, pins::OLED_SDA);
#else
U8X8_SSD1306_128X64_NONAME_HW_I2C display(U8X8_PIN_NONE, pins::OLED_SCL, pins::OLED_SDA);
#endif

skywave::Radio radio;
skywave::Button ptt, down, up, band;
bool oled_present = false;
bool watchdog_ready = false;
uint32_t last_draw = 0;

const char* state_name() {
    switch (radio.state()) {
        case skywave::State::Preview: return "PREVIEW - NO RF";
        case skywave::State::Rx: return "RX";
        case skywave::State::Tx: return "TX";
        case skywave::State::Inhibited: return "TX BLOQUEADO";
    }
    return "ERRO";
}

void draw_status() {
    char frequency[17];
    snprintf(frequency, sizeof(frequency), "%lu.%06lu MHz",
             static_cast<unsigned long>(radio.frequency() / 1000000),
             static_cast<unsigned long>(radio.frequency() % 1000000));
    if (oled_present) {
        display.clearLine(2);
        display.drawString(0, 2, radio.band().name);
        display.clearLine(3);
        display.drawString(0, 3, frequency);
        display.drawString(0, 4, skywave::mode_name(radio.band().mode));
        display.clearLine(6);
        display.drawString(0, 6, state_name());
    }
}

void serial_status() {
    Serial.printf("band=%s frequency_hz=%lu mode=%s state=%s rf_backend=absent\n",
                  radio.band().name, static_cast<unsigned long>(radio.frequency()),
                  skywave::mode_name(radio.band().mode), state_name());
}

void setup() {
    for (int pin : {pins::TX_ARM, pins::VHF_PD, pins::UHF_PD,
                    pins::CODEC_RESET_N, pins::LO_RESET_N}) {
        digitalWrite(pin, LOW);
        pinMode(pin, OUTPUT);
    }
    for (int pin : {pins::MODULE_A, pins::MODULE_B}) {
        digitalWrite(pin, HIGH);
        pinMode(pin, OUTPUT);
    }
    Serial.begin(115200);
    for (int pin : {pins::PTT, pins::TUNE_DOWN, pins::TUNE_UP, pins::BAND}) {
        pinMode(pin, INPUT_PULLUP);
    }
    Wire.begin(pins::OLED_SDA, pins::OLED_SCL, 100000);
    Wire.setTimeOut(20);
    Wire.beginTransmission(0x3C);
    oled_present = Wire.endTransmission() == 0;
    if (oled_present) {
        display.setBusClock(100000);
        display.begin();
        display.setFont(u8x8_font_chroma48medium8_r);
        display.drawString(0, 0, "SKYWAVE SDR D1");
    }
    const esp_err_t result = esp_task_wdt_init(5, true);
    if (result == ESP_OK || result == ESP_ERR_INVALID_STATE) {
        watchdog_ready = esp_task_wdt_add(nullptr) == ESP_OK;
    }
    Serial.println("SkyWave UI prototype. Commands: ? + - b. No RF backend.");
    if (!oled_present) Serial.println("OLED 0x3C not found; USB interface available.");
    if (!watchdog_ready) Serial.println("ERROR: watchdog registration failed.");
    draw_status();
}

void loop() {
    const uint32_t now = millis();
    ptt.update(digitalRead(pins::PTT) == LOW, now);
    radio.update_ptt(ptt.pressed(), now);
    if (down.update(digitalRead(pins::TUNE_DOWN) == LOW, now)) radio.tune(-1);
    if (up.update(digitalRead(pins::TUNE_UP) == LOW, now)) radio.tune(1);
    if (band.update(digitalRead(pins::BAND) == LOW, now)) radio.select_band();

    // Bound work per iteration so serial traffic cannot starve PTT polling.
    for (int count = 0; count < 8 && Serial.available(); ++count) {
        switch (Serial.read()) {
            case '+': radio.tune(1); break;
            case '-': radio.tune(-1); break;
            case 'b': radio.select_band(); break;
            case '?': serial_status(); break;
            default: break;
        }
    }
    if (now - last_draw >= 200) {
        draw_status();
        last_draw = now;
    }
    if (watchdog_ready && esp_task_wdt_reset() != ESP_OK) {
        watchdog_ready = false;
        Serial.println("ERROR: watchdog reset failed.");
    }
    delay(5);
}
