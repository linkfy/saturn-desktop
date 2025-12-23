# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes
import os

from winapi import *
from desktop_interact import open_listview_process, get_desktop_listview


def get_mouse_screen_pos():
    pt = POINT()
    if not GetCursorPos(ctypes.byref(pt)):
        raise OSError(ctypes.get_last_error(), "GetCursorPos failed")
    return pt.x, pt.y


def get_icon_client_pos(listview_hwnd, index):
    # LVM_GETITEMPOSITION writes a POINT into lParam (a pointer). Since the ListView
    # belongs to another process, we use remote memory the same way as with LVITEM.
    hProcess = open_listview_process(listview_hwnd)
    try:
        remote_pt = remote_alloc(hProcess, ctypes.sizeof(POINT))
        SendMessage(listview_hwnd, LVM_GETITEMPOSITION, index, remote_pt)

        local_pt = POINT()
        read = ctypes.c_size_t(0)
        ok = ReadProcessMemory(
            hProcess,
            remote_pt,
            ctypes.byref(local_pt),
            ctypes.sizeof(POINT),
            ctypes.byref(read),
        )
        if not ok:
            err = ctypes.get_last_error()
            raise OSError(err, f"ReadProcessMemory(POINT) failed: {err:#x}")

        return local_pt.x, local_pt.y

    finally:
        remote_free(hProcess, remote_pt)
        CloseHandle(hProcess)


def get_mouse_pos_relative_to_icon(index=0):
    listview = get_desktop_listview()
    if not listview:
        raise RuntimeError("Desktop ListView not found")

    # Mouse: screen coords -> ListView client coords
    mx, my = get_mouse_screen_pos()
    mpt = POINT(mx, my)
    if not ScreenToClient(listview, ctypes.byref(mpt)):
        raise OSError(ctypes.get_last_error(), "ScreenToClient failed")

    # Icon position in ListView client coords
    ix, iy = get_icon_client_pos(listview, index)

    dx = mpt.x - ix
    dy = mpt.y - iy
    return {
        "mouse_screen": (mx, my),
        "mouse_client": (mpt.x, mpt.y),
        "icon_client": (ix, iy),
        "delta": (dx, dy),
    }


# Example usage:
# info = get_mouse_pos_relative_to_icon(0)
# print(info)