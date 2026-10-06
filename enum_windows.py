"""
Enumerate all native Windows belonging to this process.
Run this WHILE the diagnose_window.py app is running, then interact with
the app to trigger the bug, then run this again to see the window.

Usage: python enum_windows.py <pid>
Or just: python enum_windows.py (enumerates current process, not useful)
"""
import sys
import os
import ctypes
import ctypes.wintypes

def enum_process_windows(pid):
    user32 = ctypes.windll.user32
    windows = []
    
    def callback(hwnd, lparam):
        window_pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))
        if window_pid.value == pid:
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 256)
            cls_buf = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls_buf, 256)
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            visible = bool(user32.IsWindowVisible(hwnd))
            style = user32.GetWindowLongW(hwnd, -16)  # GWL_STYLE
            ex_style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
            windows.append({
                'hwnd': hwnd, 
                'title': title_buf.value, 
                'class': cls_buf.value, 
                'w': w, 'h': h, 
                'visible': visible,
                'style': style,
                'ex_style': ex_style,
            })
        return True
    
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    cb = WNDENUMPROC(callback)
    user32.EnumWindows(cb, 0)
    return windows

if __name__ == '__main__':
    if len(sys.argv) > 1:
        pid = int(sys.argv[1])
    else:
        pid = os.getpid()
    
    print(f'Enumerating windows for PID: {pid}')
    wins = enum_process_windows(pid)
    print(f'Found {len(wins)} top-level windows:')
    print()
    for win in wins:
        visible_mark = "VISIBLE" if win["visible"] else "hidden"
        hwnd = win["hwnd"]
        cls = win["class"]
        title = win["title"][:50]
        w = win["w"]
        h = win["h"]
        print(f'  HWND={hwnd:10d}  [{visible_mark:7s}]  {w:5d}x{h:4d}  class={cls!r:35s}  title={title!r}')
    
    print()
    print('Windows close to 150x70:')
    for win in wins:
        if 80 <= win["w"] <= 250 and 40 <= win["h"] <= 120:
            print(f'  MATCH: HWND={win["hwnd"]} {win["w"]}x{win["h"]} class={win["class"]!r} visible={win["visible"]} title={win["title"]!r}')
