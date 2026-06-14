import os
import time
import json
import subprocess
import threading

import win32gui
import win32con
import win32api

# ==========================================================
# 全局常量与运行状态控制中心
# ==========================================================
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

PIPE_LEFT = r"\\.\pipe\mpv-wallpaper-left"
PIPE_RIGHT = r"\\.\pipe\mpv-wallpaper-right"

# 核心全局状态字典：跟踪子进程句柄、窗口句柄及上一次应用的配置
runtime_instances = {
    "left": {"proc": None, "hwnd": None, "config": None, "pipe": PIPE_LEFT, "title": "WALL_LEFT", "index": 0},
    "right": {"proc": None, "hwnd": None, "config": None, "pipe": PIPE_RIGHT, "title": "WALL_RIGHT", "index": 1}
}

global_config = {
    "mpv_path": ""
}

# ==========================================================
# 自动生成默认配置文件（防止首次运行报错）
# ==========================================================
def ensure_default_config():
    if not os.path.exists(CONFIG_FILE):
        default_cfg = {
            "mpv_path": r"C:\Users\GodY\source\dynamicWallpaper\mpv.exe",
            "monitors": {
                "left": {
                    "enable": True,
                    "video_path": r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\68c4f94992d000f8170d0804\1756865729049_rbYQT.mp4",
                    "speed": 1.0,
                    "mute": True
                },
                "right": {
                    "enable": True,
                    "video_path": r"C:\Users\GodY\OneDrive\Videos\LiveWallpaper\6830aff9e0666a85c1287e9f\1744473562760_0vR-m.mp4",
                    "speed": 1.0,
                    "mute": True
                }
            }
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_cfg, f, indent=4, ensure_ascii=False)
        print(f"[配置初始化] 已在脚本同级目录生成默认配置文件: {CONFIG_FILE}")

# ==========================================================
# IPC 命名管道控制
# ==========================================================
def send_mpv_command(pipe_name, command_str):
    """通过 Windows 命名管道向指定 mpv 实例发送控制指令"""
    try:
        fd = os.open(pipe_name, os.O_WRONLY | os.O_BINARY)
        os.write(fd, f"{command_str}\n".encode('utf-8'))
        os.close(fd)
        return True
    except:
        return False

# ==========================================================
# MPV 实例生命周期管理 (支持动态创建与销毁)
# ==========================================================
def stop_wallpaper_instance(key):
    """安全关闭并清理指定屏幕的 MPV 进程"""
    inst = runtime_instances[key]
    if inst["proc"]:
        print(f"[{key.upper()}] 正在关闭并注销壁纸窗口...")
        # 优先通过 IPC 发送退出命令
        if not send_mpv_command(inst["pipe"], "quit"):
            # 如果 IPC 无响应，则强行终止进程
            try:
                inst["proc"].terminate()
                inst["proc"].wait(timeout=1)
            except:
                try:
                    inst["proc"].kill()
                except:
                    pass
        inst["proc"] = None
        inst["hwnd"] = None

def start_wallpaper_instance(key, cfg, workerw, monitor):
    """为指定屏幕初始化、拉起并挂载新的 MPV 实例"""
    inst = runtime_instances[key]

    # 路径安全性预检
    if not os.path.exists(cfg["video_path"]):
        print(f"[ERROR] [{key.upper()}] 视频路径不存在: {cfg['video_path']}")
        return False

    safe_path = cfg["video_path"].replace("\\", "/")
    mute_str = "yes" if cfg["mute"] else "no"

    cmd = [
        global_config["mpv_path"],
        safe_path,
        f"--input-ipc-server={inst['pipe']}",
        f"--speed={cfg['speed']}",
        f"--mute={mute_str}",
        "--force-window=yes",
        "--no-border",
        "--loop-file=inf",
        "--keep-open=yes",
        "--vo=gpu",
        "--gpu-context=d3d11",
        "--no-osc",
        f"--title={inst['title']}",
    ]

    proc = subprocess.Popen(cmd)
    hwnd = find_window(inst["title"])

    if not hwnd:
        print(f"[ERROR] [{key.upper()}] 捕获 MPV 窗口超时")
        try:
            proc.kill()
        except:
            pass
        return False

    # Win32 样式修改：剥离独立窗口属性，注入 Child 属性
    style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)
    style |= win32con.WS_CHILD
    style &= ~win32con.WS_POPUP
    win32gui.SetWindowLong(hwnd, win32con.GWL_STYLE, style)
    win32gui.SetParent(hwnd, workerw)

    # 坐标系转换至桌面边界
    worker_rect = win32gui.GetWindowRect(workerw)
    local_x = monitor["x"] - worker_rect[0]
    local_y = monitor["y"] - worker_rect[1]

    win32gui.SetWindowPos(
        hwnd, win32con.HWND_BOTTOM,
        local_x, local_y, monitor["width"], monitor["height"],
        win32con.SWP_SHOWWINDOW | win32con.SWP_FRAMECHANGED
    )
    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

    # 封存当前实例的运行时句柄
    inst["proc"] = proc
    inst["hwnd"] = hwnd
    return True

