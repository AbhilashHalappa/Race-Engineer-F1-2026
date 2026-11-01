#pragma once
#include <Arduino.h>

constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint32_t TELEMETRY_TIMEOUT_MS = 300;
constexpr uint32_t SHIFT_FLASH_PERIOD_MS = 100;
constexpr uint8_t LED_COUNT = 60;
constexpr uint8_t LED_BRIGHTNESS = 70;

#define ENABLE_OTA 1
#if ENABLE_OTA
constexpr uint32_t OTA_WINDOW_MS = 60000;
constexpr char OTA_AP_SSID[] = "GamePadPro-RPM-LED-OTA";
constexpr char OTA_AP_PASSWORD[] = "GPRpmLedOTA8264";
constexpr uint16_t OTA_HTTP_PORT = 80;
#endif
