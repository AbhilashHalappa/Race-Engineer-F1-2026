#include "Inputs.h"
#include "Pins.h"
#include "Config.h"
#include "HandbrakeSensorProtocol.h"
#include <Preferences.h>
#include <math.h>

namespace
{
struct DebouncedButton
{
    uint8_t pin;
    bool rawPressed;
    bool stablePressed;
    uint32_t changedAt;
};

DebouncedButton buttons[3] =
{
    {SHIFT_UP_PIN, false, false, 0},
    {SHIFT_DOWN_PIN, false, false, 0},
    {SHIFTER_AUX_PIN, false, false, 0}
};

ShifterPayload shifter = {};

struct RuntimeConfig {
    HandbrakeSensorMode mode = static_cast<HandbrakeSensorMode>(HANDBRAKE_SENSOR_MODE);
    uint8_t filterDivisor = HX711_FILTER_DIVISOR;
    bool invert = (HANDBRAKE_SENSOR_MODE == HANDBRAKE_SENSOR_HX711) ? HX711_HANDBRAKE_INVERT : HALL_HANDBRAKE_INVERT;
    float capacityKg = HX711_LOAD_CELL_CAPACITY_KG;
    float maxForceKg = HX711_MAX_FORCE_KG;
    float countsPerKg = HX711_COUNTS_PER_KG;
};
RuntimeConfig sensorConfig;
Preferences sensorPrefs;


// HX711 state. The Receiver still receives the same normalized 0..4095 value
// regardless of whether Hall or load cell mode is selected.
int32_t hx711TareOffset = 0;
int32_t hx711FilteredDelta = 0;
bool hx711HasFilteredValue = false;
uint16_t hx711LastOutput = 0;

void updateButton(DebouncedButton& button, uint32_t now)
{
    const bool pressed = (digitalRead(button.pin) == LOW);
    if (pressed != button.rawPressed)
    {
        button.rawPressed = pressed;
        button.changedAt = now;
    }
    if (button.stablePressed != button.rawPressed &&
        (now - button.changedAt) >= DEBOUNCE_MS)
    {
        button.stablePressed = button.rawPressed;
    }
}

uint16_t readHallHandbrake()
{
    uint32_t total = 0;
    for (uint8_t i = 0; i < HALL_HANDBRAKE_SAMPLES; ++i)
    {
        total += static_cast<uint16_t>(analogRead(HALL_HANDBRAKE_PIN));
    }

    uint16_t value = static_cast<uint16_t>(total / HALL_HANDBRAKE_SAMPLES);
    if (value > 4095u) value = 4095u;
    if (sensorConfig.invert) value = static_cast<uint16_t>(4095u - value);
    return value;
}

bool hx711ReadRaw(int32_t& value)
{
    // DOUT is LOW only when a fresh conversion is ready. Never block the
    // shifter loop waiting for a conversion; simply keep the previous value.
    if (digitalRead(HX711_DATA_PIN) != LOW) return false;

    uint32_t data = 0;
    noInterrupts();
    for (uint8_t i = 0; i < 24; ++i)
    {
        digitalWrite(HX711_CLOCK_PIN, HIGH);
        delayMicroseconds(1);
        data = (data << 1) | (digitalRead(HX711_DATA_PIN) ? 1u : 0u);
        digitalWrite(HX711_CLOCK_PIN, LOW);
        delayMicroseconds(1);
    }

    // 25th pulse selects Channel A, gain 128 for the next conversion.
    digitalWrite(HX711_CLOCK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(HX711_CLOCK_PIN, LOW);
    interrupts();

    // Sign-extend the 24-bit two's-complement result.
    if (data & 0x00800000UL) data |= 0xFF000000UL;
    value = static_cast<int32_t>(data);
    return true;
}

bool hx711ReadRawWithTimeout(int32_t& value, uint32_t timeoutMs)
{
    const uint32_t start = millis();
    while ((millis() - start) < timeoutMs)
    {
        if (hx711ReadRaw(value)) return true;
        delay(1);
    }
    return false;
}

bool tareHX711()
{
    int64_t total = 0;
    uint8_t collected = 0;

#if ENABLE_SERIAL_DEBUG
    Serial.println("HX711: release handbrake; taring...");
#endif

    while (collected < HX711_TARE_SAMPLES)
    {
        int32_t raw = 0;
        if (!hx711ReadRawWithTimeout(raw, HX711_READY_TIMEOUT_MS))
        {
#if ENABLE_SERIAL_DEBUG
            Serial.println("[ERROR] HX711 tare timeout - check DAT/CLK/VCC/GND");
#endif
            return false;
        }
        total += raw;
        ++collected;
    }

    hx711TareOffset = static_cast<int32_t>(total / HX711_TARE_SAMPLES);
    hx711FilteredDelta = 0;
    hx711HasFilteredValue = false;
    hx711LastOutput = 0;

#if ENABLE_SERIAL_DEBUG
    Serial.print("HX711 tare offset: ");
    Serial.println(hx711TareOffset);
#endif
    return true;
}

uint16_t readHX711Handbrake()
{
    int32_t raw = 0;
    if (!hx711ReadRaw(raw)) return hx711LastOutput;

    int32_t delta = raw - hx711TareOffset;
    if (sensorConfig.invert) delta = -delta;
    if (delta < 0) delta = 0;

    if (!hx711HasFilteredValue)
    {
        hx711FilteredDelta = delta;
        hx711HasFilteredValue = true;
    }
    else if (sensorConfig.filterDivisor <= 1)
    {
        hx711FilteredDelta = delta;
    }
    else
    {
        hx711FilteredDelta += (delta - hx711FilteredDelta) / sensorConfig.filterDivisor;
    }

    float targetForceKg = sensorConfig.maxForceKg;
    if (targetForceKg < 0.1f) targetForceKg = 0.1f;
    if (targetForceKg > sensorConfig.capacityKg)
        targetForceKg = sensorConfig.capacityKg;
    const float countsPerKg = (sensorConfig.countsPerKg > 1.0f) ? sensorConfig.countsPerKg : 1.0f;
    const int32_t fullScale = static_cast<int32_t>(countsPerKg * targetForceKg);

    int64_t mapped = (static_cast<int64_t>(hx711FilteredDelta) * 4095LL) / (fullScale > 0 ? fullScale : 1);
    if (mapped < 0) mapped = 0;
    if (mapped > 4095) mapped = 4095;
    hx711LastOutput = static_cast<uint16_t>(mapped);
    return hx711LastOutput;
}

uint16_t readHandbrake()
{
if (sensorConfig.mode == HandbrakeSensorMode::HX711) return readHX711Handbrake();
    return readHallHandbrake();
}
}

bool Inputs::begin()
{
    sensorPrefs.begin("hb-sensor", false);
    sensorConfig.mode = static_cast<HandbrakeSensorMode>(sensorPrefs.getUChar("mode", static_cast<uint8_t>(sensorConfig.mode)));
    sensorConfig.filterDivisor = sensorPrefs.getUChar("filter", sensorConfig.filterDivisor);
    sensorConfig.invert = sensorPrefs.getBool("invert", sensorConfig.invert);
    sensorConfig.capacityKg = sensorPrefs.getFloat("capacity", sensorConfig.capacityKg);
    sensorConfig.maxForceKg = sensorPrefs.getFloat("maxforce", sensorConfig.maxForceKg);
    sensorConfig.countsPerKg = sensorPrefs.getFloat("counts", sensorConfig.countsPerKg);
    if ((sensorConfig.mode != HandbrakeSensorMode::HALL && sensorConfig.mode != HandbrakeSensorMode::HX711) ||
        sensorConfig.filterDivisor < 1 || sensorConfig.filterDivisor > 32 ||
        !isfinite(sensorConfig.capacityKg) || !isfinite(sensorConfig.maxForceKg) ||
        !isfinite(sensorConfig.countsPerKg) || sensorConfig.capacityKg <= 0 ||
        sensorConfig.maxForceKg <= 0 || sensorConfig.maxForceKg > sensorConfig.capacityKg ||
        sensorConfig.countsPerKg <= 0) return false;
    analogReadResolution(12);
    pinMode(HALL_HANDBRAKE_PIN, INPUT);
    pinMode(HX711_DATA_PIN, INPUT);
    pinMode(HX711_CLOCK_PIN, OUTPUT);
    digitalWrite(HX711_CLOCK_PIN, LOW);

    for (auto& button : buttons)
    {
        pinMode(button.pin, INPUT_PULLUP);
        button.rawPressed = (digitalRead(button.pin) == LOW);
        button.stablePressed = button.rawPressed;
        button.changedAt = millis();
    }

if (sensorConfig.mode == HandbrakeSensorMode::HX711) {
        if (sensorPrefs.getBool("hasTare", false)) hx711TareOffset = sensorPrefs.getInt("tare", 0);
        else if (!tareHX711()) return false;
    }

    update();
    return true;
}

void Inputs::update()
{
    const uint32_t now = millis();
    for (auto& button : buttons) updateButton(button, now);

    uint8_t state = 0;
    if (buttons[0].stablePressed) state |= (1u << 0);
    if (buttons[1].stablePressed) state |= (1u << 1);
    if (buttons[2].stablePressed) state |= (1u << 2);
    shifter.buttonState = state;
    shifter.handbrake = readHandbrake();
}

bool Inputs::handleCommand(const HandbrakeSensorFrame& command, HandbrakeSensorFrame& response)
{
    handbrakeSensorInitFrame(response, HandbrakeSensorFrameKind::STATUS, command.command, command.sequence);
    response.mode = sensorConfig.mode;
    response.filterDivisor = sensorConfig.filterDivisor;
    response.flags = sensorConfig.invert ? 1 : 0;
    response.capacityKg = sensorConfig.capacityKg;
    response.maxForceKg = sensorConfig.maxForceKg;
    response.countsPerKg = sensorConfig.countsPerKg;
    response.rawDelta = 0;
    response.output = shifter.handbrake;
    response.result = HandbrakeSensorResult::OK;

    if (!handbrakeSensorValidateFrame(command) || command.kind != HandbrakeSensorFrameKind::COMMAND) {
        response.result = HandbrakeSensorResult::BAD_FRAME;
    } else if (command.command == HandbrakeSensorCommand::SET_CONFIG) {
        const bool validMode = command.mode == HandbrakeSensorMode::HALL || command.mode == HandbrakeSensorMode::HX711;
        if (!validMode || command.filterDivisor < 1 || command.filterDivisor > 32 ||
            !isfinite(command.capacityKg) || !isfinite(command.maxForceKg) ||
            !isfinite(command.countsPerKg) || command.capacityKg <= 0 ||
            command.maxForceKg <= 0 || command.maxForceKg > command.capacityKg ||
            command.countsPerKg <= 0) {
            response.result = HandbrakeSensorResult::BAD_CONFIG;
        } else {
            RuntimeConfig previous = sensorConfig;
            sensorConfig.mode = command.mode;
            sensorConfig.filterDivisor = command.filterDivisor;
            sensorConfig.invert = (command.flags & 1) != 0;
            sensorConfig.capacityKg = command.capacityKg;
            sensorConfig.maxForceKg = command.maxForceKg;
            sensorConfig.countsPerKg = command.countsPerKg;
            sensorPrefs.putUChar("mode", static_cast<uint8_t>(sensorConfig.mode));
            sensorPrefs.putUChar("filter", sensorConfig.filterDivisor);
            sensorPrefs.putBool("invert", sensorConfig.invert);
            sensorPrefs.putFloat("capacity", sensorConfig.capacityKg);
            sensorPrefs.putFloat("maxforce", sensorConfig.maxForceKg);
            sensorPrefs.putFloat("counts", sensorConfig.countsPerKg);
            const bool verified =
                sensorPrefs.getUChar("mode", 0) == static_cast<uint8_t>(sensorConfig.mode) &&
                sensorPrefs.getUChar("filter", 0) == sensorConfig.filterDivisor &&
                sensorPrefs.getBool("invert", !sensorConfig.invert) == sensorConfig.invert &&
                fabsf(sensorPrefs.getFloat("capacity", 0) - sensorConfig.capacityKg) < 0.01f &&
                fabsf(sensorPrefs.getFloat("maxforce", 0) - sensorConfig.maxForceKg) < 0.01f &&
                fabsf(sensorPrefs.getFloat("counts", 0) - sensorConfig.countsPerKg) < 0.1f;
            if (!verified) {
                sensorConfig = previous;
                sensorPrefs.putUChar("mode", static_cast<uint8_t>(previous.mode));
                sensorPrefs.putUChar("filter", previous.filterDivisor);
                sensorPrefs.putBool("invert", previous.invert);
                sensorPrefs.putFloat("capacity", previous.capacityKg);
                sensorPrefs.putFloat("maxforce", previous.maxForceKg);
                sensorPrefs.putFloat("counts", previous.countsPerKg);
                response.result = HandbrakeSensorResult::PERSISTENCE_ERROR;
            } else if (sensorConfig.mode == HandbrakeSensorMode::HX711 && !sensorPrefs.getBool("hasTare", false)) {
                if (!tareHX711()) {
                    sensorConfig = previous;
                    sensorPrefs.putUChar("mode", static_cast<uint8_t>(previous.mode));
                    sensorPrefs.putUChar("filter", previous.filterDivisor);
                    sensorPrefs.putBool("invert", previous.invert);
                    sensorPrefs.putFloat("capacity", previous.capacityKg);
                    sensorPrefs.putFloat("maxforce", previous.maxForceKg);
                    sensorPrefs.putFloat("counts", previous.countsPerKg);
                    response.result = HandbrakeSensorResult::HX711_TIMEOUT;
                } else {
                    sensorPrefs.putInt("tare", hx711TareOffset);
                    sensorPrefs.putBool("hasTare", true);
                    if (sensorPrefs.getInt("tare", 0) != hx711TareOffset) {
                        sensorConfig = previous;
                        sensorPrefs.putUChar("mode", static_cast<uint8_t>(previous.mode));
                        sensorPrefs.putUChar("filter", previous.filterDivisor);
                        sensorPrefs.putBool("invert", previous.invert);
                        sensorPrefs.putFloat("capacity", previous.capacityKg);
                        sensorPrefs.putFloat("maxforce", previous.maxForceKg);
                        sensorPrefs.putFloat("counts", previous.countsPerKg);
                        response.result = HandbrakeSensorResult::PERSISTENCE_ERROR;
                    }
                }
            }
        }
    } else if (command.command == HandbrakeSensorCommand::TARE) {
        if (sensorConfig.mode != HandbrakeSensorMode::HX711) response.result = HandbrakeSensorResult::UNSUPPORTED;
        else if (!tareHX711()) response.result = HandbrakeSensorResult::HX711_TIMEOUT;
        else {
            sensorPrefs.putInt("tare", hx711TareOffset);
            sensorPrefs.putBool("hasTare", true);
            if (sensorPrefs.getInt("tare", 0) != hx711TareOffset) response.result = HandbrakeSensorResult::PERSISTENCE_ERROR;
        }
    } else if (command.command == HandbrakeSensorCommand::CALIBRATE) {
        if (sensorConfig.mode != HandbrakeSensorMode::HX711) response.result = HandbrakeSensorResult::UNSUPPORTED;
        else if (!isfinite(command.calibrationForceKg) || command.calibrationForceKg <= 0 || command.calibrationForceKg > sensorConfig.capacityKg)
            response.result = HandbrakeSensorResult::BAD_CALIBRATION_FORCE;
        else {
            int32_t raw = 0;
            if (!hx711ReadRawWithTimeout(raw, HX711_READY_TIMEOUT_MS)) response.result = HandbrakeSensorResult::HX711_TIMEOUT;
            else {
                const int32_t delta = abs(raw - hx711TareOffset);
                if (delta < 100) response.result = HandbrakeSensorResult::NO_LOAD;
                else {
                    sensorConfig.countsPerKg = static_cast<float>(delta) / command.calibrationForceKg;
                    sensorPrefs.putFloat("counts", sensorConfig.countsPerKg);
                    if (fabsf(sensorPrefs.getFloat("counts", 0) - sensorConfig.countsPerKg) > 0.1f)
                        response.result = HandbrakeSensorResult::PERSISTENCE_ERROR;
                }
            }
        }
    } else if (command.command == HandbrakeSensorCommand::RESET_DEFAULTS) {
        sensorPrefs.clear();
        RuntimeConfig defaults;
        sensorConfig = defaults;
        sensorPrefs.putUChar("mode", static_cast<uint8_t>(sensorConfig.mode));
        sensorPrefs.putUChar("filter", sensorConfig.filterDivisor);
        sensorPrefs.putBool("invert", sensorConfig.invert);
        sensorPrefs.putFloat("capacity", sensorConfig.capacityKg);
        sensorPrefs.putFloat("maxforce", sensorConfig.maxForceKg);
        sensorPrefs.putFloat("counts", sensorConfig.countsPerKg);
        sensorPrefs.putBool("hasTare", false);
        if (sensorConfig.mode == HandbrakeSensorMode::HX711 && !tareHX711())
            response.result = HandbrakeSensorResult::HX711_TIMEOUT;
    } else if (command.command != HandbrakeSensorCommand::GET_STATUS) {
        response.result = HandbrakeSensorResult::UNSUPPORTED;
    }

    response.mode = sensorConfig.mode;
    response.filterDivisor = sensorConfig.filterDivisor;
    response.flags = sensorConfig.invert ? 1 : 0;
    response.capacityKg = sensorConfig.capacityKg;
    response.maxForceKg = sensorConfig.maxForceKg;
    response.countsPerKg = sensorConfig.countsPerKg;
    response.rawDelta = hx711FilteredDelta;
    response.output = shifter.handbrake;
    handbrakeSensorSealFrame(response);
    return true;
}

const ShifterPayload& Inputs::getShifterData()
{
    return shifter;
}
