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


## OTA firmware updates

The WROOM controller now uses the same temporary SoftAP + browser upload approach as the Pedals firmware.

1. Power-cycle the controller to open its 60-second OTA connection window.
2. Connect your PC to Wi-Fi **GamePadPro-RPM-LED-OTA** (password **GPRpmLedOTA8264**).
3. Open **http://192.168.4.1/** and upload the compiled ESP32-WROOM `.bin` file.
4. If the PC connects within the first 60 seconds, the OTA access point remains available while connected. The controller reboots after a successful upload.

ESP-NOW and OTA share channel 1, as in the Pedals implementation. The OTA window closes after 60 seconds if no PC is connected; reboot the controller to reopen it.

## Disconnected receiver / normal-light mode

If no valid packet from the paired S3 Receiver has been received for 300 ms, all 60 LEDs turn solid white. This is also the power-up default until the receiver is detected. As soon as valid telemetry resumes, RPM sweep and shift flashing resume automatically.
