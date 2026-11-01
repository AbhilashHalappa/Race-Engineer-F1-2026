# Wheel Companion Ultra Lite — Pedal Firmware

**Firmware version:** V8.3.13  
**Protocol:** Legacy Pedal V1 + Pedal Sensor Config V2

Runtime-configurable three-pedal transmitter firmware. Throttle, brake and clutch each support independent Analog or HX711 sensor selection. The existing 19-byte `LegacyPacket` and 6-byte `PedalPayload` (throttle, brake, clutch: 0–4095) remain unchanged for Receiver S3 compatibility.

## Hardware pin map

| Input | ESP32-WROOM GPIO |
|---|---:|
| Throttle analog | 34 |
| Brake analog | 32 |
| Clutch analog | 35 |
| Brake HX711 DATA/DOUT | 33 |
| Brake HX711 CLK/SCK | 26 |
| Throttle HX711 DATA/DOUT | 27 |
| Throttle HX711 CLK/SCK | 14 |

GPIO25 is not used. Each HX711 uses its own module and load cell. Power HX711 modules from 3.3 V and connect grounds together. Confirm the clutch HX711 pin assignment against the active `Pins.h` before wiring; do not infer it from the analog pin.

## Runtime configuration

The PC application can configure each pedal independently:

- Throttle: Analog or HX711
- Brake: Analog or HX711
- Clutch: Analog or HX711

Each pedal has the same configuration capabilities: sensor mode, load-cell capacity, maximum operating force, counts-per-kg sensitivity, filter divisor, invert, tare, known-force calibration and configuration readback.

Settings are stored in the pedal ESP32 NVS namespace `pedalsens`. Tare offsets are persisted independently for throttle, brake and clutch. On startup, an HX711 pedal without a saved tare is automatically tared; keep that pedal unloaded while the unit starts.

The load-cell `capacity` is the cell's rated capacity. `maximum operating force` determines the 0–4095 output full scale.

## Calibration

1. **Sensor calibration (pedal ESP32):** tare the unloaded load cell, apply a known force, then issue the corresponding calibration command with that force in kg. The firmware averages HX711 samples and updates counts/kg.
2. **Pedal response calibration (Receiver S3):** existing curves, deadzones and HID output calibration remain on the receiver.

Settings and tare writes are read back for verification. Failed operations report a persistence error and attempt to restore the previous runtime and saved values.

## Configuration transport

The pedal sensor configuration protocol is V2. Its packed `PedalSensorFrame` is 74 bytes, with `LC` command frames and `LS` status frames. The receiver relays these frames between USB CDC and the pedal transmitter over ESP-NOW. The legacy 19-byte pedal stream remains unchanged.

## Important

- Do not power on with force applied to an HX711 pedal when a first-boot tare is required.
- Keep the existing receiver/pedal ESP-NOW channel and MAC addresses aligned.
- OTA remains enabled using the existing settings.
- Receiver S3 firmware and HID output logic are not changed by this pedal firmware version update.
