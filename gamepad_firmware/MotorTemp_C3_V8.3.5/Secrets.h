#pragma once

//==============================================================
// MotorTemp ESP32-C3 — set RECEIVER_MAC to your S3 hub STA MAC.
// After first boot, copy this board's STA MAC into the receiver's
// MOTOR_TEMP_MAC in firmware/Receiver_S3/Secrets.h
//==============================================================

constexpr uint8_t RECEIVER_MAC[6] =
{
    0x9C, 0x13, 0x9E, 0xF4, 0x35, 0xB4
};
