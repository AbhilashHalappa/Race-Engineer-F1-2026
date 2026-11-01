# ESP32-WROOM 60-LED RPM Shift Light

Independent ESP32-WROOM controller for a 60-pixel WS2812B strip. The S3 Receiver forwards only the latest Race Engineer RPM percentage and shift-light flag over ESP-NOW.

## Hardware

- ESP32-WROOM STA MAC: `A0:B7:65:DD:85:04` (configured as the peer in Receiver_S3/Secrets.h)
- WS2812B data: GPIO18
- LED layout: 60 pixels, 30 per side, symmetrical from both outer ends toward the centre
- External regulated 5 V supply recommended (4–5 A capacity for 60 pixels at high brightness)
- Join ESP32 and LED supply grounds. Fit a 330–470 ohm series resistor on data and a 1000 uF capacitor across 5 V/GND near the strip.
- Install the **Adafruit NeoPixel** Arduino library.

## Flash

Open this folder as an Arduino sketch and select an ESP32-WROOM board. Flash `RPM_ShiftLight_WROOM.ino`.

## Behaviour

- RPM 0–100% fills both sides symmetrically and retracts when RPM falls.
- Position bands progress green, yellow, orange, then red.
- The existing Race Engineer `shiftLight` flag flashes the complete bar white; white is not inferred from a full bar.
- Missing telemetry for 300 ms clears the bar.
- Receiver uses ESP-NOW channel 1 and the compact checksummed 8-byte protocol in `RpmLedProtocol.h`.

## Receiver integration

The S3 sends wheel dashboard packets first. The RPM LED packet is queued behind the wheel packet and ahead of low-rate sensor configuration traffic. It does not modify the wheel, pedal, handbrake, shifter, or MotorTemp payload formats.
