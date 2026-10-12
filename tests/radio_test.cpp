#include <cassert>
#include <cstdint>
#include <iostream>
#include "radio.h"

using namespace skywave;

int main() {
    Radio radio;
    assert(radio.state() == State::Preview);
    radio.update_ptt(true, 0);
    assert(radio.state() == State::Inhibited);
    assert(!radio.tune(1));
    assert(!radio.select_band());
    radio.set_backend(true, true);
    radio.update_ptt(true, 1);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(false, 2);
    assert(radio.state() == State::Rx);
    radio.update_ptt(true, 3);
    assert(radio.state() == State::Tx);
    radio.update_ptt(true, 30003);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(true, 30004);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(false, 30005);
    radio.update_ptt(true, 30006);
    assert(radio.state() == State::Tx);
    radio.set_backend(false, false);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(false, 30007);
    assert(radio.state() == State::Preview);

    for (std::size_t i = 0; i < BANDS.size(); ++i) {
        while (radio.tune(-1)) {}
        assert(radio.frequency() == radio.band().min_hz);
        while (radio.tune(1)) {}
        assert(radio.frequency() <= radio.band().max_hz);
        assert(radio.frequency() + radio.band().step_hz > radio.band().max_hz);
        radio.set_backend(true, true);
        assert(radio.select_band());
        assert(radio.state() == State::Preview);
    }
    assert(radio.frequency() == BANDS[0].initial_hz);
    assert(!radio.tune(0));
    radio.set_backend(true, false);
    radio.update_ptt(true, 40000);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(false, 40001);
    radio.set_backend(true, true);
    radio.update_ptt(true, UINT32_MAX - 100);
    radio.update_ptt(true, 29899);
    assert(radio.state() == State::Inhibited);
    radio.update_ptt(false, 29900);
    assert(radio.tune(1));
    assert(radio.state() == State::Preview);

    Button button;
    assert(!button.update(true, 0));
    assert(!button.update(false, 10));
    assert(!button.update(true, 20));
    assert(!button.update(true, 44));
    assert(button.update(true, 45));
    assert(!button.update(true, 100));
    assert(button.pressed());
    assert(!button.update(false, 101));
    assert(!button.update(false, 126));
    assert(!button.pressed());
    std::cout << "PASS: PTT interlocks, timeout, timer wrap, all bands, debounce\n";
}
