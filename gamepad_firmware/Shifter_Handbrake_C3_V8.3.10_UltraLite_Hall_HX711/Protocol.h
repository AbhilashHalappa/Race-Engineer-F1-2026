/******************************************************************************
 * GamePad Pro V8 — Shared ESP-NOW Protocol
 *
 * Canonical source: shared/Protocol.h
 * Sync into each firmware sketch with: shared/scripts/sync-shared.ps1
 *
 * Wire formats (do not change without bumping PROTOCOL_VERSION):
 *   LegacyPacket         = 19 bytes → wheel/pedals/MotorTemp C3 traffic
 *   WheelDashboardPacket = 21 bytes → receiver -> steering-wheel telemetry
 *   Packet               = 77 bytes → LCD display telemetry TX/RX
 ******************************************************************************/

#pragma once

#include <Arduino.h>
#include <stdint.h>
#include <string.h>

//=============================================================================
// Protocol identity
//=============================================================================

constexpr uint8_t PROTOCOL_MAGIC   = 0x47;  // 'G'
constexpr uint8_t PROTOCOL_VERSION = 1;

//=============================================================================
// Packet types
//=============================================================================

enum class PacketType : uint8_t
{
    NONE = 0,
    WHEEL,
    PEDALS,
    DASHBOARD,          // Small telemetry → steering wheel (LegacyPacket)
    LCD_DASHBOARD,      // Reserved for future unicast LCD frames
    HEARTBEAT,
    MOTOR_TEMP,         // ESP32-C3 10K NTC motor temperature → receiver
    SHIFTER             // ESP32-C3 sequential shifter → receiver
};

//=============================================================================
// Device IDs
//=============================================================================

enum class DeviceID : uint8_t
{
    RECEIVER   = 0,
    WHEEL      = 1,
    PEDALS     = 2,
    LCD        = 3,  // Not named DISPLAY — clashes with ESP32 Arduino.h macro
    MOTOR_TEMP = 4,  // Standalone ESP32-C3 + 10K NTC
    SHIFTER    = 5   // Standalone ESP32-C3 sequential shifter
};

//=============================================================================
// Device status
//=============================================================================

enum class DeviceStatus : uint8_t
{
    OK = 0,
    WAITING,
    TIMEOUT,
    ERROR
};

//=============================================================================
// Packet header (10 bytes)
//=============================================================================

struct __attribute__((packed)) PacketHeader
{
    uint8_t magic;
    uint8_t version;
    PacketType type;
    DeviceID source;
    uint16_t sequence;
    uint32_t timestamp;
};

//=============================================================================
// Payloads
//=============================================================================

struct __attribute__((packed)) WheelPayload
{
    uint32_t buttonState;
    uint16_t clutchLeft;
    uint16_t clutchRight;
    uint8_t battery;
};

struct __attribute__((packed)) PedalPayload
{
    uint16_t throttle;
    uint16_t brake;
    // V8.3.6 Ultra Lite: fits in the existing 9-byte LegacyPacket payload
    // window, so the on-air packet remains exactly 19 bytes. Older receivers
    // read only throttle/brake and safely ignore these spare payload bytes.
    uint16_t clutch;
};

// Motor temperature from standalone ESP32-C3 + 10K NTC (fits LegacyPacket union).
// Three momentary shifter inputs plus one analog handbrake on the same ESP32-C3.
// bit 0 = Shift Up, bit 1 = Shift Down, bit 2 = AUX / configurable button.
// handbrake = raw 12-bit ADC value (0..4095). This still fits in the existing
// 9-byte LegacyPacket payload window, so the on-air packet remains 19 bytes.
struct __attribute__((packed)) ShifterPayload
{
    uint8_t buttonState;
    uint16_t handbrake;
};

struct __attribute__((packed)) MotorTempPayload
{
    int16_t tempCx100; // e.g. 7525 = 75.25 °C
    uint8_t valid;     // 1 = NTC reading OK
};

// Status flags packed into WheelDashboardPayload::statusBits
//
// Layout (avoids clashing with DRS values 2 and 3):
//   bits 7-4 : raw SimHub DRS value (0=off, 2=available, 3=in use)
//   bits 3-2 : legacy motor-temp level (reserved; raw temperature now travels separately)
//   bit  1   : low fuel
//   bit  0   : low ERS energy
namespace WheelStatusBits
{
    constexpr uint8_t LOW_ERS  = 1u << 0;
    constexpr uint8_t LOW_FUEL = 1u << 1;

    constexpr uint8_t MOTOR_TEMP_SHIFT = 2;
    constexpr uint8_t MOTOR_TEMP_MASK  = 0x0Cu; // bits 3-2

    constexpr uint8_t MOTOR_TEMP_OFF  = 0; // no recent reading
    constexpr uint8_t MOTOR_TEMP_OK   = 1; // cool / normal
    constexpr uint8_t MOTOR_TEMP_WARM = 2;
    constexpr uint8_t MOTOR_TEMP_HOT  = 3; // critical — flash on LED 10

