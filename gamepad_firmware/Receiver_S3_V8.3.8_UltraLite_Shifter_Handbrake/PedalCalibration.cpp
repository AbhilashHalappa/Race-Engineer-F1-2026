#include "PedalCalibration.h"

#include <Preferences.h>

namespace
{
constexpr uint8_t FRAME_MAGIC0 = 0x50; // P
constexpr uint8_t FRAME_MAGIC1 = 0x43; // C
constexpr uint8_t FRAME_VERSION_V1 = 1;
constexpr uint8_t FRAME_VERSION_V2 = 2;
constexpr uint8_t FRAME_VERSION_V3 = 3;
constexpr size_t COMMAND_V1_FRAME_SIZE = 21;
constexpr size_t COMMAND_V2_FRAME_SIZE = 30;
constexpr size_t COMMAND_V3_FRAME_SIZE = 38;
constexpr size_t COMMAND_MAX_FRAME_SIZE = COMMAND_V3_FRAME_SIZE;

constexpr uint8_t RESPONSE_MAGIC0 = 0x50; // P
constexpr uint8_t RESPONSE_MAGIC1 = 0x53; // S
constexpr size_t RESPONSE_V1_FRAME_SIZE = 20;
constexpr size_t RESPONSE_V2_FRAME_SIZE = 29;
constexpr size_t RESPONSE_V3_FRAME_SIZE = 37;

constexpr uint8_t CMD_APPLY_VOLATILE = 1;
constexpr uint8_t CMD_SAVE = 2;
constexpr uint8_t CMD_REQUEST = 3;
constexpr uint8_t CMD_RESET_DEFAULTS = 4;
constexpr uint8_t FLAG_CLUTCH_ENABLED = 1u << 0;
constexpr uint8_t FLAG_HANDBRAKE_ENABLED = 1u << 1;

constexpr uint16_t RAW_MAX = 4095;
constexpr uint8_t MAX_DEADZONE_PERCENT = 30;
constexpr uint8_t PERSIST_VERSION_V1 = 1;
constexpr uint8_t PERSIST_VERSION_V2 = 2;
constexpr uint8_t PERSIST_VERSION_V3 = 3;

Preferences preferences;
PedalCalibration::Settings settings = {};
uint8_t frame[COMMAND_MAX_FRAME_SIZE] = {};
size_t framePos = 0;
size_t expectedFrameSize = 0;

struct __attribute__((packed)) LegacySettings
{
    PedalCalibration::AxisSettings throttle;
    PedalCalibration::AxisSettings brake;
};

struct __attribute__((packed)) PersistedSettingsV1
{
    uint8_t version;
    LegacySettings settings;
};

struct __attribute__((packed)) PersistedSettingsV2Legacy
{
    uint8_t version;
    PedalCalibration::AxisSettings throttle;
    PedalCalibration::AxisSettings brake;
    PedalCalibration::AxisSettings clutch;
    uint8_t clutchEnabled;
};

struct __attribute__((packed)) PersistedSettingsV3
{
    uint8_t version;
    PedalCalibration::Settings settings;
};

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

void setLinear(PedalCalibration::AxisSettings& axis)
{
    axis.bottomDeadzonePercent = 0;
    axis.topDeadzonePercent = 0;
    for (uint8_t i = 0; i < 6; ++i)
    {
        axis.outputPercent[i] = static_cast<uint8_t>(i * 20u);
    }
}

void setDefaults(PedalCalibration::Settings& out)
{
    setLinear(out.throttle);
    setLinear(out.brake);
    setLinear(out.clutch);
    setLinear(out.handbrake);
    out.clutchEnabled = 0;
    out.handbrakeEnabled = 0;
}

void sanitizeAxis(PedalCalibration::AxisSettings& axis)
{
    axis.bottomDeadzonePercent = min(axis.bottomDeadzonePercent, MAX_DEADZONE_PERCENT);
    axis.topDeadzonePercent = min(axis.topDeadzonePercent, MAX_DEADZONE_PERCENT);
    if (static_cast<uint16_t>(axis.bottomDeadzonePercent) + axis.topDeadzonePercent >= 95u)
    {
        axis.topDeadzonePercent = static_cast<uint8_t>(94u - axis.bottomDeadzonePercent);
    }
    uint8_t previous = 0;
    for (uint8_t i = 0; i < 6; ++i)
    {
        uint8_t value = axis.outputPercent[i] > 100u ? 100u : axis.outputPercent[i];
        if (i > 0 && value < previous)
        {
            value = previous;
        }
        axis.outputPercent[i] = value;
        previous = value;
    }
}

void sanitize(PedalCalibration::Settings& value)
{
    sanitizeAxis(value.throttle);
    sanitizeAxis(value.brake);
    sanitizeAxis(value.clutch);
    sanitizeAxis(value.handbrake);
    value.clutchEnabled = value.clutchEnabled ? 1u : 0u;
    value.handbrakeEnabled = value.handbrakeEnabled ? 1u : 0u;
}

void saveToNvs()
{
    PersistedSettingsV3 stored = {};
    stored.version = PERSIST_VERSION_V3;
    stored.settings = settings;
    preferences.putBytes("curve_v3", &stored, sizeof(stored));
}

void loadFromNvs()
{
    setDefaults(settings);

    if (preferences.getBytesLength("curve_v3") == sizeof(PersistedSettingsV3))
    {
        PersistedSettingsV3 stored = {};
        if (preferences.getBytes("curve_v3", &stored, sizeof(stored)) == sizeof(stored) &&
            stored.version == PERSIST_VERSION_V3)
        {
            settings = stored.settings;
            sanitize(settings);
            return;
        }
    }

    if (preferences.getBytesLength("curve_v2") == sizeof(PersistedSettingsV2Legacy))
    {
        PersistedSettingsV2Legacy stored = {};
        if (preferences.getBytes("curve_v2", &stored, sizeof(stored)) == sizeof(stored) &&
            stored.version == PERSIST_VERSION_V2)
        {
            settings.throttle = stored.throttle;
            settings.brake = stored.brake;
            settings.clutch = stored.clutch;
            settings.clutchEnabled = stored.clutchEnabled;
            setLinear(settings.handbrake);
            settings.handbrakeEnabled = 0;
            sanitize(settings);
            return;
        }
    }

    // Automatic migration from the exact V8.3.4/V8.3.5 curve_v1 record.
    if (preferences.getBytesLength("curve_v1") == sizeof(PersistedSettingsV1))
    {
        PersistedSettingsV1 stored = {};
        if (preferences.getBytes("curve_v1", &stored, sizeof(stored)) == sizeof(stored) &&
            stored.version == PERSIST_VERSION_V1)
        {
            settings.throttle = stored.settings.throttle;
            settings.brake = stored.settings.brake;
            setLinear(settings.clutch);
            settings.clutchEnabled = 0;
            setLinear(settings.handbrake);
            settings.handbrakeEnabled = 0;
            sanitize(settings);
        }
    }
}

void encodeAxis(uint8_t* out, size_t offset, const PedalCalibration::AxisSettings& axis)
{
    out[offset] = axis.bottomDeadzonePercent;
    out[offset + 1] = axis.topDeadzonePercent;
    for (uint8_t i = 0; i < 6; ++i)
    {
        out[offset + 2 + i] = axis.outputPercent[i];
    }
}

void decodeAxis(const uint8_t* in, size_t offset, PedalCalibration::AxisSettings& axis)
{
    axis.bottomDeadzonePercent = in[offset];
    axis.topDeadzonePercent = in[offset + 1];
    for (uint8_t i = 0; i < 6; ++i)
    {
        axis.outputPercent[i] = in[offset + 2 + i];
    }
}

void sendSettings(uint8_t version)
{
    if (version == FRAME_VERSION_V1)
    {
        uint8_t out[RESPONSE_V1_FRAME_SIZE] = {};
        out[0] = RESPONSE_MAGIC0;
        out[1] = RESPONSE_MAGIC1;
        out[2] = FRAME_VERSION_V1;
        encodeAxis(out, 3, settings.throttle);
        encodeAxis(out, 11, settings.brake);
        out[19] = crc8Atm(out, RESPONSE_V1_FRAME_SIZE - 1);
        Serial.write(out, sizeof(out));
        return;
    }

    if (version == FRAME_VERSION_V2)
    {
        uint8_t out[RESPONSE_V2_FRAME_SIZE] = {};
        out[0] = RESPONSE_MAGIC0;
        out[1] = RESPONSE_MAGIC1;
        out[2] = FRAME_VERSION_V2;
        out[3] = settings.clutchEnabled ? FLAG_CLUTCH_ENABLED : 0;
        encodeAxis(out, 4, settings.throttle);
        encodeAxis(out, 12, settings.brake);
        encodeAxis(out, 20, settings.clutch);
        out[28] = crc8Atm(out, RESPONSE_V2_FRAME_SIZE - 1);
        Serial.write(out, sizeof(out));
        return;
    }

    uint8_t out[RESPONSE_V3_FRAME_SIZE] = {};
    out[0] = RESPONSE_MAGIC0;
    out[1] = RESPONSE_MAGIC1;
    out[2] = FRAME_VERSION_V3;
    out[3] = (settings.clutchEnabled ? FLAG_CLUTCH_ENABLED : 0) |
             (settings.handbrakeEnabled ? FLAG_HANDBRAKE_ENABLED : 0);
    encodeAxis(out, 4, settings.throttle);
    encodeAxis(out, 12, settings.brake);
    encodeAxis(out, 20, settings.clutch);
    encodeAxis(out, 28, settings.handbrake);
    out[36] = crc8Atm(out, RESPONSE_V3_FRAME_SIZE - 1);
    Serial.write(out, sizeof(out));
}

uint16_t applyAxis(uint16_t raw, const PedalCalibration::AxisSettings& axis)
{
    raw = raw > RAW_MAX ? RAW_MAX : raw;
    const uint32_t bottomRaw = (static_cast<uint32_t>(RAW_MAX) * axis.bottomDeadzonePercent) / 100u;
    const uint32_t topRaw = RAW_MAX - (static_cast<uint32_t>(RAW_MAX) * axis.topDeadzonePercent) / 100u;

    uint32_t normalizedX100 = 0;
    if (raw <= bottomRaw)
    {
        normalizedX100 = 0;
    }
    else if (raw >= topRaw || topRaw <= bottomRaw)
    {
        normalizedX100 = 10000;
    }
    else
    {
        normalizedX100 = (static_cast<uint32_t>(raw - bottomRaw) * 10000u) /
                         static_cast<uint32_t>(topRaw - bottomRaw);
    }

    uint8_t segment = static_cast<uint8_t>(normalizedX100 / 2000u);
    if (segment >= 5)
    {
        segment = 4;
        normalizedX100 = 10000;
    }
    const uint32_t segmentStart = static_cast<uint32_t>(segment) * 2000u;
    const uint32_t within = normalizedX100 - segmentStart;
    const uint32_t y0 = static_cast<uint32_t>(axis.outputPercent[segment]) * 100u;
    const uint32_t y1 = static_cast<uint32_t>(axis.outputPercent[segment + 1]) * 100u;
    const uint32_t y = y0 + ((y1 - y0) * within) / 2000u;
    return static_cast<uint16_t>((y * RAW_MAX + 5000u) / 10000u);
}

void applyCommand(uint8_t version, uint8_t command)
{
    if (command == CMD_REQUEST)
    {
        sendSettings(version);
        return;
    }

    if (command == CMD_RESET_DEFAULTS)
    {
        if (version == FRAME_VERSION_V1)
        {
            // An older Wheel Companion may reset T/B without disturbing a
            // separately configured V2 clutch.
            setLinear(settings.throttle);
            setLinear(settings.brake);
        }
        else if (version == FRAME_VERSION_V2)
        {
            setLinear(settings.throttle); setLinear(settings.brake); setLinear(settings.clutch);
            settings.clutchEnabled = 0;
        }
        else
        {
            setDefaults(settings);
        }
        sendSettings(version);
        return;
    }

    if (version == FRAME_VERSION_V1)
    {
        decodeAxis(frame, 4, settings.throttle);
        decodeAxis(frame, 12, settings.brake);
    }
    else if (version == FRAME_VERSION_V2)
    {
        settings.clutchEnabled = (frame[4] & FLAG_CLUTCH_ENABLED) ? 1u : 0u;
        decodeAxis(frame, 5, settings.throttle);
        decodeAxis(frame, 13, settings.brake);
        decodeAxis(frame, 21, settings.clutch);
    }
    else
    {
        settings.clutchEnabled = (frame[4] & FLAG_CLUTCH_ENABLED) ? 1u : 0u;
        settings.handbrakeEnabled = (frame[4] & FLAG_HANDBRAKE_ENABLED) ? 1u : 0u;
        decodeAxis(frame, 5, settings.throttle);
        decodeAxis(frame, 13, settings.brake);
        decodeAxis(frame, 21, settings.clutch);
        decodeAxis(frame, 29, settings.handbrake);
    }
    sanitize(settings);

    if (command == CMD_SAVE)
    {
        saveToNvs();
    }
    if (command == CMD_APPLY_VOLATILE || command == CMD_SAVE)
    {
        sendSettings(version);
    }
}

void resetFrame()
{
    framePos = 0;
    expectedFrameSize = 0;
}
}

