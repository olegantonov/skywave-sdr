#pragma once

namespace pins {
// Proposed wiring for a separate SkyWave prototype, not the SkySentinel wiring.
constexpr int OLED_SDA = 8;
constexpr int OLED_SCL = 9;
constexpr int PTT = 4;
constexpr int TUNE_DOWN = 5;
constexpr int TUNE_UP = 6;
constexpr int BAND = 7;
constexpr int USB_DM = 19;
constexpr int USB_DP = 20;
constexpr int TX_ARM = 38;
constexpr int MODULE_A = 39;
constexpr int MODULE_B = 40;
constexpr int VHF_PD = 41;
constexpr int UHF_PD = 42;
constexpr int CODEC_RESET_N = 15;
constexpr int LO_RESET_N = 48;
}
