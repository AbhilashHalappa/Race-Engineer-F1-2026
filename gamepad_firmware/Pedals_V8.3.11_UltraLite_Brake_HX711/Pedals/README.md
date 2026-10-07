# Pedals V8.3.11 Ultra Lite — Analog / HX711 Brake

This is the active pedal firmware for Wheel Companion Ultra Lite V1.4.0.

## Existing wiring
- Throttle analog: GPIO34
- Brake analog: GPIO35
- Optional clutch analog: GPIO32

## Future brake load-cell wiring
Use a separate HX711 board for the brake:
- HX711 DAT/DOUT -> GPIO25
- HX711 CLK/SCK -> GPIO26
- HX711 VCC -> 3.3 V
- HX711 GND -> GND

Select exactly one brake sensor in `Config.h`:
```cpp
#define BRAKE_SENSOR_MODE BRAKE_SENSOR_ANALOG
// #define BRAKE_SENSOR_MODE BRAKE_SENSOR_HX711
```

In HX711 mode the firmware tares at startup and converts force into the existing 0..4095 brake field. Receiver/HID protocol is unchanged. Leave the brake released while powering the pedal ESP32.
