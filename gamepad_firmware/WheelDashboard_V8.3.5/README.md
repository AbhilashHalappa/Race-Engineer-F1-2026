# WheelDashboard

ESP32 wheel transmitter for **GamePad Pro V8**.

Sends buttons, encoders, dual clutches, and rotary-pot buttons over ESP-NOW.  
Receives compact telemetry for the MAX7219 display and 14-LED status bar.

## Board / flash

| Setting | Value |
|---------|--------|
| Board | ESP32 Dev Module (WROOM) |
| Sketch | `WheelDashboard.ino` (this folder) |
| Upload | USB serial to the wheel ESP32 |

**Libraries:** FastLED, LedController (MAX7219)

```powershell
cd "d:\Abhilash\Racing Sim Diy Final\repos\gamepad-pro-v8"
git pull origin main
```

Then open this folder’s `.ino` in Arduino IDE and Upload.

## What it does

- 3×4 button matrix → bits 0–11
- 3×4 encoder matrix → bits 12–23
- 2× rotary pots → **2 buttons each** (low / high + dead centre) → bits 24/25 and 26/27
- Dual clutch paddles (filtered ADC, raw → HID; calibrate in Windows / game)
- MAX7219: speed / gear / position
- 14× WS2812: RPM + DRS / pit / ERS / flag / fuel / ERS energy
- ESP-NOW TX ~200 Hz to receiver; RX dashboard ~50 Hz

## MAC address

Edit `Secrets.h` so `RECEIVER_MAC` matches the Wi‑Fi STA MAC of your ESP32-S3 receiver.

## Key files

| File | Purpose |
|------|---------|
| `Pins.h` | GPIO map |
| `Config.h` | Rates, LED brightness, pot zones, clutch filter |
| `Inputs.cpp` | Buttons, pots, clutches |
| `RPMBar.cpp` | 14-LED bar |
| `ESPNowManager.cpp` | Radio TX/RX |

## Clutch paddles

Clutches are **off by default** (`ENABLE_CLUTCHES 0` in `Config.h`) because
GPIO 34/35 float when nothing is wired and pick up noise from pot/button
activity (Windows RX/RY look like they move when you turn a pot).

When paddles are connected:

```cpp
#define ENABLE_CLUTCHES 1
```

Then reflash the wheel. Values are filtered ADC only — calibrate in Windows / game.

## HID button numbers (Windows)

Receiver shifts wheel bits by +1 (`buttonState << 1`), so:

| Wheel bit | Windows button | Source |
|-----------|----------------|--------|
| 0–11 | 1–12 | Push-button matrix |
| 12–23 | 13–24 | Encoder matrix |
| 24 / 25 | 25 / 26 | Pot 1 low / high |
| 26 / 27 | 27 / 28 | Pot 2 low / high |

**Free USB bits (for future shifter C3):** 0, 29, 30, 31 — seq up/down/N/R.

## Rotary pots (2 buttons each)

See also `docs/pot-buttons.md` in the repo root.

```
LOW (<=1200) → button | dead centre | HIGH (>=2800) → button
```

Tune `POT_LEFT_THRESHOLD` / `POT_RIGHT_THRESHOLD` in `Config.h` if zones feel wrong.

## LED bar

| LED | Function |
|-----|----------|
| 1–8 | RPM / shift flash |
| 9 | DRS: **red** = available (SimHub 2), **green** = in use (SimHub 3), off = 0 |
| 10 | Motor temp (C3 10K NTC): green / yellow / red-flash |
| 11 | ERS mode |
| 12 | Flag |
| 13 | Low fuel |
| 14 | Low ERS energy |

## LED 10 colours (wheel)

LED **10** on the wheel indicates the motor temperature received from the
MotorTemp_C3 over ESP-NOW.

| Temperature | Colour | Status |
|-------------|--------|--------|
| < 40 °C | Blue | Cool |
| 40–55 °C | Green | Normal |
| 55–70 °C | Yellow | Warm |
| 70–80 °C | Orange | Hot |
| 80–90 °C | Red | Very hot |
| ≥ 90 °C | Flashing Red | Critical / Over-temperature |
| No packet / invalid ADC | Off | Temperature unavailable |

The temperature is measured using a **10K NTC mounted near the motor stator windings**.

> **Warning:** Flashing red indicates an over-temperature condition. Stop using
> the motor and allow it to cool before continuing.
Brightness: `RPM_LED_BRIGHTNESS` (0–255) in `Config.h`.

## Debug

Set `ENABLE_SERIAL_DEBUG` / `DEBUG_ESPNOW` to `1` in `Config.h` only while troubleshooting, then turn off again.

## V8.3.1 Receiver watchdog

If Receiver dashboard packets stop for more than 500 ms, the wheel clears stale speed/RPM/DRS/ERS/position/flag telemetry rather than freezing the last state. Existing wheel controls continue independently.
