/*****************************************************************************/
/* GamePad Pro V8.3.3 - Race Engineer compact telemetry receiver             */
/*                                                                           */
/* Existing PC -> Receiver frame (UNCHANGED):                                */
/*   15 bytes: 'R','E', version 1, sequence, 9-byte dashboard, CRC-8/ATM      */
/*                                                                           */
/* Wheel Companion control frame (new, independent):                         */
/*   5 bytes: 'W','C', version 1, command, CRC-8/ATM                         */
/*   command 1 = enable extended Receiver -> PC live values                  */
/*   command 2 = disable extended live values                                */
/*                                                                           */
/* Both parsers observe the same incoming bytes independently. The added      */
/* control parser therefore cannot alter or consume the proven RE telemetry   */
/* stream.                                                                    */
/*****************************************************************************/

#include "RaceEngineerTelemetry.h"
#include "Config.h"
#include "PedalCalibration.h"

namespace
{
constexpr uint8_t MAGIC0 = 0x52; // R
constexpr uint8_t MAGIC1 = 0x45; // E
constexpr uint8_t VERSION = 1;
constexpr size_t FRAME_SIZE = 15;
constexpr size_t PAYLOAD_OFFSET = 5;

// Wheel Companion opt-in control protocol.
constexpr uint8_t CONTROL_MAGIC0 = 0x57; // W
constexpr uint8_t CONTROL_MAGIC1 = 0x43; // C
constexpr uint8_t CONTROL_VERSION_V1 = 1;
constexpr uint8_t CONTROL_VERSION_V2 = 2;
constexpr uint8_t CONTROL_VERSION_V3 = 3;
constexpr uint8_t CONTROL_ENABLE_EXTENDED = 1;
constexpr uint8_t CONTROL_DISABLE_EXTENDED = 2;
constexpr size_t CONTROL_FRAME_SIZE = 5;
constexpr uint32_t EXTENDED_STATUS_LEASE_MS = 3000;

uint8_t frame[FRAME_SIZE] = {};
size_t framePos = 0;
WheelDashboardPayload dashboard = {};
uint32_t rxPackets = 0;
uint32_t badPackets = 0;
uint32_t lastRxMs = 0;

uint8_t controlFrame[CONTROL_FRAME_SIZE] = {};
size_t controlPos = 0;
uint32_t extendedLeaseUntilMs = 0;
uint8_t extendedLiveVersion = CONTROL_VERSION_V1;

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

void resetParser()
{
    framePos = 0;
}

void resetControlParser()
{
    controlPos = 0;
}

void consumeTelemetry(uint8_t value)
{
    if (framePos == 0)
    {
        if (value == MAGIC0)
        {
            frame[framePos++] = value;
        }
        return;
    }

    if (framePos == 1)
    {
        if (value == MAGIC1)
        {
            frame[framePos++] = value;
        }
        else if (value == MAGIC0)
        {
            frame[0] = MAGIC0;
            framePos = 1;
        }
        else
        {
            resetParser();
        }
        return;
    }

    frame[framePos++] = value;

    if (framePos < FRAME_SIZE)
    {
        return;
    }

    const bool valid = frame[2] == VERSION &&
                       crc8Atm(frame, FRAME_SIZE - 1) == frame[FRAME_SIZE - 1];

    if (valid)
    {
        WheelDashboardPayload parsed = {};
        memcpy(&parsed, &frame[PAYLOAD_OFFSET], sizeof(parsed));

        // Clamp only malformed transport values; normal values pass through
        // unchanged to preserve the existing wheel behaviour.
        if (parsed.rpmPercent <= 100 && parsed.position <= MAX_POSITION &&
            parsed.gear >= -1 && parsed.gear <= static_cast<int8_t>(MAX_GEAR))
        {
            dashboard = parsed;
            lastRxMs = millis();
            ++rxPackets;
        }
        else
        {
            ++badPackets;
        }
    }
    else
    {
        ++badPackets;
    }

    resetParser();
}

void applyControlCommand(uint8_t version, uint8_t command)
{
    if (command == CONTROL_ENABLE_EXTENDED)
    {
        // Lease rather than latch. Ultra Lite sends V1 first for old receivers,
        // then V2. The last valid generation selects the live-value frame.
        extendedLiveVersion = version >= CONTROL_VERSION_V3 ? CONTROL_VERSION_V3 :
                              version >= CONTROL_VERSION_V2 ? CONTROL_VERSION_V2 : CONTROL_VERSION_V1;
        extendedLeaseUntilMs = millis() + EXTENDED_STATUS_LEASE_MS;
    }
    else if (command == CONTROL_DISABLE_EXTENDED)
    {
        extendedLeaseUntilMs = 0;
        extendedLiveVersion = CONTROL_VERSION_V1;
    }
}

void consumeControl(uint8_t value)
{
    if (controlPos == 0)
    {
        if (value == CONTROL_MAGIC0)
        {
            controlFrame[controlPos++] = value;
        }
        return;
    }

    if (controlPos == 1)
    {
        if (value == CONTROL_MAGIC1)
        {
            controlFrame[controlPos++] = value;
        }
        else if (value == CONTROL_MAGIC0)
        {
            controlFrame[0] = CONTROL_MAGIC0;
            controlPos = 1;
        }
        else
        {
            resetControlParser();
        }
        return;
    }

    controlFrame[controlPos++] = value;
    if (controlPos < CONTROL_FRAME_SIZE)
    {
        return;
    }

    const uint8_t version = controlFrame[2];
    const bool valid =
        (version == CONTROL_VERSION_V1 || version == CONTROL_VERSION_V2 || version == CONTROL_VERSION_V3) &&
        crc8Atm(controlFrame, CONTROL_FRAME_SIZE - 1) ==
            controlFrame[CONTROL_FRAME_SIZE - 1];

    if (valid)
    {
        applyControlCommand(version, controlFrame[3]);
    }

    resetControlParser();
}
}

