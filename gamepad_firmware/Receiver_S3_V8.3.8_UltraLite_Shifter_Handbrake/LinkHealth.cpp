#include "LinkHealth.h"

#include "Config.h"
#include "ESPNowManager.h"
#include "RaceEngineerTelemetry.h"

namespace
{
// Legacy RS/V1: exact V8.3.1 format, always transmitted.
constexpr uint8_t LEGACY_MAGIC0 = 0x52; // R
constexpr uint8_t LEGACY_MAGIC1 = 0x53; // S
constexpr uint8_t LEGACY_VERSION = 1;
constexpr size_t LEGACY_FRAME_SIZE = 25;
constexpr uint32_t LEGACY_STATUS_INTERVAL_MS = 500;

// Wheel Companion leased live values.
constexpr uint8_t LIVE_MAGIC0 = 0x57; // W
constexpr uint8_t LIVE_MAGIC1 = 0x4C; // L
constexpr uint8_t LIVE_VERSION_V1 = 1;
constexpr uint8_t LIVE_VERSION_V2 = 2;
constexpr uint8_t LIVE_VERSION_V3 = 3;
constexpr size_t LIVE_V1_FRAME_SIZE = 10; // exact V8.3.5
constexpr size_t LIVE_V2_FRAME_SIZE = 12; // + clutch uint16
constexpr size_t LIVE_V3_FRAME_SIZE = 14; // + handbrake uint16
constexpr uint32_t LIVE_STATUS_INTERVAL_MS = 100;

constexpr uint8_t FLAG_WHEEL = 1u << 0;
constexpr uint8_t FLAG_PEDALS = 1u << 1;
constexpr uint8_t FLAG_MOTOR_TEMP = 1u << 2;
constexpr uint8_t FLAG_RACE_ENGINEER = 1u << 3;
constexpr uint16_t PEDAL_RAW_INVALID = 0xFFFFu;
constexpr int16_t MOTOR_TEMP_INVALID_CX100 = static_cast<int16_t>(-32768);

uint32_t lastLegacyStatusMs = 0;
uint32_t lastLiveStatusMs = 0;

uint8_t crc8Atm(const uint8_t* data, size_t len)
{
    uint8_t crc = 0;
    for (size_t i = 0; i < len; ++i)
    {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; ++bit)
        {
            crc = (crc & 0x80u) ? static_cast<uint8_t>((crc << 1u) ^ 0x07u)
                                : static_cast<uint8_t>(crc << 1u);
        }
    }
    return crc;
}

uint16_t clampAge(uint32_t age)
{
    return age > 65535u ? 65535u : static_cast<uint16_t>(age);
}

void putU16(uint8_t* out, size_t offset, uint16_t value)
{
    out[offset] = static_cast<uint8_t>(value & 0xFFu);
    out[offset + 1] = static_cast<uint8_t>((value >> 8u) & 0xFFu);
}

void putI16(uint8_t* out, size_t offset, int16_t value)
{
    putU16(out, offset, static_cast<uint16_t>(value));
}

void putU32(uint8_t* out, size_t offset, uint32_t value)
{
    out[offset] = static_cast<uint8_t>(value & 0xFFu);
    out[offset + 1] = static_cast<uint8_t>((value >> 8u) & 0xFFu);
    out[offset + 2] = static_cast<uint8_t>((value >> 16u) & 0xFFu);
    out[offset + 3] = static_cast<uint8_t>((value >> 24u) & 0xFFu);
}

void sendLegacyStatus(uint32_t now)
{
    const ReceiverNetworkState& network = ESPNow::getNetworkState();
    uint8_t flags = 0;
    if (ESPNow::wheelConnected()) flags |= FLAG_WHEEL;
    if (ESPNow::pedalsConnected()) flags |= FLAG_PEDALS;
    if (ESPNow::motorTempConnected()) flags |= FLAG_MOTOR_TEMP;
    if (RaceEngineerTelemetry::hasData()) flags |= FLAG_RACE_ENGINEER;

    uint8_t frame[LEGACY_FRAME_SIZE] = {};
    frame[0] = LEGACY_MAGIC0;
    frame[1] = LEGACY_MAGIC1;
    frame[2] = LEGACY_VERSION;
    frame[3] = flags;

    const uint16_t wheelAge = network.wheel.lastPacketTime == 0 ? 65535u : clampAge(now - network.wheel.lastPacketTime);
    const uint16_t pedalAge = network.pedals.lastPacketTime == 0 ? 65535u : clampAge(now - network.pedals.lastPacketTime);
    const uint16_t motorAge = network.motorTemp.lastPacketTime == 0 ? 65535u : clampAge(now - network.motorTemp.lastPacketTime);
    const uint16_t reAge = clampAge(RaceEngineerTelemetry::lastPacketAgeMs());

    putU16(frame, 4, wheelAge);
    putU16(frame, 6, pedalAge);
    putU16(frame, 8, motorAge);
    putU16(frame, 10, reAge);
    putU32(frame, 12, ESPNow::wheelPackets());
    putU32(frame, 16, ESPNow::pedalPackets());
    putU32(frame, 20, ESPNow::motorTempPackets());
    frame[24] = crc8Atm(frame, LEGACY_FRAME_SIZE - 1);
    Serial.write(frame, sizeof(frame));
}

