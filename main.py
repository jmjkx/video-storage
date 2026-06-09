import os
import time
import subprocess

import win32gui
import win32con
import win32api

MPV_PATH = r"C:\Users\GodY\source\dynamicWallpaper\mpv.exe"

VIDEO_PATH = r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\68c4f94992d000f8170d0804\1756865729049_rbYQT.mp4"


def get_desktop_workerw():
    """
    根据你机器实际情况获取桌面 WorkerW

    Progman
      ├─ SHELLDLL_DefView
      └─ WorkerW  <-- 目标
    """

    progman = win32gui.FindWindow(
        "Progman",
        "Program Manager"
    )

    if not progman:
        return 0

    workerw = win32gui.FindWindowEx(
        progman,
        0,
        "WorkerW",
        None
    )

    if workerw:
        return workerw

    return progman


def find_window(title, timeout=15):

    start = time.time()

    while time.time() - start < timeout:

        result = []

        def enum_callback(hwnd, _):

            text = win32gui.GetWindowText(hwnd)

            if title in text:
                result.append(hwnd)

        win32gui.EnumWindows(enum_callback, None)

        if result:
            return result[0]

        time.sleep(0.2)

    return None


def main():

    if not os.path.exists(MPV_PATH):
        print("mpv不存在")
        return

    if not os.path.exists(VIDEO_PATH):
        print("视频不存在")
        return

    workerw = get_desktop_workerw()

    print("workerw =", workerw)

    if not workerw:
        print("获取WorkerW失败")
        return

    title = "MY_WALLPAPER_TEST"

    cmd = [
        MPV_PATH,
        VIDEO_PATH,

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

    print("启动 mpv...")

    subprocess.Popen(cmd)

    hwnd = find_window(title)

    print("mpv hwnd =", hwnd)

    if not hwnd:
        print("找不到 mpv 窗口")
        return

    print("原始 parent =", win32gui.GetParent(hwnd))
    print("原始 rect =", win32gui.GetWindowRect(hwnd))

    # 修改窗口样式
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

    # 挂到桌面
    win32gui.SetParent(
        hwnd,
        workerw
    )

    print("新 parent =", win32gui.GetParent(hwnd))

    # 获取主显示器尺寸
    width = win32api.GetSystemMetrics(0)
    height = win32api.GetSystemMetrics(1)

    win32gui.SetWindowPos(
        hwnd,
        win32con.HWND_BOTTOM,
        0,
        0,
        width,
        height,
        win32con.SWP_SHOWWINDOW
        | win32con.SWP_FRAMECHANGED
    )

    win32gui.ShowWindow(
        hwnd,
        win32con.SW_SHOW
    )

    win32gui.UpdateWindow(hwnd)

    print("完成")
    print("如果成功，现在应该能看到视频在桌面图标下面播放")

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()