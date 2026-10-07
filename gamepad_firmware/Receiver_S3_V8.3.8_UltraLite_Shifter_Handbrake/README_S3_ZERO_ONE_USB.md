# GamePad Pro V8 — ESP32-S3 Zero receiver

This port keeps the existing receiver behaviour while using the S3 Zero's single USB-C connector as a composite USB device:

- USB HID gamepad
- USB CDC COM port for SimHub
- ESP-NOW wheel and pedal reception
- Dashboard forwarding to the wheel
- Onboard RGB status LED

Steering is **not** on this board (standalone device).

## Required Arduino IDE settings

Use an ESP32 Arduino core that supports native USB HID on ESP32-S3.

- Board: **ESP32S3 Dev Module** (or the exact S3 Zero board definition)
- USB CDC On Boot: **Enabled**
- USB Mode: **USB-OTG / TinyUSB**
- Upload Mode: **USB-OTG CDC** when available
- Flash size: match the board
- PSRAM: match the board; the receiver does not require PSRAM

Only one USB-C cable is required. Windows should enumerate both a game controller and a COM port.

## Pin changes

- Onboard addressable RGB LED: GPIO 21
- Steering encoder / centre button removed (GPIO 6 / 7 / 8 free)
- GPIO43/GPIO44 UART removed; SimHub now uses native USB CDC (`Serial`)

GPIO21 is correct for the Waveshare ESP32-S3-Zero. If your S3 Zero is another model, verify its onboard RGB LED GPIO.

## MAC address

Replace `RECEIVER_MAC` in `Secrets.h` with the Wi-Fi STA MAC address of your S3 Zero. The same new receiver MAC must also be entered as the destination/receiver address in the wheel and pedal transmitter projects.

## Debug output

`ENABLE_SERIAL_DEBUG` and `DEBUG_ESPNOW` are disabled by default because SimHub shares the same USB CDC port. Enable them temporarily for troubleshooting, then disable them for normal use.

## Test order

1. Flash the S3 Zero.
2. Reconnect the single USB cable.
3. Confirm a game controller and COM port appear in Windows.
4. Update the receiver MAC in the wheel and pedal projects.
5. Verify wheel ESP-NOW connection.
6. Verify pedal ESP-NOW connection.
7. Test wheel buttons, throttle, brake, both clutches, and status LED (steering is a separate device).
8. Select the S3 Zero COM port in SimHub and test dashboard forwarding.
