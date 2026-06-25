import ctypes
from ctypes import wintypes
import sys

ole32 = ctypes.windll.ole32
shell32 = ctypes.windll.shell32
gdi32 = ctypes.windll.gdi32

class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]

class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_byte * 8)]

IID_IShellItemImageFactory = GUID(0xBCC18B79, 0xBA16, 0x442F, (0x80, 0xC4, 0x8A, 0x59, 0xC3, 0x0C, 0x46, 0x3B))

def get_shell_thumbnail(path: str, width: int, height: int):
    ole32.CoInitialize(None)
    shellItem = ctypes.c_void_p()
    hr = shell32.SHCreateItemFromParsingName(
        ctypes.c_wchar_p(path),
        None,
        ctypes.byref(IID_IShellItemImageFactory),
        ctypes.byref(shellItem)
    )
    if hr != 0:
        print("SHCreateItemFromParsingName failed", hex(hr & 0xffffffff))
        return None

    HRESULT = wintypes.LONG
    GetImageProto = ctypes.WINFUNCTYPE(
        HRESULT,
        ctypes.c_void_p,
        SIZE,
        ctypes.c_int,
        ctypes.POINTER(wintypes.HBITMAP)
    )
    
    vtable_pointer = ctypes.cast(shellItem, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))
    vtable = vtable_pointer.contents
    GetImage = ctypes.cast(vtable[3], GetImageProto)
    
    hbitmap = wintypes.HBITMAP()
    size = SIZE(width, height)
    
    for flags in (0x00, 0x04, 0x02, 0x10):
        hr = GetImage(shellItem, size, flags, ctypes.byref(hbitmap))
        if hr == 0 and hbitmap:
            print("Success with flag", hex(flags))
            break
    
    ReleaseProto = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)
    Release = ctypes.cast(vtable[2], ReleaseProto)
    Release(shellItem)
    
    if hr == 0 and hbitmap:
        return hbitmap.value
    else:
        print("GetImage failed", hex(hr & 0xffffffff))
    return None

if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage
    app = QApplication(sys.argv)
    # Test on the Python script itself
    hbm = get_shell_thumbnail(r"C:\Users\Yuran\Documents\Programming\archive_manager\main.py", 256, 256)
    print("HBITMAP:", hbm)
    if hbm:
        img = QImage.fromHBITMAP(hbm)
        print("QImage size:", img.size())
        gdi32.DeleteObject(wintypes.HBITMAP(hbm))
