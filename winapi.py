# -*- coding: utf-8 -*-
import ctypes
from ctypes import wintypes

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
LVM_FIRST = 0x1000
LVIF_TEXT = 0x0001
LVS_EX_SNAPTOGRID = 0x00080000
LVM_GETITEMCOUNT = LVM_FIRST + 4
LVM_SETITEMPOSITION = LVM_FIRST + 15
LVM_GETITEMTEXTW = LVM_FIRST + 115
LVM_SETEXTENDEDLISTVIEWSTYLE = LVM_FIRST + 54
LVM_GETEXTENDEDLISTVIEWSTYLE = LVM_FIRST + 55

PROCESS_VM_OPERATION = 0x0008
PROCESS_VM_READ = 0x0010
PROCESS_VM_WRITE = 0x0020
PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_ALL_ACCESS = 0x1F0FFF  # usually works; otherwise use finer-grained flags

MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
MEM_RELEASE = 0x8000
PAGE_READWRITE = 0x04

# --- LRESULT compatibility ---
if not hasattr(wintypes, "LRESULT"):
    wintypes.LRESULT = wintypes.LPARAM

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# Windows 10+: best option (Per-monitor DPI aware v2)
try:
    SetProcessDpiAwarenessContext = user32.SetProcessDpiAwarenessContext
    SetProcessDpiAwarenessContext.argtypes = [wintypes.HANDLE]
    SetProcessDpiAwarenessContext.restype = wintypes.BOOL
    DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = wintypes.HANDLE(-4)
    SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
except Exception:
    # Legacy fallback
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

# -----------------------------------------------------------------------------
# user32: FindWindowExW, SendMessageW, GetWindowThreadProcessId
# -----------------------------------------------------------------------------
FindWindowEx = user32.FindWindowExW
FindWindowEx.argtypes = [
    wintypes.HWND,    # hwndParent
    wintypes.HWND,    # hwndChildAfter
    wintypes.LPCWSTR, # lpszClass
    wintypes.LPCWSTR, # lpszWindow
]
FindWindowEx.restype = wintypes.HWND

SendMessage = user32.SendMessageW
# NOTE: no argtypes on purpose, since we sometimes pass ints and sometimes pointers
SendMessage.restype = wintypes.LRESULT

GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
GetWindowThreadProcessId.restype = wintypes.DWORD

# --- user32 extras ---
class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

GetCursorPos = user32.GetCursorPos
GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
GetCursorPos.restype = wintypes.BOOL

ScreenToClient = user32.ScreenToClient
ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
ScreenToClient.restype = wintypes.BOOL

ClientToScreen = user32.ClientToScreen
ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(POINT)]
ClientToScreen.restype = wintypes.BOOL

LVM_GETITEMPOSITION = LVM_FIRST + 16  # 0x1010

# -----------------------------------------------------------------------------
# kernel32: OpenProcess, VirtualAllocEx, Read/WriteProcessMemory, VirtualFreeEx
# -----------------------------------------------------------------------------
OpenProcess = kernel32.OpenProcess
OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
OpenProcess.restype = wintypes.HANDLE

VirtualAllocEx = kernel32.VirtualAllocEx
VirtualAllocEx.argtypes = [
    wintypes.HANDLE,  # hProcess
    wintypes.LPVOID,  # lpAddress
    ctypes.c_size_t,  # dwSize
    wintypes.DWORD,   # flAllocationType
    wintypes.DWORD,   # flProtect
]
VirtualAllocEx.restype = wintypes.LPVOID

WriteProcessMemory = kernel32.WriteProcessMemory
WriteProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.LPCVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
WriteProcessMemory.restype = wintypes.BOOL

ReadProcessMemory = kernel32.ReadProcessMemory
ReadProcessMemory.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.LPVOID,
    ctypes.c_size_t,
    ctypes.POINTER(ctypes.c_size_t),
]
ReadProcessMemory.restype = wintypes.BOOL

VirtualFreeEx = kernel32.VirtualFreeEx
VirtualFreeEx.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    ctypes.c_size_t,
    wintypes.DWORD,
]
VirtualFreeEx.restype = wintypes.BOOL

CloseHandle = kernel32.CloseHandle
CloseHandle.argtypes = [wintypes.HANDLE]
CloseHandle.restype = wintypes.BOOL

# -----------------------------------------------------------------------------
# LVITEMW structure (wide / Unicode)
# -----------------------------------------------------------------------------
class LVITEMW(ctypes.Structure):
    _fields_ = [
        ("mask", wintypes.UINT),
        ("iItem", wintypes.INT),
        ("iSubItem", wintypes.INT),
        ("state", wintypes.UINT),
        ("stateMask", wintypes.UINT),
        ("pszText", wintypes.LPWSTR),
        ("cchTextMax", wintypes.INT),
        ("iImage", wintypes.INT),
        ("lParam", wintypes.LPARAM),
        ("iIndent", wintypes.INT),
        ("iGroupId", wintypes.INT),
        ("cColumns", wintypes.UINT),
        ("puColumns", ctypes.POINTER(wintypes.UINT)),
        ("piColFmt", ctypes.POINTER(ctypes.c_int)),
        ("iGroup", ctypes.c_int),
    ]


# -----------------------------------------------------------------------------
# Helper: allocate remote memory
# -----------------------------------------------------------------------------
def remote_alloc(hProcess, size):
    addr = VirtualAllocEx(
        hProcess,
        None,
        size,
        MEM_COMMIT | MEM_RESERVE,
        PAGE_READWRITE,
    )
    if not addr:
        err = ctypes.get_last_error()
        raise OSError(err, f"VirtualAllocEx failed with error {err:#x}")
    return addr


def remote_free(hProcess, addr):
    if addr:
        if not VirtualFreeEx(hProcess, addr, 0, MEM_RELEASE):
            err = ctypes.get_last_error()
            print(f"[warn] VirtualFreeEx error {err:#x}")