    constexpr uint8_t DRS_SHIFT     = 4;
    constexpr uint8_t DRS_MASK      = 0x0Fu;
    constexpr uint8_t DRS_AVAILABLE = 2u;
    constexpr uint8_t DRS_ACTIVE    = 3u;

    inline uint8_t getDrs(uint8_t statusBits)
    {
        return static_cast<uint8_t>((statusBits >> DRS_SHIFT) & DRS_MASK);
    }

    inline uint8_t packDrs(uint8_t drs)
    {
        return static_cast<uint8_t>((drs & DRS_MASK) << DRS_SHIFT);
    }

    inline uint8_t getMotorTempLevel(uint8_t statusBits)
    {
        return static_cast<uint8_t>(
            (statusBits & MOTOR_TEMP_MASK) >> MOTOR_TEMP_SHIFT);
    }

    inline uint8_t packMotorTempLevel(uint8_t level)
    {
        return static_cast<uint8_t>(
            (level & 0x03u) << MOTOR_TEMP_SHIFT);
    }
}

// Legacy compact telemetry for the wheel (9 bytes).
// Kept unchanged so wheel input packets and the MotorTemp C3 remain compatible.
struct __attribute__((packed)) WheelDashboardPayload
{
    uint16_t speed;
    int8_t gear;
    uint8_t position;
    uint8_t rpmPercent;
    uint8_t shiftLight;
    uint8_t flagStatus;
    uint8_t ersMode;
    uint8_t statusBits;   // WheelStatusBits::* (motor-temp bits are now unused)
};

// Extended receiver -> wheel telemetry. The receiver forwards the raw C3
// temperature and the wheel decides the LED colour/thresholds locally.
struct __attribute__((packed)) WheelDashboardExtendedPayload
{
    uint16_t speed;
    int8_t gear;
    uint8_t position;
    uint8_t rpmPercent;
    uint8_t shiftLight;
    uint8_t flagStatus;
    uint8_t ersMode;
    uint8_t statusBits;
    int16_t motorTempCx100;  // 2260 = 22.60 C; MOTOR_TEMP_INVALID_CX100 = stale/invalid
};

constexpr int16_t MOTOR_TEMP_INVALID_CX100 = static_cast<int16_t>(-32768);

// Full telemetry for the LCD dashboard (67 bytes).
struct __attribute__((packed)) DashboardPayload
{
    uint16_t speed;
    int8_t gear;
    uint8_t position;
    uint8_t rpmPercent;
    uint16_t rpm;
    uint8_t shiftLight;
    uint8_t flagStatus;
    uint8_t ersMode;

    uint8_t ersBattery;
    uint8_t drs;
    uint8_t pitLimiter;

    uint16_t currentLap;
    uint16_t totalLaps;

    uint32_t currentLapMs;
    uint32_t lastLapMs;
    uint32_t bestLapMs;
    int32_t deltaMs;

    uint8_t diff;
    uint8_t brakeBias;
    uint8_t engineBrake;
    uint8_t fuelMix;
    uint8_t engineMap;
    uint8_t fuelPercent;

    uint8_t tyreWear[4];
    uint16_t tyreTemp[4];
    uint16_t tyrePressureX10[4];
    uint16_t brakeTemp[4];
};

struct __attribute__((packed)) HeartbeatPayload
{
    uint16_t battery;
    int8_t rssi;
    DeviceStatus status;
};

// Dedicated receiver -> steering-wheel frame. It is intentionally separate
// from LegacyPacket so the existing 19-byte wheel/C3 packets do not change.
struct __attribute__((packed)) WheelDashboardPacket
{
    PacketHeader header;
    WheelDashboardExtendedPayload dashboard;
};

//=============================================================================
// Full LCD packet (77 bytes)
//=============================================================================

constexpr size_t MAX_PAYLOAD_SIZE = sizeof(DashboardPayload);

struct __attribute__((packed)) Packet
{
    PacketHeader header;

    union
    {
        WheelPayload wheel;
        PedalPayload pedals;
        WheelDashboardPayload wheelDashboard;
        DashboardPayload dashboard;
        HeartbeatPayload heartbeat;
        MotorTempPayload motorTemp;
        ShifterPayload shifter;
        uint8_t raw[MAX_PAYLOAD_SIZE];
    };
};

//=============================================================================
// Legacy wheel/pedal packet (19 bytes)
//=============================================================================

constexpr size_t LEGACY_PAYLOAD_SIZE = sizeof(WheelPayload);

struct __attribute__((packed)) LegacyPacket
{
    PacketHeader header;

    union
    {
        WheelPayload wheel;
        PedalPayload pedals;
        WheelDashboardPayload dashboard;
        HeartbeatPayload heartbeat;
        MotorTempPayload motorTemp;
        ShifterPayload shifter;
        uint8_t raw[LEGACY_PAYLOAD_SIZE];
    };
};

static_assert(sizeof(ShifterPayload) == 3, "Shifter+handbrake payload must remain 3 bytes");
static_assert(sizeof(LegacyPacket) == 19, "Legacy ESP-NOW packet must remain 19 bytes");

//=============================================================================
// Helpers
//=============================================================================

