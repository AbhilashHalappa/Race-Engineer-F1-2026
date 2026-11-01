/******************************************************************************
 * GamePad Pro V8
 * Inputs.cpp
 *
 * Wheel input manager
 ******************************************************************************/

#include "Inputs.h"

#include "Pins.h"
#include "Config.h"

//=============================================================================
// Local Data
//=============================================================================

static void scanButtonMatrix();
static void scanEncoderMatrix();
static void scanFormerAnalogButtons();

namespace
{

WheelPayload wheel = {};

uint16_t buttonMatrixState  = 0;
uint16_t encoderMatrixState = 0;

bool lastEncoderState[3][4] = {};

const uint8_t buttonRows[3] =
{
    BTN_ROW1_PIN,
    BTN_ROW2_PIN,
    BTN_ROW3_PIN
};

const uint8_t buttonCols[4] =
{
    BTN_COL1_PIN,
    BTN_COL2_PIN,
    BTN_COL3_PIN,
    BTN_COL4_PIN
};

const uint8_t encoderRows[3] =
{
    ENC_ROW1_PIN,
    ENC_ROW2_PIN,
    ENC_ROW3_PIN
};

const uint8_t encoderCols[4] =
{
    ENC_COL1_PIN,
    ENC_COL2_PIN,
    ENC_COL3_PIN,
    ENC_COL4_PIN
};

struct DebouncedButton
{
    uint8_t pin;
    uint8_t bit;
    bool stablePressed;
    bool lastRawPressed;
    uint8_t matchingSamples;
};

DebouncedButton formerAnalogButtons[4] =
{
    { POT1_BUTTON_PIN, POT1_BUTTON_BIT, false, false, 0 },
    { POT2_BUTTON_PIN, POT2_BUTTON_BIT, false, false, 0 },
    { CLUTCH_LEFT_BUTTON_PIN, CLUTCH_LEFT_BUTTON_BIT, false, false, 0 },
    { CLUTCH_RIGHT_BUTTON_PIN, CLUTCH_RIGHT_BUTTON_BIT, false, false, 0 }
};

void processButtonMatrix(uint8_t row, uint8_t col, bool pressed)
{
    const uint8_t bit = (row * 4) + col;

    if (pressed)
        buttonMatrixState |= (1U << bit);
    else
        buttonMatrixState &= ~(1U << bit);
}

void processEncoderMatrix(uint8_t row, uint8_t col, bool pressed)
{
    const uint8_t bit = (row * 4) + col;

    if (!pressed)
    {
        encoderMatrixState &= ~(1U << bit);
        return;
    }

    const uint8_t pairCol = col ^ 1;

    if (digitalRead(encoderCols[pairCol]) == HIGH)
        encoderMatrixState |= (1U << bit);
}

} // namespace

//=============================================================================
// Initialize
//=============================================================================

bool Inputs::begin()
{
    for (uint8_t i = 0; i < 3; i++)
    {
        pinMode(buttonRows[i], OUTPUT);
        digitalWrite(buttonRows[i], HIGH);
        pinMode(encoderRows[i], OUTPUT);
        digitalWrite(encoderRows[i], HIGH);
    }

    for (uint8_t i = 0; i < 4; i++)
    {
        pinMode(buttonCols[i], INPUT_PULLUP);
        pinMode(encoderCols[i], INPUT_PULLUP);
    }

    // GPIO 34/35/36/39 have no internal pull-up support.
    // External pull-ups are required; buttons connect the pin to GND.
    for (uint8_t i = 0; i < 4; i++)
        pinMode(formerAnalogButtons[i].pin, INPUT);

    wheel = {};
    wheel.battery = 100;

    return true;
}

//=============================================================================
// Scan Button Matrix
//=============================================================================

static void scanButtonMatrix()
{
    buttonMatrixState = 0;

    for (uint8_t row = 0; row < 3; row++)
    {
        for (uint8_t i = 0; i < 3; i++)
            digitalWrite(buttonRows[i], HIGH);

        digitalWrite(buttonRows[row], LOW);
        delayMicroseconds(10);

        for (uint8_t col = 0; col < 4; col++)
        {
            const bool pressed = (digitalRead(buttonCols[col]) == LOW);
            processButtonMatrix(row, col, pressed);
        }
    }

    for (uint8_t i = 0; i < 3; i++)
        digitalWrite(buttonRows[i], HIGH);
}

//=============================================================================
// Scan Encoder Matrix
//=============================================================================

static void scanEncoderMatrix()
{
    // Encoder state is event/state based; do not clear it every scan.
    for (uint8_t row = 0; row < 3; row++)
    {
        for (uint8_t i = 0; i < 3; i++)
            digitalWrite(encoderRows[i], HIGH);

        digitalWrite(encoderRows[row], LOW);
        delayMicroseconds(100);

        for (uint8_t col = 0; col < 4; col++)
        {
            const bool currentState = (digitalRead(encoderCols[col]) == LOW);

            if (currentState != lastEncoderState[row][col])
            {
                processEncoderMatrix(row, col, currentState);
                lastEncoderState[row][col] = currentState;
            }
        }
    }

    for (uint8_t i = 0; i < 3; i++)
        digitalWrite(encoderRows[i], HIGH);
}

//=============================================================================
// Former analog inputs — now four independent digital buttons
//=============================================================================

static void scanFormerAnalogButtons()
{
    for (uint8_t i = 0; i < 4; i++)
    {
        DebouncedButton& button = formerAnalogButtons[i];

        // External pull-up + switch to GND: LOW means pressed.
        const bool rawPressed = (digitalRead(button.pin) == LOW);

        if (rawPressed == button.lastRawPressed)
        {
            if (button.matchingSamples < ANALOG_INPUT_BUTTON_DEBOUNCE_SAMPLES)
                ++button.matchingSamples;
        }
        else
        {
            button.lastRawPressed = rawPressed;
            button.matchingSamples = 1;
        }

        if (button.matchingSamples >= ANALOG_INPUT_BUTTON_DEBOUNCE_SAMPLES)
            button.stablePressed = rawPressed;

        if (button.stablePressed)
            wheel.buttonState |= (1UL << button.bit);
    }
}

//=============================================================================
// Update Inputs
//=============================================================================

void Inputs::update()
{
    scanButtonMatrix();
    scanEncoderMatrix();

    wheel.buttonState = 0;

    // Existing matrix and encoder assignments remain unchanged.
    wheel.buttonState |= static_cast<uint32_t>(buttonMatrixState);
    wheel.buttonState |= (static_cast<uint32_t>(encoderMatrixState) << 12);

    // Four former analog controls occupy button bits 24-27.
    scanFormerAnalogButtons();

    // No analog clutch axes are generated or transmitted.
    wheel.clutchLeft = 0;
    wheel.clutchRight = 0;
    wheel.battery = 100;
}

//=============================================================================
// Get Latest Wheel Data
//=============================================================================

const WheelPayload& Inputs::getWheelData()
{
    return wheel;
}
