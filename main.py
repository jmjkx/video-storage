import os
import time
import subprocess

import win32gui
import win32con
import win32api

MPV_PATH = r"C:\Users\GodY\source\dynamicWallpaper\mpv.exe"

VIDEO_1 = r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\68c4f94992d000f8170d0804\1756865729049_rbYQT.mp4"  # 屏幕1的视频
VIDEO_2 = r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\6830aff9e0666a85c1287e9f\1744473562760_0vR-m.mp4"  # 屏幕2的视频


def get_desktop_workerw():

    progman = win32gui.FindWindow(
        "Progman",
        "Program Manager"
    )

    workerw = win32gui.FindWindowEx(
        progman,
        0,
        "WorkerW",
        None
    )

    return workerw


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

    monitors.sort(key=lambda m: m["x"])

    return monitors


def find_window(title, timeout=15):

    start = time.time()

    while time.time() - start < timeout:

        found = []

        def enum_callback(hwnd, _):

            text = win32gui.GetWindowText(hwnd)

            if title in text:
                found.append(hwnd)

        win32gui.EnumWindows(enum_callback, None)

        if found:
            return found[0]

        time.sleep(0.2)

    return None


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
        print("找不到窗口:", title)
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

    worker_rect = win32gui.GetWindowRect(workerw)

    worker_x = worker_rect[0]
    worker_y = worker_rect[1]

    local_x = monitor["x"] - worker_x
    local_y = monitor["y"] - worker_y

    print("worker_rect =", worker_rect)
    print("local =", local_x, local_y)

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

    rect = win32gui.GetWindowRect(hwnd)

    print(title)
    print("monitor =", monitor)
    print("actual rect =", rect)


def main():

    workerw = get_desktop_workerw()

    print("workerw =", workerw)

    monitors = get_monitors()

    print("monitors =", monitors)

    if len(monitors) < 2:
        print("检测不到双屏")
        return

    # 左边屏幕
    start_wallpaper(
        VIDEO_1,
        "WALL_LEFT",
        workerw,
        monitors[0]
    )

    time.sleep(1)

    # 右边屏幕
    start_wallpaper(
        VIDEO_2,
        "WALL_RIGHT",
        workerw,
        monitors[1]
    )

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()