# ==========================================================
# 核心差分机：实现全配置热修改与开关响应
# ==========================================================
def dispatch_hot_changes(key, new_cfg, workerw, monitor):
    """对比新旧配置，决策应该拉起、销毁还是通过 IPC 修改 MPV 属性"""
    inst = runtime_instances[key]
    old_cfg = inst["config"]

    old_enable = old_cfg.get("enable", False) if old_cfg else False
    new_enable = new_cfg.get("enable", False)

    # 情况 1: 原本关闭 -> 现在开启 (冷启动)
    if not old_enable and new_enable:
        print(f"[{key.upper()}] 检测到热配置：唤醒屏幕壁纸层...")
        if start_wallpaper_instance(key, new_cfg, workerw, monitor):
            inst["config"] = new_cfg.copy()
        return

    # 情况 2: 原本开启 -> 现在关闭 (热销毁)
    if old_enable and not new_enable:
        print(f"[{key.upper()}] 检测到热配置：关闭当前屏幕壁纸层")
        stop_wallpaper_instance(key)
        inst["config"] = new_cfg.copy()
        return

    # 情况 3: 持续开启状态 -> 执行细分参数的 IPC 差分同步
    if old_enable and new_enable:
        # 如果对应的进程离奇死亡，强制转为冷启动修复
        if not inst["proc"] or inst["proc"].poll() is not None:
            start_wallpaper_instance(key, new_cfg, workerw, monitor)
            inst["config"] = new_cfg.copy()
            return

        pipe = inst["pipe"]

        # A. 视频路径变动 -> 通过 IPC 执行无缝 loadfile
        if new_cfg["video_path"] != old_cfg["video_path"]:
            if os.path.exists(new_cfg["video_path"]):
                safe_path = new_cfg["video_path"].replace("\\", "/")
                print(f"[{key.upper()}] 热热换源 -> {os.path.basename(safe_path)}")
                send_mpv_command(pipe, f'loadfile "{safe_path}"')
                time.sleep(0.1)  # 缓冲防抖，确保属性不被载入重置
                send_mpv_command(pipe, f'set speed {new_cfg["speed"]}')
                send_mpv_command(pipe, f'set mute {"yes" if new_cfg["mute"] else "no"}')
            else:
                print(f"[警告] 忽略无效的目标视频路径: {new_cfg['video_path']}")

        # B. 播放速率变动 -> 动态调速
        elif new_cfg["speed"] != old_cfg["speed"]:
            print(f"[{key.upper()}] 热调速率 -> {new_cfg['speed']}x")
            send_mpv_command(pipe, f'set speed {new_cfg["speed"]}')

        # C. 静音状态变动 -> 动态切音频
        if new_cfg["mute"] != old_cfg["mute"]:
            mute_str = "yes" if new_cfg["mute"] else "no"
            print(f"[{key.upper()}] 热切静音 -> {mute_str}")
            send_mpv_command(pipe, f'set mute {mute_str}')

        inst["config"] = new_cfg.copy()
        return

    # 情况 4: 原本关闭 -> 现在依然关闭
    if not old_enable and not new_enable:
        inst["config"] = new_cfg.copy()

