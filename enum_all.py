"""
Enumerate ALL top-level windows for a given PID AND its child processes.
Run this from a separate terminal WHILE the app is running and the second window is visible.

Usage: python enum_all.py <pid>
"""
import sys
import ctypes
import ctypes.wintypes
import subprocess

def get_child_pids(parent_pid):
    """Get all child process PIDs of parent_pid using wmic."""
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where', f'ParentProcessId={parent_pid}', 'get', 'ProcessId,Name'],
            capture_output=True, text=True, timeout=5
        )
        pids = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and not line.startswith('ProcessId'):
                parts = line.split()
                if parts:
                    try:
                        pids.append(int(parts[-1]))
                    except ValueError:
                        pass
        return pids
    except Exception as e:
        print(f"[WMIC error] {e}")
        return []

def enum_all_windows_all_pids(pids_set):
    user32 = ctypes.windll.user32
    wins = []
    def cb(hwnd, _):
        pid_c = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_c))
        if pid_c.value in pids_set:
            tbuf = ctypes.create_unicode_buffer(512)
            cbuf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, tbuf, 512)
            user32.GetClassNameW(hwnd, cbuf, 256)
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            parent = user32.GetParent(hwnd)
            owner = user32.GetWindow(hwnd, 4)
            visible = bool(user32.IsWindowVisible(hwnd))
            wins.append({
                'hwnd': hwnd, 'pid': pid_c.value,
                'title': tbuf.value, 'class': cbuf.value,
                'w': w, 'h': h, 'parent': parent, 'owner': owner,
                'visible': visible,
            })
        return True
    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    user32.EnumWindows(WNDENUMPROC(cb), 0)
    return wins

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python enum_all.py <main_pid>")
        sys.exit(1)
    
    main_pid = int(sys.argv[1])
    child_pids = get_child_pids(main_pid)
    all_pids = {main_pid} | set(child_pids)
    
    print(f"Main PID: {main_pid}")
    print(f"Child PIDs: {child_pids}")
    print(f"Total PIDs to scan: {sorted(all_pids)}")
    print()
    
    wins = enum_all_windows_all_pids(all_pids)
    print(f"Found {len(wins)} windows across all processes:")
    print()
    for w in wins:
        is_top = (w['parent'] == 0 and w['owner'] == 0)
        mark = "TOP" if is_top else "CHD"
        print(f"[{mark}] HWND={w['hwnd']:10d}  PID={w['pid']:7d}  "
              f"vis={int(w['visible'])}  {w['w']:5d}x{w['h']:4d}  "
              f"class={w['class']!r:40s}  title={w['title'][:50]!r}")