void RaceEngineerTelemetry::begin()
{
    dashboard = {};
    resetParser();
    resetControlParser();
    extendedLeaseUntilMs = 0;
    extendedLiveVersion = CONTROL_VERSION_V1;
}

void RaceEngineerTelemetry::update()
{
    // At 50 Hz the PC telemetry is only 750 bytes/s. The occasional 5-byte
    // Wheel Companion lease frame is negligible. Keep the bounded serial work
    // so USB HID remains first-priority.
    uint8_t budget = 64;
    while (budget-- && Serial.available() > 0)
    {
        const uint8_t value = static_cast<uint8_t>(Serial.read());
        // Independent observers: neither parser removes bytes from the other.
        consumeControl(value);
        PedalCalibration::consumeSerialByte(value);
        consumeTelemetry(value);
    }
}

const WheelDashboardPayload& RaceEngineerTelemetry::getDashboard()
{
    return dashboard;
}

bool RaceEngineerTelemetry::hasData()
{
    return rxPackets != 0 && (millis() - lastRxMs) <= RACE_ENGINEER_TIMEOUT_MS;
}

uint32_t RaceEngineerTelemetry::packetsReceived()
{
    return rxPackets;
}

uint32_t RaceEngineerTelemetry::invalidPackets()
{
    return badPackets;
}

uint32_t RaceEngineerTelemetry::lastPacketAgeMs()
{
    return rxPackets == 0 ? UINT32_MAX : (millis() - lastRxMs);
}

bool RaceEngineerTelemetry::extendedStatusEnabled()
{
    if (extendedLeaseUntilMs == 0)
    {
        return false;
    }

    // Signed subtraction handles millis() wraparound correctly for short
    // leases (< 2^31 ms).
    return static_cast<int32_t>(extendedLeaseUntilMs - millis()) > 0;
}

uint32_t RaceEngineerTelemetry::extendedStatusLeaseRemainingMs()
{
    if (!extendedStatusEnabled())
    {
        return 0;
    }
    return extendedLeaseUntilMs - millis();
}

uint8_t RaceEngineerTelemetry::extendedStatusVersion()
{
    return extendedStatusEnabled() ? extendedLiveVersion : 0;
}
