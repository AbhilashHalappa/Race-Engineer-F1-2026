/******************************************************************************
 * Wheel Companion Ultra Lite - Pedal Input Manager
 * Three independent pedal inputs: Analog or HX711 load cell.
 * Legacy PedalPayload remains unchanged (0..4095 per axis).
 ******************************************************************************/
#include "Inputs.h"
#include "Pins.h"
#include "Config.h"
#include <Preferences.h>
#include <math.h>
#include <string.h>

namespace {
struct SensorSettings {
    uint8_t throttleMode;
    uint8_t brakeMode;
    uint8_t clutchMode;
    uint8_t flags;
    uint8_t throttleFilter;
    uint8_t brakeFilter;
    uint8_t clutchFilter;
    float throttleCapacityKg;
    float brakeCapacityKg;
    float clutchCapacityKg;
    float throttleMaxForceKg;
    float brakeMaxForceKg;
    float clutchMaxForceKg;
    float throttleCountsPerKg;
    float brakeCountsPerKg;
    float clutchCountsPerKg;
};

Preferences preferences;
SensorSettings settings{};
PedalPayload pedals{};
float throttleFiltered = 0.0f, brakeFiltered = 0.0f, clutchFiltered = 0.0f;
int32_t throttleTare = 0, brakeTare = 0, clutchTare = 0;
int32_t throttleDelta = 0, brakeDelta = 0, clutchDelta = 0;
bool throttleHasFilter = false, brakeHasFilter = false, clutchHasFilter = false;
uint16_t throttleLast = 0, brakeLast = 0, clutchLast = 0;
uint16_t responseSequence = 0;
bool tarePersistenceFailed = false;

constexpr uint8_t FLAG_THROTTLE_INVERT = 0x01;
constexpr uint8_t FLAG_BRAKE_INVERT = 0x02;
constexpr uint8_t FLAG_CLUTCH_INVERT = 0x04;

bool isAnalog(uint8_t mode) { return mode == static_cast<uint8_t>(PedalSensorMode::ANALOG_INPUT); }
bool isHx711(uint8_t mode) { return mode == static_cast<uint8_t>(PedalSensorMode::HX711); }

void defaults() {
    settings.throttleMode = THROTTLE_SENSOR_MODE == THROTTLE_SENSOR_HX711 ? static_cast<uint8_t>(PedalSensorMode::HX711) : static_cast<uint8_t>(PedalSensorMode::ANALOG_INPUT);
    settings.brakeMode = BRAKE_SENSOR_MODE == BRAKE_SENSOR_HX711 ? static_cast<uint8_t>(PedalSensorMode::HX711) : static_cast<uint8_t>(PedalSensorMode::ANALOG_INPUT);
    settings.clutchMode = CLUTCH_SENSOR_MODE == CLUTCH_SENSOR_HX711 ? static_cast<uint8_t>(PedalSensorMode::HX711) : static_cast<uint8_t>(PedalSensorMode::ANALOG_INPUT);
    settings.flags = (THROTTLE_HX711_INVERT ? FLAG_THROTTLE_INVERT : 0) |
                     (BRAKE_HX711_INVERT ? FLAG_BRAKE_INVERT : 0) |
                     (CLUTCH_HX711_INVERT ? FLAG_CLUTCH_INVERT : 0);
    settings.throttleFilter = THROTTLE_HX711_FILTER_DIVISOR;
    settings.brakeFilter = BRAKE_HX711_FILTER_DIVISOR;
    settings.clutchFilter = CLUTCH_HX711_FILTER_DIVISOR;
    settings.throttleCapacityKg = THROTTLE_LOAD_CELL_CAPACITY_KG;
    settings.brakeCapacityKg = BRAKE_LOAD_CELL_CAPACITY_KG;
    settings.clutchCapacityKg = CLUTCH_LOAD_CELL_CAPACITY_KG;
    settings.throttleMaxForceKg = THROTTLE_MAX_FORCE_KG;
    settings.brakeMaxForceKg = BRAKE_MAX_FORCE_KG;
    settings.clutchMaxForceKg = CLUTCH_MAX_FORCE_KG;
    settings.throttleCountsPerKg = THROTTLE_HX711_COUNTS_PER_KG;
    settings.brakeCountsPerKg = BRAKE_HX711_COUNTS_PER_KG;
    settings.clutchCountsPerKg = CLUTCH_HX711_COUNTS_PER_KG;
}

bool validAxis(float capacity, float maxForce, float counts) {
    return isfinite(capacity) && isfinite(maxForce) && isfinite(counts) &&
           capacity >= 1.0f && capacity <= 1000.0f &&
           maxForce >= 0.1f && maxForce <= capacity &&
           counts >= 1.0f && counts <= 100000000.0f;
}

bool validSettings(const SensorSettings& s) {
    if ((!isAnalog(s.throttleMode) && !isHx711(s.throttleMode)) ||
        (!isAnalog(s.brakeMode) && !isHx711(s.brakeMode)) ||
        (!isAnalog(s.clutchMode) && !isHx711(s.clutchMode))) return false;
    return validAxis(s.throttleCapacityKg, s.throttleMaxForceKg, s.throttleCountsPerKg) &&
           validAxis(s.brakeCapacityKg, s.brakeMaxForceKg, s.brakeCountsPerKg) &&
           validAxis(s.clutchCapacityKg, s.clutchMaxForceKg, s.clutchCountsPerKg);
}

bool saveSettings() {
    const size_t written = preferences.putBytes("sensorcfg", &settings, sizeof(settings));
    if (written != sizeof(settings)) return false;
    SensorSettings verify{};
    return preferences.getBytes("sensorcfg", &verify, sizeof(verify)) == sizeof(verify) &&
           memcmp(&verify, &settings, sizeof(settings)) == 0;
}

bool loadTareValue(const char* key, int32_t& value) {
    if (preferences.getBytesLength(key) != sizeof(value)) return false;
    return preferences.getBytes(key, &value, sizeof(value)) == sizeof(value);
}

bool saveTareValue(const char* key, int32_t value) {
    if (preferences.putBytes(key, &value, sizeof(value)) != sizeof(value)) return false;
    int32_t verify = 0;
    return preferences.getBytes(key, &verify, sizeof(verify)) == sizeof(verify) && verify == value;
}

struct RuntimeSnapshot {
    int32_t throttleTare, brakeTare, clutchTare;
    int32_t throttleDelta, brakeDelta, clutchDelta;
    float throttleFiltered, brakeFiltered, clutchFiltered;
    bool throttleHasFilter, brakeHasFilter, clutchHasFilter;
    uint16_t throttleLast, brakeLast, clutchLast;
    PedalPayload pedals;
};

RuntimeSnapshot snapshotRuntime() {
    return {throttleTare, brakeTare, clutchTare,
            throttleDelta, brakeDelta, clutchDelta,
            throttleFiltered, brakeFiltered, clutchFiltered,
            throttleHasFilter, brakeHasFilter, clutchHasFilter,
            throttleLast, brakeLast, clutchLast, pedals};
}

void restoreRuntime(const RuntimeSnapshot& s) {
    throttleTare=s.throttleTare; brakeTare=s.brakeTare; clutchTare=s.clutchTare;
    throttleDelta=s.throttleDelta; brakeDelta=s.brakeDelta; clutchDelta=s.clutchDelta;
    throttleFiltered=s.throttleFiltered; brakeFiltered=s.brakeFiltered; clutchFiltered=s.clutchFiltered;
    throttleHasFilter=s.throttleHasFilter; brakeHasFilter=s.brakeHasFilter; clutchHasFilter=s.clutchHasFilter;
    throttleLast=s.throttleLast; brakeLast=s.brakeLast; clutchLast=s.clutchLast;
    pedals=s.pedals;
}

void restoreTarePersistence(const RuntimeSnapshot& s) {
    saveTareValue("tare_t", s.throttleTare);
    saveTareValue("tare_b", s.brakeTare);
    saveTareValue("tare_c", s.clutchTare);
}

void loadSettings() {
    defaults();
    if (preferences.getBytesLength("sensorcfg") == sizeof(settings)) {
        SensorSettings stored{};
        if (preferences.getBytes("sensorcfg", &stored, sizeof(stored)) == sizeof(stored) && validSettings(stored)) settings = stored;
    }
}

void configureHx711Pins(uint8_t dataPin, uint8_t clockPin) {
    pinMode(dataPin, INPUT);
    pinMode(clockPin, OUTPUT);
    digitalWrite(clockPin, LOW);
}

void configurePins() {
    analogReadResolution(12);
    analogSetAttenuation(ADC_11db);
    if (isAnalog(settings.throttleMode)) pinMode(THROTTLE_ADC_PIN, INPUT); else configureHx711Pins(THROTTLE_HX711_DATA_PIN, THROTTLE_HX711_CLOCK_PIN);
    if (isAnalog(settings.brakeMode)) pinMode(BRAKE_ADC_PIN, INPUT); else configureHx711Pins(BRAKE_HX711_DATA_PIN, BRAKE_HX711_CLOCK_PIN);
#if ENABLE_CLUTCH_PEDAL
    if (isAnalog(settings.clutchMode)) pinMode(CLUTCH_ADC_PIN, INPUT); else configureHx711Pins(CLUTCH_HX711_DATA_PIN, CLUTCH_HX711_CLOCK_PIN);
#else
    pinMode(CLUTCH_ADC_PIN, INPUT);
#endif
}

bool hxRead(uint8_t dataPin, uint8_t clockPin, int32_t& value) {
    if (digitalRead(dataPin) != LOW) return false;
    uint32_t data = 0;
    noInterrupts();
    for (uint8_t i = 0; i < 24; ++i) {
        digitalWrite(clockPin, HIGH); delayMicroseconds(1);
        data = (data << 1) | (digitalRead(dataPin) ? 1u : 0u);
        digitalWrite(clockPin, LOW); delayMicroseconds(1);
    }
    digitalWrite(clockPin, HIGH); delayMicroseconds(1);
    digitalWrite(clockPin, LOW);
    interrupts();
    if (data & 0x00800000UL) data |= 0xFF000000UL;
    value = static_cast<int32_t>(data);
    return true;
}

bool hxReadTimeout(uint8_t dataPin, uint8_t clockPin, int32_t& value, uint32_t timeoutMs) {
    const uint32_t start = millis();
    while (millis() - start < timeoutMs) {
        if (hxRead(dataPin, clockPin, value)) return true;
        delay(1);
    }
    return false;
}

bool tareOne(uint8_t dataPin, uint8_t clockPin, uint8_t samples, uint32_t timeoutMs, int32_t& offset) {
    int64_t total = 0;
    for (uint8_t i = 0; i < samples; ++i) {
        int32_t raw = 0;
        if (!hxReadTimeout(dataPin, clockPin, raw, timeoutMs)) return false;
        total += raw;
    }
    offset = static_cast<int32_t>(total / samples);
    return true;
}

bool tareThrottle() {
    tarePersistenceFailed = false;
    const int32_t previous = throttleTare;
    if (!tareOne(THROTTLE_HX711_DATA_PIN, THROTTLE_HX711_CLOCK_PIN, THROTTLE_HX711_TARE_SAMPLES, THROTTLE_HX711_READY_TIMEOUT_MS, throttleTare)) return false;
    if (!saveTareValue("tare_t", throttleTare)) { throttleTare=previous; tarePersistenceFailed=true; return false; }
    throttleDelta=0; throttleHasFilter=false; throttleLast=0; return true;
}
bool tareBrake() {
    tarePersistenceFailed = false;
    const int32_t previous = brakeTare;
    if (!tareOne(BRAKE_HX711_DATA_PIN, BRAKE_HX711_CLOCK_PIN, BRAKE_HX711_TARE_SAMPLES, BRAKE_HX711_READY_TIMEOUT_MS, brakeTare)) return false;
    if (!saveTareValue("tare_b", brakeTare)) { brakeTare=previous; tarePersistenceFailed=true; return false; }
    brakeDelta=0; brakeHasFilter=false; brakeLast=0; return true;
}
bool tareClutch() {
    tarePersistenceFailed = false;
    const int32_t previous = clutchTare;
    if (!tareOne(CLUTCH_HX711_DATA_PIN, CLUTCH_HX711_CLOCK_PIN, CLUTCH_HX711_TARE_SAMPLES, CLUTCH_HX711_READY_TIMEOUT_MS, clutchTare)) return false;
    if (!saveTareValue("tare_c", clutchTare)) { clutchTare=previous; tarePersistenceFailed=true; return false; }
    clutchDelta=0; clutchHasFilter=false; clutchLast=0; return true;
}

uint16_t readLoadCell(uint8_t dataPin, uint8_t clockPin, bool invert, uint8_t divisor,
                      float countsPerKg, float maxForceKg, float capacityKg,
                      int32_t tare, int32_t& filtered, bool& hasFilter, uint16_t& last) {
    int32_t raw = 0;
    if (!hxRead(dataPin, clockPin, raw)) return last;
    int32_t delta = raw - tare;
    if (invert) delta = -delta;
    if (delta < 0) delta = 0;
    if (!hasFilter) { filtered = delta; hasFilter = true; }
    else if (divisor <= 1) filtered = delta;
    else filtered += (delta - filtered) / divisor;
    const float force = constrain(maxForceKg, 0.1f, capacityKg);
    const float safeCountsPerKg = countsPerKg > 1.0f ? countsPerKg : 1.0f;
    const float scale = safeCountsPerKg * force;
    int64_t mapped = static_cast<int64_t>((static_cast<double>(filtered) * 4095.0) / scale);
    if (mapped < 0) mapped = 0;
    if (mapped > 4095) mapped = 4095;
    last = static_cast<uint16_t>(mapped);
    return last;
}

uint16_t readAxis(uint8_t mode, uint8_t adcPin, uint8_t hxData, uint8_t hxClock,
                  bool invert, uint8_t divisor, float counts, float force, float capacity,
                  int32_t tare, float& analogFiltered, int32_t& delta, bool& hasFilter, uint16_t& last) {
    if (isHx711(mode)) return readLoadCell(hxData, hxClock, invert, divisor, counts, force, capacity, tare, delta, hasFilter, last);
    analogFiltered = PEDAL_ADC_FILTER_ALPHA * analogRead(adcPin) + (1.0f - PEDAL_ADC_FILTER_ALPHA) * analogFiltered;
    delta = static_cast<int32_t>(constrain(analogFiltered, 0.0f, static_cast<float>(ADC_MAX_VALUE)));
    return static_cast<uint16_t>(delta);
}

uint16_t readThrottle() { return readAxis(settings.throttleMode, THROTTLE_ADC_PIN, THROTTLE_HX711_DATA_PIN, THROTTLE_HX711_CLOCK_PIN, settings.flags & FLAG_THROTTLE_INVERT, settings.throttleFilter, settings.throttleCountsPerKg, settings.throttleMaxForceKg, settings.throttleCapacityKg, throttleTare, throttleFiltered, throttleDelta, throttleHasFilter, throttleLast); }
uint16_t readBrake() { return readAxis(settings.brakeMode, BRAKE_ADC_PIN, BRAKE_HX711_DATA_PIN, BRAKE_HX711_CLOCK_PIN, settings.flags & FLAG_BRAKE_INVERT, settings.brakeFilter, settings.brakeCountsPerKg, settings.brakeMaxForceKg, settings.brakeCapacityKg, brakeTare, brakeFiltered, brakeDelta, brakeHasFilter, brakeLast); }
uint16_t readClutch() {
#if ENABLE_CLUTCH_PEDAL
    return readAxis(settings.clutchMode, CLUTCH_ADC_PIN, CLUTCH_HX711_DATA_PIN, CLUTCH_HX711_CLOCK_PIN, settings.flags & FLAG_CLUTCH_INVERT, settings.clutchFilter, settings.clutchCountsPerKg, settings.clutchMaxForceKg, settings.clutchCapacityKg, clutchTare, clutchFiltered, clutchDelta, clutchHasFilter, clutchLast);
#else
    clutchFiltered = 0.0f; clutchDelta = 0; clutchLast = 0; return 0;
#endif
}

void copySettingsToFrame(PedalSensorFrame& f) {
    f.throttleMode=settings.throttleMode; f.brakeMode=settings.brakeMode; f.clutchMode=settings.clutchMode; f.flags=settings.flags;
    f.throttleFilterDivisor=settings.throttleFilter; f.brakeFilterDivisor=settings.brakeFilter; f.clutchFilterDivisor=settings.clutchFilter;
    f.throttleCapacityKg=settings.throttleCapacityKg; f.brakeCapacityKg=settings.brakeCapacityKg; f.clutchCapacityKg=settings.clutchCapacityKg;
    f.throttleMaxForceKg=settings.throttleMaxForceKg; f.brakeMaxForceKg=settings.brakeMaxForceKg; f.clutchMaxForceKg=settings.clutchMaxForceKg;
    f.throttleCountsPerKg=settings.throttleCountsPerKg; f.brakeCountsPerKg=settings.brakeCountsPerKg; f.clutchCountsPerKg=settings.clutchCountsPerKg;
}

void resetAxisRuntime(bool throttle, bool brake, bool clutch) {
    if (throttle) { throttleTare=0; throttleDelta=0; throttleHasFilter=false; throttleLast=0; }
    if (brake) { brakeTare=0; brakeDelta=0; brakeHasFilter=false; brakeLast=0; }
    if (clutch) { clutchTare=0; clutchDelta=0; clutchHasFilter=false; clutchLast=0; }
}

bool tareAxisIfNeeded(uint8_t mode, bool throttle, bool brake, bool clutch) {
    if (throttle && isHx711(mode)) return tareThrottle();
    if (brake && isHx711(mode)) return tareBrake();
    if (clutch && isHx711(mode)) return tareClutch();
    return true;
}
}