inline void initPacket(Packet& packet,
                       PacketType type,
                       DeviceID source,
                       uint16_t sequence)
{
    memset(&packet, 0, sizeof(Packet));
    packet.header.magic     = PROTOCOL_MAGIC;
    packet.header.version   = PROTOCOL_VERSION;
    packet.header.type      = type;
    packet.header.source    = source;
    packet.header.sequence  = sequence;
    packet.header.timestamp = millis();
}

inline void initLegacyPacket(LegacyPacket& packet,
                             PacketType type,
                             DeviceID source,
                             uint16_t sequence)
{
    memset(&packet, 0, sizeof(LegacyPacket));
    packet.header.magic     = PROTOCOL_MAGIC;
    packet.header.version   = PROTOCOL_VERSION;
    packet.header.type      = type;
    packet.header.source    = source;
    packet.header.sequence  = sequence;
    packet.header.timestamp = millis();
}

inline void initWheelDashboardPacket(WheelDashboardPacket& packet,
                                     uint16_t sequence)
{
    memset(&packet, 0, sizeof(WheelDashboardPacket));
    packet.header.magic     = PROTOCOL_MAGIC;
    packet.header.version   = PROTOCOL_VERSION;
    packet.header.type      = PacketType::DASHBOARD;
    packet.header.source    = DeviceID::RECEIVER;
    packet.header.sequence  = sequence;
    packet.header.timestamp = millis();
    packet.dashboard.motorTempCx100 = MOTOR_TEMP_INVALID_CX100;
}

inline bool validatePacketHeader(const PacketHeader& header)
{
    return (header.magic == PROTOCOL_MAGIC) &&
           (header.version == PROTOCOL_VERSION);
}

inline bool validatePacket(const Packet& packet)
{
    return validatePacketHeader(packet.header);
}

inline bool validateLegacyPacket(const LegacyPacket& packet)
{
    return validatePacketHeader(packet.header);
}

// Project a full LCD dashboard snapshot into the compact wheel frame.
inline WheelDashboardPayload toWheelDashboard(const DashboardPayload& src)
{
    WheelDashboardPayload dst = {};
    dst.speed      = src.speed;
    dst.gear       = src.gear;
    dst.position   = src.position;
    dst.rpmPercent = src.rpmPercent;
    dst.shiftLight = src.shiftLight;
    dst.flagStatus = src.flagStatus;
    dst.ersMode    = src.ersMode;

    uint8_t bits = 0;

    // SimHub DRS lives in the high nibble (0 / 2 / 3).
    if (src.drs == WheelStatusBits::DRS_AVAILABLE ||
        src.drs == WheelStatusBits::DRS_ACTIVE)
    {
        bits |= WheelStatusBits::packDrs(src.drs);
    }

    // Treat 1..threshold as low (0 often means "no data")
    if (src.fuelPercent >= 1 && src.fuelPercent <= 15)
    {
        bits |= WheelStatusBits::LOW_FUEL;
    }

    if (src.ersBattery >= 1 && src.ersBattery <= 20)
    {
        bits |= WheelStatusBits::LOW_ERS;
    }

    // bits 3-2 are intentionally left clear. Raw motor temperature is
    // forwarded separately in WheelDashboardExtendedPayload.

    dst.statusBits = bits;
    return dst;
}

inline WheelDashboardExtendedPayload toWheelDashboardExtended(const DashboardPayload& src)
{
    const WheelDashboardPayload base = toWheelDashboard(src);

    WheelDashboardExtendedPayload dst = {};
    dst.speed          = base.speed;
    dst.gear           = base.gear;
    dst.position       = base.position;
    dst.rpmPercent     = base.rpmPercent;
    dst.shiftLight     = base.shiftLight;
    dst.flagStatus     = base.flagStatus;
    dst.ersMode        = base.ersMode;
    dst.statusBits     = base.statusBits;
    dst.motorTempCx100 = MOTOR_TEMP_INVALID_CX100;
    return dst;
}

//=============================================================================
// Compile-time layout checks (protects future edits)
//=============================================================================

static_assert(sizeof(PacketHeader) == 10, "PacketHeader size mismatch");
static_assert(sizeof(WheelPayload) == 9, "WheelPayload size mismatch");
static_assert(sizeof(PedalPayload) == 6, "PedalPayload size mismatch");
static_assert(sizeof(MotorTempPayload) == 3, "MotorTempPayload size mismatch");
static_assert(sizeof(ShifterPayload) == 3, "ShifterPayload size mismatch");
static_assert(sizeof(WheelDashboardPayload) == 9, "WheelDashboardPayload size mismatch");
static_assert(sizeof(WheelDashboardExtendedPayload) == 11, "WheelDashboardExtendedPayload size mismatch");
static_assert(sizeof(WheelDashboardPacket) == 21, "WheelDashboardPacket size mismatch");
static_assert(sizeof(DashboardPayload) == 67, "DashboardPayload size mismatch");
static_assert(sizeof(LegacyPacket) == 19, "LegacyPacket size mismatch");
static_assert(sizeof(Packet) == sizeof(PacketHeader) + MAX_PAYLOAD_SIZE,
              "Packet size mismatch");
