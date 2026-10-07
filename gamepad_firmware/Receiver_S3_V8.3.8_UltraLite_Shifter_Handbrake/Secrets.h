#pragma once

//==============================================================
// Receiver ESP32-S3 Zero MAC Address
// IMPORTANT: replace this value with your S3 Zero Wi-Fi STA MAC.
//==============================================================

// Receiver
constexpr uint8_t RECEIVER_MAC[6] =
{
    0x9C, 0x13, 0x9E, 0xF4, 0x35, 0xB4
};

// LCD Display ESP32-S3 Dev
constexpr uint8_t DISPLAY_MAC[6] =
{
    0x14, 0xC1, 0x9F, 0x3A, 0x04, 0x2C
};

// Wheel
constexpr uint8_t WHEEL_MAC[6] =
{
    0xB4, 0xBF, 0xE9, 0x0E, 0x75, 0xC8
};

// Pedals
constexpr uint8_t PEDALS_MAC[6] =
{
    0xA0, 0xB7, 0x65, 0xDD, 0x85, 0x04
};

// Motor-temp ESP32-C3 (10K NTC) — set to your C3 STA MAC
constexpr uint8_t MOTOR_TEMP_MAC[6] =
{
    0xE0, 0x72, 0xA1, 0x21, 0x4D, 0x74
};

// Sequential-shifter ESP32-C3 Wi-Fi STA MAC.
// Replace this placeholder with the MAC printed by Shifter_C3 at boot.
constexpr uint8_t SHIFTER_MAC[6] =
{
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};