void PedalCalibration::begin()
{
    preferences.begin("pedalcurve", false);
    loadFromNvs();
    resetFrame();
}

void PedalCalibration::consumeSerialByte(uint8_t value)
{
    if (framePos == 0)
    {
        if (value == FRAME_MAGIC0)
        {
            frame[framePos++] = value;
        }
        return;
    }

    if (framePos == 1)
    {
        if (value == FRAME_MAGIC1)
        {
            frame[framePos++] = value;
        }
        else if (value == FRAME_MAGIC0)
        {
            frame[0] = FRAME_MAGIC0;
            framePos = 1;
        }
        else
        {
            resetFrame();
        }
        return;
    }

    frame[framePos++] = value;

    if (framePos == 3)
    {
        expectedFrameSize = frame[2] == FRAME_VERSION_V1 ? COMMAND_V1_FRAME_SIZE :
                            frame[2] == FRAME_VERSION_V2 ? COMMAND_V2_FRAME_SIZE :
                            frame[2] == FRAME_VERSION_V3 ? COMMAND_V3_FRAME_SIZE : 0;
        if (expectedFrameSize == 0)
        {
            resetFrame();
            return;
        }
    }

    if (expectedFrameSize == 0 || framePos < expectedFrameSize)
    {
        return;
    }

    const bool valid = crc8Atm(frame, expectedFrameSize - 1) == frame[expectedFrameSize - 1];
    if (valid)
    {
        const uint8_t command = frame[3];
        if (command >= CMD_APPLY_VOLATILE && command <= CMD_RESET_DEFAULTS)
        {
            applyCommand(frame[2], command);
        }
    }
    resetFrame();
}

uint16_t PedalCalibration::applyThrottle(uint16_t raw)
{
    return applyAxis(raw, settings.throttle);
}

uint16_t PedalCalibration::applyBrake(uint16_t raw)
{
    return applyAxis(raw, settings.brake);
}

uint16_t PedalCalibration::applyClutch(uint16_t raw)
{
    return applyAxis(raw, settings.clutch);
}

bool PedalCalibration::clutchEnabled()
{
    return settings.clutchEnabled != 0;
}

const PedalCalibration::Settings& PedalCalibration::getSettings()
{
    return settings;
}

uint16_t PedalCalibration::applyHandbrake(uint16_t raw)
{
    return applyAxis(raw, settings.handbrake);
}

bool PedalCalibration::handbrakeEnabled()
{
    return settings.handbrakeEnabled != 0;
}
