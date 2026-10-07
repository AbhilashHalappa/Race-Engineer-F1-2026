# Wireless Sequential Shifter + Handbrake — ESP32-C3 V8.3.10

One ESP32-C3 Super Mini handles three sequential-shifter switches plus the handbrake. The handbrake firmware supports **either an analog Hall sensor or an HX711 + load cell**, selected at compile time. The wireless packet and ESP32-S3 Receiver remain unchanged: both sensor types are normalized to the same 0..4095 handbrake value.

## Select the handbrake sensor

Open `Config.h` and change only `HANDBRAKE_SENSOR_MODE`.

For the current analog Hall sensor:

```cpp
#define HANDBRAKE_SENSOR_MODE HANDBRAKE_SENSOR_HALL
```

For the future HX711 + 40 kg load cell:

```cpp
#define HANDBRAKE_SENSOR_MODE HANDBRAKE_SENSOR_HX711
```

Only one mode can be active in a build.

## Wiring — shifter (same for both modes)

| Function | ESP32-C3 | Wiring | USB result |
|---|---:|---|---|
| Shift Up | GPIO4 | momentary switch to GND | Button 30 |
| Shift Down | GPIO5 | momentary switch to GND | Button 31 |
| AUX | GPIO6 | momentary switch to GND | Button 32 |

## Wiring — Hall sensor mode

| Hall connection | ESP32-C3 |
|---|---|
| Signal | GPIO0 |
| GND | GND |
| Supply | 3.3 V when supported by the Hall sensor |

The GPIO0 signal must stay within 0..3.3 V. Never feed a 5 V analog signal directly into the ESP32-C3.

If the Hall direction is reversed, change:

```cpp
constexpr bool HALL_HANDBRAKE_INVERT = true;
```

## Wiring — HX711 + load cell mode

| HX711 | ESP32-C3 |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| DAT / DOUT | GPIO1 |
| CLK / SCK | GPIO2 |

Connect the 40 kg load cell to the HX711 excitation/signal inputs according to the load cell/HX711 markings (`E+`, `E-`, `A+`, `A-`) or the board-specific color labels. Do not assume wire colors are universal.

The HX711 driver is included in this firmware, so **no external HX711 Arduino library is required**.

### HX711 startup tare

The C3 automatically tares the load cell at boot. Keep the handbrake fully released while powering/resetting the C3.

### Choose the force that equals 100%

`HX711_COUNTS_FOR_FULL_SCALE` controls how much load-cell change becomes 4095/100% handbrake:

```cpp
constexpr int32_t HX711_COUNTS_FOR_FULL_SCALE = 1000000;
```

The 40 kg cell does **not** need to be pulled to 40 kg. You can tune this value so, for example, your preferred 10–15 kg pull reaches 100%. The Wheel Companion application then performs its normal endpoint/deadzone/6-point curve processing on that transmitted range.

If pulling produces negative counts after tare, change:

```cpp
constexpr bool HX711_HANDBRAKE_INVERT = true;
```

### HX711 sample rate

For a sim-racing handbrake, configure the HX711 module for **80 samples/second** if the board exposes the RATE selection/solder jumper. A module left at 10 SPS will work but will feel noticeably slower. This is a hardware/module setting on many HX711 boards, not something the ESP32 can always change in software.

## Pairing / Receiver

This C3 firmware uses the exact same `ShifterPayload` as V8.3.8, so the existing matching Receiver remains valid:

`Receiver_S3_V8.3.8_UltraLite_Shifter_Handbrake`

1. Flash this C3 sketch.
2. Open Serial Monitor at 115200 and note the C3 STA MAC.
3. Put that MAC into `SHIFTER_MAC` in Receiver `Secrets.h` if not already paired.
4. Flash the Receiver only if pairing or Receiver firmware needs changing.
5. Enable Handbrake in Wheel Companion and run its calibration.

The app-side calibration, top/bottom deadzones and 6-point response curve work for **both Hall and load-cell modes** because the Receiver sees the same 0..4095 handbrake channel.


## Matching the Ultra Lite application UI

The app now has a Handbrake Sensor selector. Select **Hall sensor (analog)** or **Load cell (HX711)** to change the calibration/curve presentation. The selection in the app does not reflash the C3, so `HANDBRAKE_SENSOR_MODE` in `Config.h` must match.

For load-cell mode, also match the application's **Load cell capacity** and **Max force for 100%** to `HX711_LOAD_CELL_CAPACITY_KG` and `HX711_MAX_FORCE_KG`. Calibrate `HX711_COUNTS_PER_KG` once using a known load. This keeps 0..4095 equal to 0..selected max force, so the application's six curve points correspond to 0/20/40/60/80/100% of the selected force.
