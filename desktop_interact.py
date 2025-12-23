import os
from winapi import *

# -----------------------------------------------------------------------------
# Helper: get the desktop SysListView32
# -----------------------------------------------------------------------------
def get_desktop_listview():
    progman = FindWindowEx(0, 0, "Progman", None)
    defview = FindWindowEx(progman, 0, "SHELLDLL_DefView", None)

    if not defview:
        workerw = FindWindowEx(0, 0, "WorkerW", None)
        while workerw and not defview:
            defview = FindWindowEx(workerw, 0, "SHELLDLL_DefView", None)
            workerw = FindWindowEx(0, workerw, "WorkerW", None)

    if not defview:
        return None

    listview = FindWindowEx(defview, 0, "SysListView32", None)
    return listview


# -----------------------------------------------------------------------------
# Helper: open the process that owns the ListView
# -----------------------------------------------------------------------------
def open_listview_process(hwnd):
    pid = wintypes.DWORD(0)
    thread_id = GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if thread_id == 0 or pid.value == 0:
        raise RuntimeError("Failed to get the ListView PID")

    # print(f"[dbg] ListView PID (explorer) = {pid.value}, Python PID = {os.getpid()}")

    # Try ALL_ACCESS; if it fails, you can narrow the required flags
    hProcess = OpenProcess(PROCESS_ALL_ACCESS, False, pid.value)
    if not hProcess:
        err = ctypes.get_last_error()
        raise OSError(err, f"OpenProcess failed with error {err:#x}")

    return hProcess


# -----------------------------------------------------------------------------
# get_icon_name(index)
# -----------------------------------------------------------------------------
def get_icon_name(index):
    listview = get_desktop_listview()
    if not listview:
        print("Desktop ListView not found")
        return None

    # Number of icons
    count = SendMessage(listview, LVM_GETITEMCOUNT, 0, 0)
    print("[dbg] Desktop icons reported by ListView:", count)
    if index < 0 or index >= count:
        print("Index out of range")
        return None

    # Open the ListView owner process (explorer.exe)
    hProcess = open_listview_process(listview)

    # Structure sizes
    text_max = 260
    local_text_buffer = ctypes.create_unicode_buffer(text_max)
    lvitem_local = LVITEMW()
    lvitem_size = ctypes.sizeof(LVITEMW)

    try:
        # Allocate remote memory: first for the text buffer, then for the LVITEM
        remote_text = remote_alloc(hProcess, text_max * ctypes.sizeof(ctypes.c_wchar))
        remote_lvitem = remote_alloc(hProcess, lvitem_size)

        # Prepare local LVITEM, but with pszText pointing to remote_text (in the remote process)
        lvitem_local.mask = LVIF_TEXT
        lvitem_local.iItem = index
        lvitem_local.iSubItem = 0
        lvitem_local.state = 0
        lvitem_local.stateMask = 0
        # Cast the remote address to LPWSTR
        lvitem_local.pszText = ctypes.cast(remote_text, wintypes.LPWSTR)
        lvitem_local.cchTextMax = text_max
        lvitem_local.iImage = 0
        lvitem_local.lParam = 0
        lvitem_local.iIndent = 0
        lvitem_local.iGroupId = 0
        lvitem_local.cColumns = 0
        lvitem_local.puColumns = None
        lvitem_local.piColFmt = None
        lvitem_local.iGroup = 0

        # Write LVITEM into remote memory
        written = ctypes.c_size_t(0)
        ok = WriteProcessMemory(
            hProcess,
            remote_lvitem,
            ctypes.byref(lvitem_local),
            lvitem_size,
            ctypes.byref(written),
        )
        if not ok or written.value != lvitem_size:
            err = ctypes.get_last_error()
            raise OSError(err, f"WriteProcessMemory(LVITEM) failed: {err:#x}")

        # Send the message to the ListView using the remote LVITEM pointer
        SendMessage(listview, LVM_GETITEMTEXTW, index, remote_lvitem)

        # Read the text from remote memory into the local buffer
        read = ctypes.c_size_t(0)
        ok = ReadProcessMemory(
            hProcess,
            remote_text,
            local_text_buffer,
            text_max * ctypes.sizeof(ctypes.c_wchar),
            ctypes.byref(read),
        )
        if not ok:
            err = ctypes.get_last_error()
            raise OSError(err, f"ReadProcessMemory(text) failed: {err:#x}")

        # Return the buffer value (Python string)
        return local_text_buffer.value

    finally:
        # Free remote memory and close handle
        remote_free(hProcess, remote_text)
        remote_free(hProcess, remote_lvitem)
        CloseHandle(hProcess)


# -----------------------------------------------------------------------------
# move_first_icon(x, y)
# -----------------------------------------------------------------------------
def move_first_icon(x, y):
    listview = get_desktop_listview()
    if not listview:
        print("Desktop icon list not found")
        return

    count = SendMessage(listview, LVM_GETITEMCOUNT, 0, 0)
    print("Total icons:", count)
    if count == 0:
        print("No icons")
        return

    lparam = (x & 0xFFFF) | (y << 16)
    SendMessage(listview, LVM_SETITEMPOSITION, 0, lparam)
    print(f"Icon 0 moved to ({x}, {y})")


def move_icon(index, x, y):
    listview = get_desktop_listview()
    if not listview:
        return

    # ListView client coordinates
    lparam = (int(x) & 0xFFFF) | ((int(y) & 0xFFFF) << 16)
    SendMessage(listview, LVM_SETITEMPOSITION, index, lparam)


def get_item_count() -> int:
    listview = get_desktop_listview()
    count = SendMessage(listview, LVM_GETITEMCOUNT, 0, 0)
    return count

def disable_snap_to_grid() -> bool:
    listview = get_desktop_listview()
    if not listview:
        return False

    # Clear only the SNAPTOGRID bit (mask in wParam)
    SendMessage(listview, LVM_SETEXTENDEDLISTVIEWSTYLE, LVS_EX_SNAPTOGRID, 0)

    # Verify
    ex_style = int(SendMessage(listview, LVM_GETEXTENDEDLISTVIEWSTYLE, 0, 0))
    return (ex_style & LVS_EX_SNAPTOGRID) == 0