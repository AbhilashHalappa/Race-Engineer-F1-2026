# MotorTemp_C3

Standalone **ESP32-C3** that reads a **2-wire 10K NTC** thermistor and sends
motor temperature to the GamePad Pro **receiver** over **ESP-NOW**.

LED **10** on the wheel shows the temperature band.

## Hardware (10K NTC)

Voltage divider (need one extra **10K** resistor matching the NTC):

```
3V3 ---- 10K fixed ----+---- GPIO 4 (ADC)
                       |
                     NTC 10K
                       |
                      GND
```

| Part | Notes |
|------|--------|
| NTC | 10K @ 25 °C, 2 wires |
| Series R | 10K (same as NTC R25) |
| ADC pin | GPIO **4** |

Tune `NTC_BETA` in `Config.h` if your probe’s B-value is not **3950** (common values: 3435, 3950, 3977).

## Arduino IDE

| Setting | Value |
|---------|--------|
| Board | ESP32C3 Dev Module (or your C3 board) |
| Sketch | `MotorTemp_C3.ino` |
| Libraries | none beyond ESP32 core (ADC only) |

## Setup steps

1. Flash this sketch; open Serial Monitor (115200) and note **STA MAC**.
2. Put that MAC in `firmware/Receiver_S3/Secrets.h` as `MOTOR_TEMP_MAC`.
3. Confirm `RECEIVER_MAC` here matches the S3 hub.
4. Flash **Receiver_S3** and **WheelDashboard**.

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

Tune `MOTOR_TEMP_WARM_C` / `MOTOR_TEMP_HOT_C` in `firmware/Receiver_S3/Config.h`.
