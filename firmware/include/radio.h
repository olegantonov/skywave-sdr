#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace skywave {
enum class Mode { Lsb, Usb, Fm };
enum class State { Preview, Rx, Tx, Inhibited };

struct Band {
    const char* name;
    uint32_t min_hz;
    uint32_t max_hz;
    uint32_t initial_hz;
    uint32_t step_hz;
    Mode mode;
};

// Engineering UI profiles, not a regulatory authorization or a TX band plan.
inline constexpr std::array<Band, 6> BANDS{{
    {"HF 40m", 7000000, 7300000, 7100000, 100, Mode::Lsb},
    {"HF 20m", 14000000, 14350000, 14200000, 100, Mode::Usb},
    {"HF 15m", 21000000, 21450000, 21200000, 100, Mode::Usb},
    {"HF 10m", 28000000, 29700000, 28400000, 100, Mode::Usb},
    {"VHF 2m", 144000000, 148000000, 145500000, 12500, Mode::Fm},
    {"UHF 70cm", 430000000, 440000000, 433500000, 12500, Mode::Fm},
}};

inline const char* mode_name(Mode mode) {
    switch (mode) {
        case Mode::Lsb: return "LSB";
        case Mode::Usb: return "USB";
        case Mode::Fm: return "FM";
    }
    return "?";
}

class Radio {
public:
    static constexpr uint32_t TX_TIMEOUT_MS = 30000;

    const Band& band() const { return BANDS[band_index_]; }
    uint32_t frequency() const { return frequency_hz_; }
    State state() const { return state_; }

    bool tune(int direction) {
        if (ptt_ || (direction != -1 && direction != 1)) return false;
        const int64_t next = static_cast<int64_t>(frequency_hz_) +
                             direction * static_cast<int64_t>(band().step_hz);
        if (next < band().min_hz || next > band().max_hz) return false;
        frequency_hz_ = static_cast<uint32_t>(next);
        invalidate();
        return true;
    }

    bool select_band() {
        if (ptt_) return false;
        band_index_ = (band_index_ + 1) % BANDS.size();
        frequency_hz_ = band().initial_hz;
        invalidate();
        return true;
    }

    // Only a future hardware backend may assert readiness and TX permission.
    void set_backend(bool ready, bool tx_permitted) {
        ready_ = ready;
        permitted_ = ready && tx_permitted;
        if (ptt_ && (!ready_ || !permitted_)) {
            latched_ = true;
            state_ = State::Inhibited;
        } else if (!ptt_) {
            state_ = ready_ ? State::Rx : State::Preview;
        }
    }

    void update_ptt(bool pressed, uint32_t now) {
        if (!pressed) {
            ptt_ = false;
            latched_ = false;
            state_ = ready_ ? State::Rx : State::Preview;
            return;
        }
        if (!ptt_) {
            started_ms_ = now;
            latched_ = !ready_ || !permitted_;
        }
        ptt_ = true;
        if (now - started_ms_ >= TX_TIMEOUT_MS || !ready_ || !permitted_) {
            latched_ = true;
        }
        state_ = latched_ ? State::Inhibited : State::Tx;
    }

private:
    void invalidate() {
        ready_ = false;
        permitted_ = false;
        state_ = State::Preview;
    }
    std::size_t band_index_ = 0;
    uint32_t frequency_hz_ = BANDS[0].initial_hz;
    uint32_t started_ms_ = 0;
    State state_ = State::Preview;
    bool ptt_ = false;
    bool latched_ = false;
    bool ready_ = false;
    bool permitted_ = false;
};

class Button {
public:
    bool update(bool pressed, uint32_t now) {
        if (pressed != raw_) {
            raw_ = pressed;
            changed_ms_ = now;
        }
        const bool previous = stable_;
        if (now - changed_ms_ >= 25) stable_ = raw_;
        return stable_ && !previous;
    }
    bool pressed() const { return stable_; }

private:
    bool raw_ = false;
    bool stable_ = false;
    uint32_t changed_ms_ = 0;
};
}
