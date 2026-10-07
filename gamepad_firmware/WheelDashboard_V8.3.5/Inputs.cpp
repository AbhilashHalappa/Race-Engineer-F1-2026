/******************************************************************************
 * GamePad Pro V8
 * Inputs.cpp
 *
 * Part 1
 ******************************************************************************/

#include "Inputs.h"

#include "Pins.h"
#include "Config.h"

//=============================================================================
// Local Data
//=============================================================================
static void scanButtonMatrix();
static void scanEncoderMatrix();
static void readPots();
static void readClutches();

namespace
{


constexpr uint32_t POT_BUTTON_MASK =
    (1UL << POT1_BIT_LOW)  |
    (1UL << POT1_BIT_HIGH) |
    (1UL << POT2_BIT_LOW)  |
    (1UL << POT2_BIT_HIGH);

//-----------------------------------------------------------------------------
// Latest Wheel Data
//-----------------------------------------------------------------------------

WheelPayload wheel = {};

//-----------------------------------------------------------------------------
// Matrix States
//-----------------------------------------------------------------------------

uint16_t buttonMatrixState  = 0;
uint16_t encoderMatrixState = 0;

bool lastEncoderState[3][4] = {};

//-----------------------------------------------------------------------------
// ADC Filters
//-----------------------------------------------------------------------------

float clutchLeftFiltered  = 0.0f;
float clutchRightFiltered = 0.0f;

void applyPotPosition(uint16_t adc,
                      uint8_t bitLow,
                      uint8_t bitHigh)
{
    // Left / right with dead centre — never both at once.
    if (adc <= POT_LEFT_THRESHOLD)
    {
        wheel.buttonState |= (1UL << bitLow);
    }
    else if (adc >= POT_RIGHT_THRESHOLD)
    {
        wheel.buttonState |= (1UL << bitHigh);
    }
    // else: dead zone — no pot button pressed
}

//=============================================================================
// Matrix Pin Tables
//=============================================================================

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

//=============================================================================
// Process Button Matrix
//=============================================================================

void processButtonMatrix(uint8_t row,
                         uint8_t col,
                         bool pressed)
{
    uint8_t bit =
        (row * 4) + col;

    if (pressed)
    {
        buttonMatrixState |= (1U << bit);
    }
    else
    {
        buttonMatrixState &= ~(1U << bit);
    }
}

//=============================================================================
// Process Encoder Matrix
//=============================================================================

void processEncoderMatrix(uint8_t row,
                          uint8_t col,
                          bool pressed)
{
    uint8_t bit = (row * 4) + col;

    // Clear on release
    if (!pressed)
    {
        encoderMatrixState &= ~(1U << bit);
        return;
    }

    // Encoder columns work as pairs:
    // 0 <-> 1
    // 2 <-> 3
    uint8_t pairCol = col ^ 1;

    // Match old working logic:
    // Only accept this side if the paired side is HIGH
    if (digitalRead(encoderCols[pairCol]) == HIGH)
    {
        encoderMatrixState |= (1U << bit);
    }
}

} // namespace

//=============================================================================
// Initialize
//=============================================================================

bool Inputs::begin()
{
    //---------------------------------------------------------------------
    // Button Matrix
    //---------------------------------------------------------------------

    for (uint8_t i = 0; i < 3; i++)
    {
        pinMode(buttonRows[i], OUTPUT);
        digitalWrite(buttonRows[i], HIGH);
    }

    for (uint8_t i = 0; i < 4; i++)
    {
        pinMode(buttonCols[i], INPUT_PULLUP);
    }

    //---------------------------------------------------------------------
    // Encoder Matrix
    //---------------------------------------------------------------------

    for (uint8_t i = 0; i < 3; i++)
    {
        pinMode(encoderRows[i], OUTPUT);
        digitalWrite(encoderRows[i], HIGH);
    }

    for (uint8_t i = 0; i < 4; i++)
    {
        pinMode(encoderCols[i], INPUT_PULLUP);
    }

    //---------------------------------------------------------------------
    // Analog Inputs
    //---------------------------------------------------------------------

    pinMode(CLUTCH_LEFT_ADC_PIN, INPUT);
    pinMode(CLUTCH_RIGHT_ADC_PIN, INPUT);

    pinMode(POT1_ADC_PIN, INPUT);
    pinMode(POT2_ADC_PIN, INPUT);

    //---------------------------------------------------------------------
    // Initialize ADC Filters
    //---------------------------------------------------------------------
	analogReadResolution(12);

	analogSetAttenuation(ADC_11db);
    clutchLeftFiltered =
        analogRead(CLUTCH_LEFT_ADC_PIN);

    clutchRightFiltered =
        analogRead(CLUTCH_RIGHT_ADC_PIN);

    //---------------------------------------------------------------------
    // Default Values
    //---------------------------------------------------------------------

    wheel.buttonState = 0;

    wheel.clutchLeft = 0;

    wheel.clutchRight = 0;

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
        //-------------------------------------------------------------
        // All Rows HIGH
        //-------------------------------------------------------------

        for (uint8_t i = 0; i < 3; i++)
        {
            digitalWrite(buttonRows[i], HIGH);
        }

        //-------------------------------------------------------------
        // Drive Current Row LOW
        //-------------------------------------------------------------

        digitalWrite(buttonRows[row], LOW);

        delayMicroseconds(10);

        //-------------------------------------------------------------
        // Read Columns
        //-------------------------------------------------------------

        for (uint8_t col = 0; col < 4; col++)
        {
            bool pressed =
                (digitalRead(buttonCols[col]) == LOW);

            processButtonMatrix(
                row,
                col,
                pressed);
        }
    }

    //-------------------------------------------------------------
    // Restore Rows HIGH
    //-------------------------------------------------------------

    for (uint8_t i = 0; i < 3; i++)
    {
        digitalWrite(buttonRows[i], HIGH);
    }
}

