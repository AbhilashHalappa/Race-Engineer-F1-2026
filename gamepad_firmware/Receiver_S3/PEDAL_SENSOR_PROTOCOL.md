# Pedal Sensor Configuration Protocol V1

This is a separate protocol for load-cell sensor setup. It does **not** modify `Protocol.h`, `LegacyPacket`, the 100 Hz pedal telemetry stream, or the receiver's existing PC/PS V1–V3 response-curve calibration protocol.

## Data path

`PC UI --USB CDC--> Receiver S3 --ESP-NOW--> Pedal ESP32`

Responses travel back through the same path. The receiver's existing serial byte fan-out parser remains in place; the new `LC` parser observes the incoming stream independently.

## Frame format

Both command and status frames are exactly 54 bytes. All multi-byte values and IEEE-754 `float` values use the ESP32 little-endian representation.

| Offset | Size | Field |
|---:|---:|---|
| 0 | 1 | Magic 0: ASCII `L` |
| 1 | 1 | Magic 1: `C` command, `S` status |
| 2 | 1 | Protocol version = 1 |
| 3 | 1 | Kind: 1 command, 2 status |
| 4 | 1 | Command ID |
| 5 | 2 | Sequence, uint16 |
| 7 | 1 | Throttle mode: 1 analog, 2 HX711 |
| 8 | 1 | Brake mode: 1 analog, 2 HX711 |
| 9 | 1 | Flags: bit 0 throttle invert, bit 1 brake invert |
| 10 | 1 | Throttle filter divisor (minimum 1) |
| 11 | 1 | Brake filter divisor (minimum 1) |
| 12 | 4 | Throttle load-cell capacity kg, float |
| 16 | 4 | Brake load-cell capacity kg, float |
| 20 | 4 | Throttle maximum operating force kg, float |
| 24 | 4 | Brake maximum operating force kg, float |
| 28 | 4 | Throttle counts per kg, float |
| 32 | 4 | Brake counts per kg, float |
| 36 | 4 | Known calibration force kg, float |
| 40 | 1 | Result code (status) |
| 41 | 4 | Throttle raw delta from tare, int32 |
| 45 | 4 | Brake raw delta from tare, int32 |
| 49 | 2 | Current throttle output 0–4095 |
| 51 | 2 | Current brake output 0–4095 |
| 53 | 1 | CRC-8/ATM over bytes 0–52 (poly 0x07, init 0) |

## Commands

| ID | Command | Behaviour |
|---:|---|---|
| 1 | GET_STATUS | Return current settings and live readings |
| 2 | SET_CONFIG | Validate, apply, auto-tare selected HX711 axes, then save settings in pedal NVS |
| 3 | TARE_THROTTLE | Re-zero throttle HX711 |
| 4 | TARE_BRAKE | Re-zero brake HX711 |
| 5 | TARE_BOTH | Re-zero each axis currently configured as HX711 |
| 6 | CALIBRATE_THROTTLE | Average eight readings under the known force in field 36 and calculate counts/kg |
| 7 | CALIBRATE_BRAKE | Same for brake |
| 8 | RESET_DEFAULTS | Restore compile-time defaults, re-tare active HX711 axes and save |

For calibration, first tare with the pedal unloaded. Then apply a known force and send command 6 or 7 with the known force in kg in field 36. The calibration force must be at least 0.1 kg and no greater than the configured cell capacity.

## Result codes

| Code | Meaning |
|---:|---|
| 0 | OK |
| 1 | Invalid frame |
| 2 | Invalid configuration |
| 3 | HX711 ready timeout |
| 4 | No meaningful load detected during calibration |
| 5 | Invalid known calibration force |
| 6 | Command unsupported for selected sensor mode |

## UI integration notes

- Send a complete 54-byte frame, not ASCII text or JSON.
- `SET_CONFIG` automatically tares any axis configured as HX711; instruct the user to release both pedals before applying the new configuration.
- After every command, wait for an `LS` status frame and inspect its result code.
- Poll `GET_STATUS` when refreshing live raw values; status is not continuously streamed.
- Keep the existing PC/PS curve/deadzone UI and protocol intact. Sensor calibration and response-curve calibration are separate operations.
