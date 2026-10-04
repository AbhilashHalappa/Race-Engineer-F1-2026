"""Windows-target display/runtime diagnostics used by release readiness checks."""
from __future__ import annotations

import os
import platform


def display_environment() -> dict:
    result={"windows":os.name=="nt","platform":platform.platform(),"monitor_count":None,"virtual_screen":None,"dpi":None,"scale_percent":None,"high_dpi_capable":None}
    if os.name != 'nt':
        return result
    try:
        import ctypes
        user32=ctypes.windll.user32
        result["monitor_count"]=int(user32.GetSystemMetrics(80))  # SM_CMONITORS
        x=int(user32.GetSystemMetrics(76)); y=int(user32.GetSystemMetrics(77))
        w=int(user32.GetSystemMetrics(78)); h=int(user32.GetSystemMetrics(79))
        result["virtual_screen"]={"x":x,"y":y,"width":w,"height":h}
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
        hdc=user32.GetDC(0)
        try:
            gdi32=ctypes.windll.gdi32; dpi=int(gdi32.GetDeviceCaps(hdc,88))  # LOGPIXELSX
        finally:
            user32.ReleaseDC(0,hdc)
        result["dpi"]=dpi; result["scale_percent"]=round(dpi/96*100); result["high_dpi_capable"]=dpi>0
    except Exception as error:
        result["error"]=str(error)
    return result
