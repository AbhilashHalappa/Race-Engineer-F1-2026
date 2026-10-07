# Receiver S3 V8.3.3 — Dual-App Compatibility

V8.3.3 works with both the previous full Race Engineer application and Wheel Companion Lite V1.3.0 without reflashing. The legacy `RS/V1` 25-byte status packet remains always-on. Wheel Companion explicitly leases a separate `WL/V1` live-value stream through a CRC-protected `WC/V1` command.

No USB HID, ESP-NOW, pedal, wheel, MotorTemp, or 15-byte PC telemetry layouts are changed.

# Receiver_S3

ESP32-S3 Zero/One USB hub for **GamePad Pro V8**.

One USB-C cable provides:

1. **USB HID gamepad** (wheel buttons, clutches, pedals — no steering)
2. **USB CDC COM port** for SimHub telemetry
3. **ESP-NOW** RX from wheel + pedals, TX dashboard to wheel + LCD

## Board / flash

| Setting | Value |
|---------|--------|
| Board | **ESP32S3 Dev Module** (or your S3 Zero definition) |
| USB CDC On Boot | **Enabled** |
| USB Mode | **USB-OTG / TinyUSB** |
| Sketch | `Receiver_S3.ino` (this folder) |

```powershell
cd "d:\Abhilash\Racing Sim Diy Final\repos\gamepad-pro-v8"
git pull origin main
```

Open this folder’s `.ino` → select the S3 COM port → Upload.  
After upload, reconnect USB and confirm Windows shows a **Game controller** and a **COM port**.

More detail: `README_S3_ZERO_ONE_USB.md`.

## Pins (`Pins.h`)

| Signal | GPIO |
|--------|------|
| Onboard RGB status LED | 21 (Waveshare S3-Zero) |

GPIO 6 / 7 / 8 are unused (steering encoder removed).  
SimHub uses native USB CDC (`Serial`) — no extra UART pins.

## MAC addresses (`Secrets.h`)

| Symbol | Device |
|--------|--------|
| `RECEIVER_MAC` | This S3 (must match wheel/pedals destination) |
| `WHEEL_MAC` | Wheel ESP32 STA MAC |
| `PEDALS_MAC` | Pedals ESP32 STA MAC |
| `MOTOR_TEMP_MAC` | Motor-temp ESP32-C3 STA MAC |
| `DISPLAY_MAC` | LCD board (informational; LCD TX is broadcast) |

## Status LED colours

| Colour | Meaning |
|--------|---------|
| Cyan | Ready / waiting for both |
| Yellow | Pedals OK, waiting wheel |
| Orange | Wheel OK, waiting pedals |
| Green | Wheel + pedals connected |

## HID mapping (summary)

| Input | HID |
|-------|-----|
| X / Y | Unused (steering = standalone device) |
| Throttle / brake | Z / RZ |
| Clutch L / R | RX / RY |
| Wheel `buttonState` bit `i` | USB bit `i+1` |
| USB bits **0, 29, 30, 31** | Free — reserved for sequential shifter (up / down / N / R) |
| Y (planned) | Load-cell handbrake from shifter C3 |

Steering is **not** part of this hub — use your separate steering device in Windows / the sim.

## SimHub

- Select **this receiver’s COM port** in SimHub (not the wheel).
- Keep `ENABLE_SERIAL_DEBUG` / `DEBUG_ESPNOW` at **0** while SimHub is connected (same CDC port).
- Telemetry string format: `D2.` + fields (see `SimHub.cpp`).
- Wheel gets a compact 19-byte dash @ 50 Hz; LCD gets full 77-byte broadcast @ 25 Hz.

## Key files

| File | Purpose |
|------|---------|
| `Gamepad.cpp` | USB HID report (change-only + keepalive) |
| `ESPNowManager.cpp` | Peers, TX priority (wheel dash > LCD) |
| `SimHub.cpp` | Parse SimHub serial → `DashboardPayload` |
| `StatusLED.cpp` | NeoPixel status |
| `Config.h` | Rates, TX power, timeouts |

## Design notes

- HID is updated **first** in `loop()` so LCD/SimHub work cannot stall controls.
- Only one ESP-NOW send at a time; failed/stale frames are dropped.
- LCD uses ESP-NOW **broadcast** so a powered-off display cannot block the radio.

## V8.3.0 telemetry source

SimHub is no longer used by the active receiver firmware. The same USB-C connection remains a composite USB HID + CDC device, but CDC now receives Race Engineer's compact 15-byte binary wheel frame. `RaceEngineerTelemetry.cpp` performs fixed-size CRC validation without `String`, `strtok_r`, or the previous 39-field parser. The receiver forwards only the compact wheel snapshot plus MotorTemp C3 data to the wheel.

The old SimHub parser is preserved only under `legacy/Receiver_S3_SimHub/` and is not compiled into `Receiver_S3`.

## V8.3.1 link health

The Receiver reports a CRC-protected health frame to Race Engineer every 500 ms. It contains live ESP-NOW state for the Wheel, Pedals and MotorTemp C3. Race Engineer shows these in Control Center and logs disconnect/reconnect transitions.

The Receiver status LED now means:

- Green: Wheel + Pedals + MotorTemp connected
- Yellow: Wheel missing
- Orange: Pedals missing
- Purple: MotorTemp missing while Wheel + Pedals are healthy
- Cyan: waiting / Wheel + Pedals both absent

If Race Engineer PC telemetry goes stale, the Receiver continues forwarding a safe zero dashboard at 50 Hz so stale RPM/DRS/ERS cannot remain frozen; MotorTemp continues independently.


## V8.3.3 dual-app Wheel Companion extension

The Receiver once again keeps the original `RS/V1` 25-byte health packet as the always-on USB CDC status stream, so the previous full Race Engineer application sees exactly the status format it expects.

Wheel Companion Lite V1.3.0 opts in with a separate CRC-protected `WC/V1` control frame. While the three-second lease is active, the Receiver additionally sends `WL/V1` live values at 10 Hz: throttle raw ADC, brake raw ADC and MotorTemp `tempCx100`. A normal Wheel Companion exit sends disable immediately; a crash or disconnect falls back automatically when the lease expires.

Only this Receiver_S3 sketch needs to be flashed for V8.3.3. ESP-NOW packet layouts and USB HID mappings are unchanged.


## V8.3.5 pedal-axis normalization

The existing pedal transmitter protocol is unchanged. `SWAP_PEDAL_AXES=1` in
`Config.h` normalizes the installed reversed pedal channels at Receiver ingress.
This makes the same corrected semantic values feed USB HID, Wheel Companion live
status, and throttle/brake response curves. No Pedal-C3 reflash is required.


## V8.3.8 combined shifter + handbrake

The same ESP32-C3 peer now sends Shift Up/Down/AUX plus a 12-bit analog handbrake. USB mapping is: X = optional foot clutch, Y = optional handbrake, Z = throttle, RZ = brake, RX/RY = wheel clutch paddles, buttons 30/31/32 = shifter. The legacy 19-byte ESP-NOW packet size is unchanged.

Wheel Companion uses WC/WL V3 and PC/PS V3 for handbrake live values and saved calibration. V1 and V2 remain accepted for compatibility. Handbrake is disabled by default until enabled in the application.