bool Inputs::begin() {
    preferences.begin("pedalsens", false);
    loadSettings();
    configurePins();
    if (isAnalog(settings.throttleMode)) throttleFiltered=analogRead(THROTTLE_ADC_PIN);
    else if (!loadTareValue("tare_t", throttleTare) && !tareThrottle()) return false;
    if (isAnalog(settings.brakeMode)) brakeFiltered=analogRead(BRAKE_ADC_PIN);
    else if (!loadTareValue("tare_b", brakeTare) && !tareBrake()) return false;
#if ENABLE_CLUTCH_PEDAL
    if (isAnalog(settings.clutchMode)) clutchFiltered=analogRead(CLUTCH_ADC_PIN);
    else if (!loadTareValue("tare_c", clutchTare) && !tareClutch()) return false;
#else
    clutchFiltered=0.0f;
#endif
    pedals.throttle=readThrottle(); pedals.brake=readBrake(); pedals.clutch=readClutch();
    return true;
}

void Inputs::update() {
    pedals.throttle=readThrottle();
    pedals.brake=readBrake();
    pedals.clutch=readClutch();
}

const PedalPayload& Inputs::getPedalData() { return pedals; }

void Inputs::getSensorStatus(PedalSensorFrame& response, PedalSensorResult result) {
    pedalSensorInitFrame(response, PedalSensorFrameKind::STATUS, PedalSensorCommand::GET_STATUS, responseSequence++);
    copySettingsToFrame(response);
    response.result=result;
    response.throttleRawDelta=throttleDelta; response.brakeRawDelta=brakeDelta; response.clutchRawDelta=clutchDelta;
    response.throttleOutput=pedals.throttle; response.brakeOutput=pedals.brake; response.clutchOutput=pedals.clutch;
    pedalSensorSealFrame(response);
}