# ==========================================================
# 后台异步线程：零延迟监控配置文件
# ==========================================================
def monitor_config_thread(workerw, monitors):
    last_mtime = os.path.getmtime(CONFIG_FILE)
    global global_config

    while True:
        time.sleep(1.0)
        try:
            current_mtime = os.path.getmtime(CONFIG_FILE)
            if current_mtime > last_mtime:
                last_mtime = current_mtime
                print("\n[系统通知] 检测到 config.json 更新，正在同步状态机...")

                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    new_data = json.load(f)

                # 处理 mpv.exe 核心路径本身发生改变的极端热配置情况
                new_mpv = new_data.get("mpv_path", "")
                if new_mpv != global_config["mpv_path"]:
                    print("[系统通知] 核心 MPV 引擎路径变更，正在重启所有服务集群...")
                    global_config["mpv_path"] = new_mpv
                    # 销毁后由下方的比较器重新拉起
                    stop_wallpaper_instance("left")
                    stop_wallpaper_instance("right")

                monitors_cfg = new_data.get("monitors", {})

                if "left" in monitors_cfg and len(monitors) > 0:
                    dispatch_hot_changes("left", monitors_cfg["left"], workerw, monitors[0])
                if "right" in monitors_cfg and len(monitors) > 1:
                    dispatch_hot_changes("right", monitors_cfg["right"], workerw, monitors[1])

        except Exception as e:
            print(f"[监控线程异常] 同步错误: {e}")

# ==========================================================
# Windows 底层句柄和显示器拓扑获取
# ==========================================================
def get_desktop_workerw():
    progman = win32gui.FindWindow("Progman", "Program Manager")
    if not progman:
        return 0
    try:
        win32gui.SendMessageTimeout(progman, 0x052C, 0, 0, 0, 1000)
    except:
        pass
    target_workerw = 0
    def enum_windows(hwnd, _):
        nonlocal target_workerw
        shell_view = win32gui.FindWindowEx(hwnd, 0, "SHELLDLL_DefView", None)
        if shell_view:
            workerw = win32gui.FindWindowEx(0, hwnd, "WorkerW", None)
            if workerw:
                target_workerw = workerw
    win32gui.EnumWindows(enum_windows, None)
    if target_workerw:
        return target_workerw
    workerw = win32gui.FindWindowEx(progman, 0, "WorkerW", None)
    return workerw if workerw else progman

def get_monitors():
    monitors = []
    for monitor in win32api.EnumDisplayMonitors():
        _, _, rect = monitor
        left, top, right, bottom = rect
        monitors.append({"x": left, "y": top, "width": right - left, "height": bottom - top})
    monitors.sort(key=lambda m: (m["y"], m["x"]))
    return monitors

def find_window(title, timeout=15):
    start = time.time()
    while time.time() - start < timeout:
        result = []
        def enum_callback(hwnd, _):
            if title in win32gui.GetWindowText(hwnd):
                result.append(hwnd)
        win32gui.EnumWindows(enum_callback, None)
        if result:
            return result[0]
        time.sleep(0.2)
    return None

# ==========================================================
# 主程序生命周期入口
# ==========================================================
def main():
    global global_config
    ensure_default_config()

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
    except Exception as e:
        print(f"[启动失败] 解析 JSON 异常: {e}")
        return

    global_config["mpv_path"] = config_data.get("mpv_path", "")
    if not os.path.exists(global_config["mpv_path"]):
        print(f"[启动失败] mpv.exe 路径配置错误: {global_config['mpv_path']}")
        return

    workerw = get_desktop_workerw()
    monitors = get_monitors()

    if len(monitors) < 2:
        print(f"[硬件受限] 当前系统仅检测到 {len(monitors)} 个显示器，无法完全映射双屏集群。")
        return

    monitors_cfg = config_data.get("monitors", {})
    left_init = monitors_cfg.get("left")
    right_init = monitors_cfg.get("right")

    print("\n[基础架构] 正在部署壁纸核心容器...")

    # 1. 静态初始化左屏 (根据初始 enable 状态决定是否拉起)
    if left_init and left_init.get("enable", False):
        start_wallpaper_instance("left", left_init, workerw, monitors[0])
    runtime_instances["left"]["config"] = left_init.copy() if left_init else {"enable": False}

    time.sleep(0.5)

    # 2. 静态初始化右屏 (根据初始 enable 状态决定是否拉起)
    if right_init and right_init.get("enable", False):
        start_wallpaper_instance("right", right_init, workerw, monitors[1])
    runtime_instances["right"]["config"] = right_init.copy() if right_init else {"enable": False}

    print("[基础架构] 初始化完毕。")

    # 3. 激活异步热配置扫描守护线程
    monitor_thread = threading.Thread(
        target=monitor_config_thread,
        args=(workerw, monitors),
        daemon=True
    )
    monitor_thread.start()

    # 主进程持续挂起
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n[系统退出] 正在回收进程树资源...")
        stop_wallpaper_instance("left")
        stop_wallpaper_instance("right")

if __name__ == "__main__":
    main()