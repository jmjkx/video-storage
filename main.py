import os
import time
import subprocess

import win32gui
import win32con
import win32api

# ==========================================================

# 配置区

# ==========================================================

MPV_PATH = r"C:\Users\GodY\source\dynamicWallpaper\mpv.exe"

VIDEO_1 = r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\68c4f94992d000f8170d0804\1756865729049_rbYQT.mp4"  # 屏幕1的视频
VIDEO_2 = r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\6830aff9e0666a85c1287e9f\1744473562760_0vR-m.mp4"  # 屏幕2的视频

# ==========================================================

# WorkerW 获取（Win10 / Win11 通用）

# ==========================================================

def get_desktop_workerw():
    progman = win32gui.FindWindow(
        "Progman",
        "Program Manager"
    )

    if not progman:
        return 0

    try:
        win32gui.SendMessageTimeout(
            progman,
            0x052C,
            0,
            0,
            0,
            1000
        )
    except:
        pass

    target_workerw = 0

    def enum_windows(hwnd, _):
        nonlocal target_workerw

        shell_view = win32gui.FindWindowEx(
            hwnd,
            0,
            "SHELLDLL_DefView",
            None
        )

        if shell_view:
            workerw = win32gui.FindWindowEx(
                0,
                hwnd,
                "WorkerW",
                None
            )

            if workerw:
                target_workerw = workerw

    win32gui.EnumWindows(
        enum_windows,
        None
    )

    if target_workerw:
        return target_workerw

    workerw = win32gui.FindWindowEx(
        progman,
        0,
        "WorkerW",
        None
    )

    if workerw:
        return workerw

    return progman

# ==========================================================

# 调试用

# ==========================================================

def dump_desktop_structure():
    print("\n========== Desktop Structure ==========\n")

    def enum_windows(hwnd, _):
        cls = win32gui.GetClassName(hwnd)

        if cls in ("Progman", "WorkerW"):
            print(
                f"TOP: {hwnd} {cls} "
                f"{win32gui.GetWindowText(hwnd)}"
            )

            child = win32gui.FindWindowEx(
                hwnd,
                0,
                None,
                None
            )

            while child:
                print(
                    "   CHILD:",
                    child,
                    win32gui.GetClassName(child),
                    win32gui.GetWindowText(child)
                )

                child = win32gui.FindWindowEx(
                    hwnd,
                    child,
                    None,
                    None
                )

    win32gui.EnumWindows(
        enum_windows,
        None
    )

    print("\n=======================================\n")

# ==========================================================

# 获取显示器

# ==========================================================

def get_monitors():
    monitors = []

    for monitor in win32api.EnumDisplayMonitors():
        _, _, rect = monitor

        left, top, right, bottom = rect

        monitors.append({
            "x": left,
            "y": top,
            "width": right - left,
            "height": bottom - top
        })

    monitors.sort(
        key=lambda m: (
            m["y"],
            m["x"]
        )
    )

    return monitors

# ==========================================================

# 查找 mpv 窗口

# ==========================================================

def find_window(title, timeout=15):
    start = time.time()

    while time.time() - start < timeout:
        result = []

        def enum_callback(hwnd, _):
            text = win32gui.GetWindowText(hwnd)

            if title in text:
                result.append(hwnd)

        win32gui.EnumWindows(
            enum_callback,
            None
        )

        if result:
            return result[0]

        time.sleep(0.2)

    return None

# ==========================================================

# 启动单个壁纸

# ==========================================================

def start_wallpaper(
    video_path,
    title,
    workerw,
    monitor
):
    cmd = [
        MPV_PATH,
        video_path,

        "--force-window=yes",
        "--no-border",

        "--loop-file=inf",
        "--keep-open=yes",

        "--vo=gpu",
        "--gpu-context=d3d11",

        "--no-audio",
        "--no-osc",

        f"--title={title}",
    ]

    subprocess.Popen(cmd)

    hwnd = find_window(title)

    if not hwnd:
        print(
            f"[ERROR] 找不到窗口: {title}"
        )
        return

    style = win32gui.GetWindowLong(
        hwnd,
        win32con.GWL_STYLE
    )

    style |= win32con.WS_CHILD
    style &= ~win32con.WS_POPUP

    win32gui.SetWindowLong(
        hwnd,
        win32con.GWL_STYLE,
        style
    )

    win32gui.SetParent(
        hwnd,
        workerw
    )

    worker_rect = win32gui.GetWindowRect(
        workerw
    )

    worker_x = worker_rect[0]
    worker_y = worker_rect[1]

    local_x = monitor["x"] - worker_x
    local_y = monitor["y"] - worker_y

    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_BOTTOM,

        local_x,
        local_y,

        monitor["width"],
        monitor["height"],

        win32con.SWP_SHOWWINDOW
        | win32con.SWP_FRAMECHANGED
    )

    win32gui.ShowWindow(
        hwnd,
        win32con.SW_SHOW
    )

    print("\n--------------------------------")
    print(title)
    print("monitor =", monitor)
    print("worker_rect =", worker_rect)
    print("local =", local_x, local_y)
    print(
        "actual rect =",
        win32gui.GetWindowRect(hwnd)
    )
    print("--------------------------------\n")

# ==========================================================

# 主函数

# ==========================================================

def main():
    if not os.path.exists(MPV_PATH):
        print("mpv.exe不存在")
        return

    if not os.path.exists(VIDEO_1):
        print("VIDEO_1不存在")
        return

    if not os.path.exists(VIDEO_2):
        print("VIDEO_2不存在")
        return

    workerw = get_desktop_workerw()

    print("workerw =", workerw)

    if not workerw:
        print("获取 WorkerW 失败")
        return

    monitors = get_monitors()

    print("monitors =", monitors)

    if len(monitors) < 2:
        print("检测不到双显示器")
        return

    start_wallpaper(
        VIDEO_1,
        "WALL_LEFT",
        workerw,
        monitors[0]
    )

    time.sleep(1)

    start_wallpaper(
        VIDEO_2,
        "WALL_RIGHT",
        workerw,
        monitors[1]
    )

    print("\n动态壁纸启动成功\n")

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