//=============================================================================
// Scan Encoder Matrix
//=============================================================================

static void scanEncoderMatrix()
{
    // IMPORTANT:
    // Do NOT clear encoderMatrixState here.
    // Encoder outputs are event/state based, not simple button matrix state.

    for (uint8_t row = 0; row < 3; row++)
    {
        //-------------------------------------------------------------
        // All Rows HIGH
        //-------------------------------------------------------------

        for (uint8_t i = 0; i < 3; i++)
        {
            digitalWrite(encoderRows[i], HIGH);
        }

        //-------------------------------------------------------------
        // Drive Current Row LOW
        //-------------------------------------------------------------

        digitalWrite(encoderRows[row], LOW);

        delayMicroseconds(100);

        //-------------------------------------------------------------
        // Read Columns
        //-------------------------------------------------------------

        for (uint8_t col = 0; col < 4; col++)
        {
            bool currentState =
                (digitalRead(encoderCols[col]) == LOW);

            if (currentState != lastEncoderState[row][col])
            {
                processEncoderMatrix(
                    row,
                    col,
                    currentState);

                lastEncoderState[row][col] = currentState;
            }
        }
    }

    //-------------------------------------------------------------
    // Restore Rows HIGH
    //-------------------------------------------------------------

    for (uint8_t i = 0; i < 3; i++)
    {
        digitalWrite(encoderRows[i], HIGH);
    }
}

//=============================================================================
// Read Potentiometers
//=============================================================================

static void readPots()
{
    // Clear pot button bits, then apply left/right zones.
    wheel.buttonState &= ~POT_BUTTON_MASK;

    applyPotPosition(
        analogRead(POT1_ADC_PIN),
        POT1_BIT_LOW,
        POT1_BIT_HIGH);

    applyPotPosition(
        analogRead(POT2_ADC_PIN),
        POT2_BIT_LOW,
        POT2_BIT_HIGH);
}

//=============================================================================
// Read Clutches
//=============================================================================

// ESP32 ADC mux needs a throwaway sample after channel change, otherwise the
// previous pot/matrix activity can leak into floating clutch pins.
static uint16_t readAdcSettled(uint8_t pin)
{
    analogRead(pin);
    delayMicroseconds(20);
    return static_cast<uint16_t>(analogRead(pin));
}

static void readClutches()
{
#if !ENABLE_CLUTCHES
    wheel.clutchLeft  = 0;
    wheel.clutchRight = 0;
    return;
#else
    constexpr float alpha = 0.30f;

    //-------------------------------------------------------------
    // Left Clutch
    //-------------------------------------------------------------

    clutchLeftFiltered =
        (alpha * readAdcSettled(CLUTCH_LEFT_ADC_PIN)) +
        ((1.0f - alpha) * clutchLeftFiltered);

    //-------------------------------------------------------------
    // Right Clutch
    //-------------------------------------------------------------

    clutchRightFiltered =
        (alpha * readAdcSettled(CLUTCH_RIGHT_ADC_PIN)) +
        ((1.0f - alpha) * clutchRightFiltered);

    //-------------------------------------------------------------
    // Store
    //-------------------------------------------------------------

    wheel.clutchLeft =
        static_cast<uint16_t>(clutchLeftFiltered);

    wheel.clutchRight =
        static_cast<uint16_t>(clutchRightFiltered);
#endif
}

//=============================================================================
// Update Inputs
//=============================================================================

void Inputs::update()
{
    //---------------------------------------------------------------------
    // Scan Matrices
    //---------------------------------------------------------------------

    scanButtonMatrix();

    scanEncoderMatrix();

    //---------------------------------------------------------------------
    // Build Button State
    //---------------------------------------------------------------------

    wheel.buttonState = 0;

    // Button Matrix
    // Bits 0-11

    wheel.buttonState |=
        static_cast<uint32_t>(buttonMatrixState);

    // Encoder Matrix
    // Bits 12-23

    wheel.buttonState |=
        (static_cast<uint32_t>(encoderMatrixState) << 12);

    //---------------------------------------------------------------------
    // Clutch paddles (forced to 0 when ENABLE_CLUTCHES is 0)
    // Read before pots so ADC mux residue from pots does not smear in.
    //---------------------------------------------------------------------

    readClutches();

    //---------------------------------------------------------------------
    // Potentiometers — 2 positions each (bits 24/25 and 26/27)
    //---------------------------------------------------------------------

    readPots();

    wheel.battery = 100;
}

//=============================================================================
// Get Latest Wheel Data
//=============================================================================

const WheelPayload& Inputs::getWheelData()
{
    return wheel;
}