bool Inputs::processSensorCommand(const PedalSensorFrame& command, PedalSensorFrame& response) {
    PedalSensorResult result=PedalSensorResult::OK;
    if (!pedalSensorValidateFrame(command) || command.kind != PedalSensorFrameKind::COMMAND) { getSensorStatus(response, PedalSensorResult::BAD_FRAME); return false; }

    const uint8_t cmd=static_cast<uint8_t>(command.command);
    if (cmd==static_cast<uint8_t>(PedalSensorCommand::GET_STATUS)) {
        // no-op
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::SET_THROTTLE_CONFIG) ||
               cmd==static_cast<uint8_t>(PedalSensorCommand::SET_BRAKE_CONFIG) ||
               cmd==static_cast<uint8_t>(PedalSensorCommand::SET_CLUTCH_CONFIG)) {
        const bool throttle=cmd==static_cast<uint8_t>(PedalSensorCommand::SET_THROTTLE_CONFIG);
        const bool brake=cmd==static_cast<uint8_t>(PedalSensorCommand::SET_BRAKE_CONFIG);
        const bool clutch=cmd==static_cast<uint8_t>(PedalSensorCommand::SET_CLUTCH_CONFIG);
        const SensorSettings previous=settings;
        const RuntimeSnapshot snapshot=snapshotRuntime();
        const int32_t pt=throttleTare,pb=brakeTare,pc=clutchTare;
        const int32_t ptd=throttleDelta,pbd=brakeDelta,pcd=clutchDelta;
        const bool pth=throttleHasFilter,pbh=brakeHasFilter,pch=clutchHasFilter;
        const uint16_t ptl=throttleLast,pbl=brakeLast,pcl=clutchLast;
        SensorSettings next=settings;
        if (throttle) {
            next.throttleMode=command.throttleMode; next.throttleFilter=max<uint8_t>(1,command.throttleFilterDivisor);
            next.throttleCapacityKg=command.throttleCapacityKg; next.throttleMaxForceKg=command.throttleMaxForceKg; next.throttleCountsPerKg=command.throttleCountsPerKg;
            next.flags=(next.flags & ~FLAG_THROTTLE_INVERT) | (command.flags & FLAG_THROTTLE_INVERT);
        } else if (brake) {
            next.brakeMode=command.brakeMode; next.brakeFilter=max<uint8_t>(1,command.brakeFilterDivisor);
            next.brakeCapacityKg=command.brakeCapacityKg; next.brakeMaxForceKg=command.brakeMaxForceKg; next.brakeCountsPerKg=command.brakeCountsPerKg;
            next.flags=(next.flags & ~FLAG_BRAKE_INVERT) | (command.flags & FLAG_BRAKE_INVERT);
        } else {
            next.clutchMode=command.clutchMode; next.clutchFilter=max<uint8_t>(1,command.clutchFilterDivisor);
            next.clutchCapacityKg=command.clutchCapacityKg; next.clutchMaxForceKg=command.clutchMaxForceKg; next.clutchCountsPerKg=command.clutchCountsPerKg;
            next.flags=(next.flags & ~FLAG_CLUTCH_INVERT) | (command.flags & FLAG_CLUTCH_INVERT);
        }
        if (!validSettings(next)) result=PedalSensorResult::BAD_CONFIG;
        else {
            settings=next; configurePins(); resetAxisRuntime(throttle,brake,clutch);
            bool ok=true;
            if (throttle) ok=tareAxisIfNeeded(settings.throttleMode,true,false,false);
            if (brake && ok) ok=tareAxisIfNeeded(settings.brakeMode,false,true,false);
            if (clutch && ok) ok=tareAxisIfNeeded(settings.clutchMode,false,false,true);
            if (throttle && isAnalog(settings.throttleMode)) throttleFiltered=analogRead(THROTTLE_ADC_PIN);
            if (brake && isAnalog(settings.brakeMode)) brakeFiltered=analogRead(BRAKE_ADC_PIN);
#if ENABLE_CLUTCH_PEDAL
            if (clutch && isAnalog(settings.clutchMode)) clutchFiltered=analogRead(CLUTCH_ADC_PIN);
#endif
            if (!ok) {
                settings=previous; throttleTare=pt; brakeTare=pb; clutchTare=pc; throttleDelta=ptd; brakeDelta=pbd; clutchDelta=pcd;
                throttleHasFilter=pth; brakeHasFilter=pbh; clutchHasFilter=pch; throttleLast=ptl; brakeLast=pbl; clutchLast=pcl;
                restoreTarePersistence(snapshot);
                configurePins(); result=tarePersistenceFailed ? PedalSensorResult::PERSISTENCE_ERROR : PedalSensorResult::HX711_TIMEOUT;
            } else if (!saveSettings()) {
                settings=previous; restoreRuntime(snapshot);
                restoreTarePersistence(snapshot); configurePins(); (void)saveSettings();
                result=PedalSensorResult::PERSISTENCE_ERROR;
            }
        }
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::SET_CONFIG)) {
        SensorSettings next=settings;
        next.throttleMode=command.throttleMode; next.brakeMode=command.brakeMode; next.clutchMode=command.clutchMode; next.flags=command.flags & 0x07;
        next.throttleFilter=max<uint8_t>(1,command.throttleFilterDivisor); next.brakeFilter=max<uint8_t>(1,command.brakeFilterDivisor); next.clutchFilter=max<uint8_t>(1,command.clutchFilterDivisor);
        next.throttleCapacityKg=command.throttleCapacityKg; next.brakeCapacityKg=command.brakeCapacityKg; next.clutchCapacityKg=command.clutchCapacityKg;
        next.throttleMaxForceKg=command.throttleMaxForceKg; next.brakeMaxForceKg=command.brakeMaxForceKg; next.clutchMaxForceKg=command.clutchMaxForceKg;
        next.throttleCountsPerKg=command.throttleCountsPerKg; next.brakeCountsPerKg=command.brakeCountsPerKg; next.clutchCountsPerKg=command.clutchCountsPerKg;
        if (!validSettings(next)) result=PedalSensorResult::BAD_CONFIG;
        else {
            const SensorSettings previous=settings; const RuntimeSnapshot snapshot=snapshotRuntime(); settings=next; configurePins(); resetAxisRuntime(true,true,true);
            const bool ok=(isAnalog(settings.throttleMode)||tareThrottle()) && (isAnalog(settings.brakeMode)||tareBrake()) && (isAnalog(settings.clutchMode)||tareClutch());
            if (!ok) { settings=previous; restoreRuntime(snapshot); restoreTarePersistence(snapshot); configurePins(); (void)saveSettings(); result=tarePersistenceFailed ? PedalSensorResult::PERSISTENCE_ERROR : PedalSensorResult::HX711_TIMEOUT; }
            else {
                if(isAnalog(settings.throttleMode)) throttleFiltered=analogRead(THROTTLE_ADC_PIN);
                if(isAnalog(settings.brakeMode)) brakeFiltered=analogRead(BRAKE_ADC_PIN);
                if(isAnalog(settings.clutchMode)) clutchFiltered=analogRead(CLUTCH_ADC_PIN);
                if (!saveSettings()) { settings=previous; restoreRuntime(snapshot); restoreTarePersistence(snapshot); configurePins(); (void)saveSettings(); result=PedalSensorResult::PERSISTENCE_ERROR; }
            }
        }
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_THROTTLE) || cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_BRAKE) || cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_CLUTCH)) {
        const RuntimeSnapshot snapshot=snapshotRuntime();
        if (cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_THROTTLE)) result=isHx711(settings.throttleMode) ? (tareThrottle()?PedalSensorResult::OK:(tarePersistenceFailed?PedalSensorResult::PERSISTENCE_ERROR:PedalSensorResult::HX711_TIMEOUT)) : PedalSensorResult::UNSUPPORTED;
        else if (cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_BRAKE)) result=isHx711(settings.brakeMode) ? (tareBrake()?PedalSensorResult::OK:(tarePersistenceFailed?PedalSensorResult::PERSISTENCE_ERROR:PedalSensorResult::HX711_TIMEOUT)) : PedalSensorResult::UNSUPPORTED;
        else result=isHx711(settings.clutchMode) ? (tareClutch()?PedalSensorResult::OK:(tarePersistenceFailed?PedalSensorResult::PERSISTENCE_ERROR:PedalSensorResult::HX711_TIMEOUT)) : PedalSensorResult::UNSUPPORTED;
        if (result!=PedalSensorResult::OK && result!=PedalSensorResult::UNSUPPORTED) restoreRuntime(snapshot);
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::TARE_BOTH)) {
        const RuntimeSnapshot snapshot=snapshotRuntime();
        const bool ok=(!isHx711(settings.throttleMode)||tareThrottle()) &&
                      (!isHx711(settings.brakeMode)||tareBrake()) &&
                      (!isHx711(settings.clutchMode)||tareClutch());
        if (!ok) { restoreRuntime(snapshot); restoreTarePersistence(snapshot); result=tarePersistenceFailed ? PedalSensorResult::PERSISTENCE_ERROR : PedalSensorResult::HX711_TIMEOUT; }
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_THROTTLE) || cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_BRAKE) || cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_CLUTCH)) {
        const bool throttle=cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_THROTTLE);
        const bool brake=cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_BRAKE);
        const bool clutch=cmd==static_cast<uint8_t>(PedalSensorCommand::CALIBRATE_CLUTCH);
        const float capacity=throttle?settings.throttleCapacityKg:(brake?settings.brakeCapacityKg:settings.clutchCapacityKg);
        const uint8_t mode=throttle?settings.throttleMode:(brake?settings.brakeMode:settings.clutchMode);
        if (!isfinite(command.calibrationForceKg) || command.calibrationForceKg<0.1f || command.calibrationForceKg>capacity) result=PedalSensorResult::BAD_CALIBRATION_FORCE;
        else if (!isHx711(mode)) result=PedalSensorResult::UNSUPPORTED;
        else {
            const uint8_t data=throttle?THROTTLE_HX711_DATA_PIN:(brake?BRAKE_HX711_DATA_PIN:CLUTCH_HX711_DATA_PIN);
            const uint8_t clock=throttle?THROTTLE_HX711_CLOCK_PIN:(brake?BRAKE_HX711_CLOCK_PIN:CLUTCH_HX711_CLOCK_PIN);
            const uint32_t timeout=throttle?THROTTLE_HX711_READY_TIMEOUT_MS:(brake?BRAKE_HX711_READY_TIMEOUT_MS:CLUTCH_HX711_READY_TIMEOUT_MS);
            int64_t total=0; bool ok=true;
            for(uint8_t i=0;i<8;++i){int32_t raw=0;if(!hxReadTimeout(data,clock,raw,timeout)){ok=false;break;}total+=raw;}
            if(!ok) result=PedalSensorResult::HX711_TIMEOUT;
            else {
                const int32_t tare=throttle?throttleTare:(brake?brakeTare:clutchTare);
                int32_t delta=static_cast<int32_t>(total/8)-tare;
                const uint8_t invert=throttle?FLAG_THROTTLE_INVERT:(brake?FLAG_BRAKE_INVERT:FLAG_CLUTCH_INVERT);
                if(settings.flags & invert) delta=-delta;
                if(delta<100) result=PedalSensorResult::NO_LOAD;
                else {
                    const SensorSettings previous=settings;
                    const float counts=static_cast<float>(delta)/command.calibrationForceKg;
                    if(throttle) settings.throttleCountsPerKg=counts;
                    else if(brake) settings.brakeCountsPerKg=counts;
                    else settings.clutchCountsPerKg=counts;
                    if (!saveSettings()) { settings=previous; (void)saveSettings(); result=PedalSensorResult::PERSISTENCE_ERROR; }
                }
            }
        }
    } else if (cmd==static_cast<uint8_t>(PedalSensorCommand::RESET_DEFAULTS)) {
        const SensorSettings previous=settings;
        const RuntimeSnapshot snapshot=snapshotRuntime();
        defaults(); configurePins(); resetAxisRuntime(true,true,true);
        const bool ok=(!isHx711(settings.throttleMode)||tareThrottle()) &&
                      (!isHx711(settings.brakeMode)||tareBrake()) &&
                      (!isHx711(settings.clutchMode)||tareClutch());
        if (!ok) { settings=previous; restoreRuntime(snapshot); restoreTarePersistence(snapshot); configurePins(); result=tarePersistenceFailed ? PedalSensorResult::PERSISTENCE_ERROR : PedalSensorResult::HX711_TIMEOUT; }
        else {
            if(isAnalog(settings.throttleMode)) throttleFiltered=analogRead(THROTTLE_ADC_PIN);
            if(isAnalog(settings.brakeMode)) brakeFiltered=analogRead(BRAKE_ADC_PIN);
            if(isAnalog(settings.clutchMode)) clutchFiltered=analogRead(CLUTCH_ADC_PIN);
            if (!saveSettings()) { settings=previous; restoreRuntime(snapshot); restoreTarePersistence(snapshot); configurePins(); result=PedalSensorResult::PERSISTENCE_ERROR; }
        }
    } else result=PedalSensorResult::UNSUPPORTED;

    getSensorStatus(response,result);
    response.command=command.command;
    pedalSensorSealFrame(response);
    return result==PedalSensorResult::OK;
}
