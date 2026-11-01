# Wireless Sequential Shifter + Handbrake — ESP32-C3

One ESP32-C3 Super Mini handles three sequential-shifter switches plus the handbrake. The handbrake sensor can be Hall (GPIO0) or HX711/load cell (GPIO1 DAT, GPIO2 CLK). Sensor selection and calibration are runtime settings stored in ESP32-C3 NVS and managed from Wheel Companion Ultra Lite.

## OTA firmware update

The C3 starts its OTA SoftAP after ESP-NOW initialization. Both use channel 1, matching the pedal OTA radio arrangement.

| Setting | Handbrake OTA |
|---|---|
| Wi-Fi SSID | `GamePadPro-Handbrake-OTA` |
| Password | `GPPedalsOTA8264` |
| Address | `http://192.168.4.1/` |
| Initial window | 60 seconds |
| Upload | Browser-based ESP32-C3 `.bin` upload |
| Completion | Firmware verification, success page, automatic reboot |

The OTA window stays active after 60 seconds while a PC remains connected or an upload is in progress. Otherwise, the temporary access point closes. Reboot the C3 to open another OTA window. Connect to the handbrake SSID (not the pedals SSID), open the address above, select a firmware binary compiled for the ESP32-C3 handbrake board, and upload it. Do not remove power during flashing.

The pedal OTA code and credentials are not changed. The handbrake uses a distinct SSID so the two boards are easy to identify. OTA is independent of the Receiver S3 and does not use GPIO25.

## Wiring

### Shifter switches
| Function | ESP32-C3 | Wiring | USB result |
|---|---:|---|---|
| Shift Up | GPIO4 | momentary switch to GND | Button 30 |
| Shift Down | GPIO5 | momentary switch to GND | Button 31 |
| AUX | GPIO6 | momentary switch to GND | Button 32 |

### Hall sensor
| Hall connection | ESP32-C3 |
|---|---|
| Signal | GPIO0 |
| GND | GND |
| Supply | 3.3 V when supported by the Hall sensor |

GPIO0 must remain within 0..3.3 V. Never connect a 5 V analog output directly to the C3.

### HX711 + load cell
| HX711 | ESP32-C3 |
|---|---|
| VCC | 3.3 V |
| GND | GND |
| DAT / DOUT | GPIO1 |
| CLK / SCK | GPIO2 |

Connect the load cell to the HX711 excitation/signal terminals according to the board markings (E+, E-, A+, A-). Wire colours are not universal. No external HX711 Arduino library is required.

## Runtime configuration in Wheel Companion

Open the Handbrake controls and choose Hall or HX711. Settings are sent through USB to the Receiver S3, forwarded over ESP-NOW to this C3, and stored in NVS: sensor type, capacity, maximum force, counts/kg, filter divisor, inversion, tare and known-force calibration. Readback and result status are also available.

For HX711, release the handbrake before TARE. For known-force calibration, tare first, apply a measured force, enter that force in kg, and select CALIBRATE. Hall mode does not use load-cell tare or force calibration. The C3 uses stored tare on boot; if no tare has been saved, it performs an initial tare, so keep the handbrake released during that first boot.

## ESP-NOW pairing

The C3 sends to the Receiver MAC in its `Secrets.h`. The Receiver must have this C3's STA MAC in `SHIFTER_MAC` in Receiver `Secrets.h`. Both devices must use the same ESP-NOW channel.

## Compatibility safeguards

- Existing 19-byte shifter/handbrake telemetry packet remains unchanged.
- Shift Up / Shift Down / AUX remain buttons 30 / 31 / 32.
- Handbrake remains the same normalized 0..4095 channel.
- Pedal sensor configuration frames and pedal OTA implementation remain unchanged.
- Runtime sensor configuration uses the separate HB/HS protocol with CRC-8/ATM.
