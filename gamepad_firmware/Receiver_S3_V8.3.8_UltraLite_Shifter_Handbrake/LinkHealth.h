/*****************************************************************************/
/* GamePad Pro V8.3.3 - dual-app Receiver status reporter                    */
/*                                                                           */
/* Always emits the original RS/V1 25-byte status frame for backward          */
/* compatibility. Wheel Companion may opt in to a separate WL/V1 live-value   */
/* frame using the short leased WC control command.                           */
/*****************************************************************************/
#pragma once

#include <Arduino.h>

namespace LinkHealth
{
    void begin();
    void update();
}
