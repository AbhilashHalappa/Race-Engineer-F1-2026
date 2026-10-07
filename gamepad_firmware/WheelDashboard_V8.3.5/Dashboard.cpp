/******************************************************************************
 * GamePad Pro V8
 * Dashboard.cpp
 ******************************************************************************/

#include "Dashboard.h"

#include "Display.h"
#include "RPMBar.h"

//=============================================================================
// Local Data
//=============================================================================

namespace
{

WheelDashboardExtendedPayload dashboard = {};

} // namespace

//=============================================================================
// Initialize Dashboard
//=============================================================================

bool Dashboard::begin()
{
    dashboard.motorTempCx100 = MOTOR_TEMP_INVALID_CX100;

    Display::begin();

    RPMBar::begin();

    return true;
}

//=============================================================================
// Update Dashboard
//=============================================================================

void Dashboard::update()
{
    //--------------------------------------------------------------
    // Update MAX7219 Display
    //--------------------------------------------------------------

    Display::setDashboardData(dashboard);
    Display::update();

    //--------------------------------------------------------------
    // Update RPM LED Bar
    //--------------------------------------------------------------

    RPMBar::setDashboardData(dashboard);
    RPMBar::update();
}

//=============================================================================
// Store Latest Dashboard Data
//=============================================================================

void Dashboard::setData(const WheelDashboardExtendedPayload& data)
{
    dashboard = data;
}

//=============================================================================
// Get Latest Dashboard Data
//=============================================================================

const WheelDashboardExtendedPayload& Dashboard::getData()
{
    return dashboard;
}