void sendWheelCompanionLiveValues(uint8_t version)
{
    const bool pedalsConnected = ESPNow::pedalsConnected();
    const bool motorTempConnected = ESPNow::motorTempConnected();
    const PedalPayload& pedals = ESPNow::getPedalData();
    const MotorTempPayload& motor = ESPNow::getMotorTempData();
    const ShifterPayload& shifter = ESPNow::getShifterData();
    const bool shifterConnected = ESPNow::shifterConnected();

    const uint16_t throttleRaw = pedalsConnected ? pedals.throttle : PEDAL_RAW_INVALID;
    const uint16_t brakeRaw = pedalsConnected ? pedals.brake : PEDAL_RAW_INVALID;
    const uint16_t clutchRaw = pedalsConnected ? pedals.clutch : PEDAL_RAW_INVALID;
    const uint16_t handbrakeRaw = shifterConnected ? shifter.handbrake : PEDAL_RAW_INVALID;
    const int16_t motorTempCx100 = (motorTempConnected && motor.valid != 0)
        ? motor.tempCx100 : MOTOR_TEMP_INVALID_CX100;

    if (version < LIVE_VERSION_V2)
    {
        // Byte-for-byte V8.3.5 WL/V1.
        uint8_t frame[LIVE_V1_FRAME_SIZE] = {};
        frame[0] = LIVE_MAGIC0;
        frame[1] = LIVE_MAGIC1;
        frame[2] = LIVE_VERSION_V1;
        putU16(frame, 3, throttleRaw);
        putU16(frame, 5, brakeRaw);
        putI16(frame, 7, motorTempCx100);
        frame[9] = crc8Atm(frame, LIVE_V1_FRAME_SIZE - 1);
        Serial.write(frame, sizeof(frame));
        return;
    }

    if (version < LIVE_VERSION_V3)
    {
        uint8_t frame[LIVE_V2_FRAME_SIZE] = {};
        frame[0] = LIVE_MAGIC0; frame[1] = LIVE_MAGIC1; frame[2] = LIVE_VERSION_V2;
        putU16(frame, 3, throttleRaw); putU16(frame, 5, brakeRaw); putU16(frame, 7, clutchRaw);
        putI16(frame, 9, motorTempCx100);
        frame[11] = crc8Atm(frame, LIVE_V2_FRAME_SIZE - 1);
        Serial.write(frame, sizeof(frame));
        return;
    }

    uint8_t frame[LIVE_V3_FRAME_SIZE] = {};
    frame[0] = LIVE_MAGIC0; frame[1] = LIVE_MAGIC1; frame[2] = LIVE_VERSION_V3;
    putU16(frame, 3, throttleRaw); putU16(frame, 5, brakeRaw); putU16(frame, 7, clutchRaw);
    putU16(frame, 9, handbrakeRaw); putI16(frame, 11, motorTempCx100);
    frame[13] = crc8Atm(frame, LIVE_V3_FRAME_SIZE - 1);
    Serial.write(frame, sizeof(frame));
}
}

void LinkHealth::begin()
{
    lastLegacyStatusMs = 0;
    lastLiveStatusMs = 0;
}

void LinkHealth::update()
{
    const uint32_t now = millis();
    if ((now - lastLegacyStatusMs) >= LEGACY_STATUS_INTERVAL_MS)
    {
        lastLegacyStatusMs = now;
        sendLegacyStatus(now);
    }

    const uint8_t liveVersion = RaceEngineerTelemetry::extendedStatusVersion();
    if (liveVersion != 0)
    {
        if ((now - lastLiveStatusMs) >= LIVE_STATUS_INTERVAL_MS)
        {
            lastLiveStatusMs = now;
            sendWheelCompanionLiveValues(liveVersion);
        }
    }
    else
    {
        lastLiveStatusMs = 0;
    }
}
