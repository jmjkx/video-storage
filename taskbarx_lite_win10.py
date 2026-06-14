# -*- coding: utf-8 -*-
"""
Win10 Taskbar Center (Windows 11 Style - Universal Parent-Relative Centering Pro)

功能：
融合 [开始菜单] + [全类型搜索组件] + [任务视图按钮] + [应用图标群] 为统一流式布局。
通过动态父窗口句柄 (Parent HWND) 追溯算法，修正跨层级坐标转换失效问题，实现完美绝对居中。

退出：Ctrl+C
"""

import sys
import time
import win32gui

try:
    import uiautomation as auto
except ImportError:
    print("错误 (Error)：缺少必要依赖库 'uiautomation'。")
    print("请先执行以下命令安装：pip install uiautomation")
    sys.exit(1)

SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010

def find_handles():
    """
    深度遍历任务栏树状拓扑结构，全量捕获核心控制组件
    """
    shell = win32gui.FindWindow("Shell_TrayWnd", None)
    if not shell:
        return None

    res = {
        "shell": shell,
        "start": None,
        "search": None,
        "taskview": None,
        "tasksw": None,
        "tasklist": None
    }

    def enum_proc(hwnd, lParam):
        class_name = win32gui.GetClassName(hwnd)
        text = win32gui.GetWindowText(hwnd)

        # 1. 捕获开始菜单按钮
        if class_name in ["Button", "Start"] and not res["start"]:
            if class_name == "Start" or text in ["开始", "", "Start"]:
                res["start"] = hwnd

        # 2. 捕获搜索组件 (涵盖输入框模式与图标模式)
        if class_name in ["TrayDummySearchControl", "SearchBoxTrayClass"]:
            res["search"] = hwnd
        elif class_name == "TrayButton":
            if "搜索" in text or "Search" in text:
                res["search"] = hwnd
            # 3. 捕获任务视图按钮
            elif "任务视图" in text or "Task View" in text:
                res["taskview"] = hwnd

        # 4. 捕获应用图标主控及内嵌控制台
        if class_name == "MSTaskSwWClass":
            res["tasksw"] = hwnd
        if class_name == "MSTaskListWClass":
            res["tasklist"] = hwnd

        return True

    win32gui.EnumChildWindows(shell, enum_proc, None)
    return res

def get_actual_tasklist_width(tasklist_hwnd):
    """
    通过 UI 自动化接口 (UI Automation API, 缩写 API, pronounced 'A-P-I')
    解析无原生句柄的内部 DirectUI 元素流，精确计算当前运行图标的物理像素跨度
    """
    try:
        tasklist_control = auto.ControlFromHandle(tasklist_hwnd)
        children = tasklist_control.GetChildren()

        valid_rects = [
            child.BoundingRectangle
            for child in children
            if child.BoundingRectangle.right > child.BoundingRectangle.left
        ]

        if valid_rects:
            min_left = min(r.left for r in valid_rects)
            max_right = max(r.right for r in valid_rects)
            return max_right - min_left
    except Exception:
        pass
    return 0

def center_all_elements():
    h = find_handles()
    if not h or not h["tasklist"]:
        return

    shell_rect = win32gui.GetWindowRect(h["shell"])
    shell_width = shell_rect[2] - shell_rect[0]

    # 动态构建待居中的空间序列
    components = []
    total_cluster_width = 0
    padding = 4

    # 检查并追加 [开始菜单]
    if h["start"]:
        r = win32gui.GetWindowRect(h["start"])
        w = r[2] - r[0]
        if w > 0:
            components.append({"hwnd": h["start"], "width": w, "rect": r})
            total_cluster_width += w

    # 检查并追加 [搜索窗口/图标]
    if h["search"]:
        r = win32gui.GetWindowRect(h["search"])
        w = r[2] - r[0]
        if w > 0:
            if total_cluster_width > 0: total_cluster_width += padding
            components.append({"hwnd": h["search"], "width": w, "rect": r})
            total_cluster_width += w

    # 检查并追加 [任务视图]
    if h["taskview"]:
        r = win32gui.GetWindowRect(h["taskview"])
        w = r[2] - r[0]
        if w > 0:
            if total_cluster_width > 0: total_cluster_width += padding
            components.append({"hwnd": h["taskview"], "width": w, "rect": r})
            total_cluster_width += w

    # 检查并追加 [应用图标列表] (采用 UIA 真实内容边界)
    actual_list_width = get_actual_tasklist_width(h["tasklist"])
    if actual_list_width > 0:
        if total_cluster_width > 0: total_cluster_width += padding
        r = win32gui.GetWindowRect(h["tasklist"])
        components.append({"hwnd": h["tasklist"], "width": actual_list_width, "rect": r})
        total_cluster_width += actual_list_width

    if total_cluster_width <= 0:
        return

    # 基于经典几何公式计算大控制链在屏幕上的绝对起始物理点 (Target Screen X)
    cluster_screen_x = shell_rect[0] + (shell_width - total_cluster_width) // 2
    current_screen_x = cluster_screen_x

    # 核心迭代：全组件无差别亲代坐标变换布局引擎
    for comp in components:
        hwnd = comp["hwnd"]

        # 动态追溯当前组件的直接亲代窗口句柄
        parent_hwnd = win32gui.GetParent(hwnd)
        if not parent_hwnd:
            parent_hwnd = h["shell"]

        # 将屏幕绝对坐标动态裁剪转换为对应亲代窗口的专属客户区坐标
        target_x = win32gui.ScreenToClient(parent_hwnd, (current_screen_x, 0))[0]

        # 提取当前亲代窗口的屏幕基准点，换算相对 Y 轴偏移量
        parent_rect = win32gui.GetWindowRect(parent_hwnd)
        current_x = comp["rect"][0] - parent_rect[0]
        target_y = comp["rect"][1] - parent_rect[1]

        # 触发底层 Win32 核心架构位移，杜绝任何图层重叠与不跟手现象
        if abs(current_x - target_x) >= 1:
            win32gui.SetWindowPos(
                hwnd, 0, target_x, target_y,
                0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
            )

        # 物理坐标指针流式递增
        current_screen_x += comp["width"] + padding

if __name__ == "__main__":
    # 限制高频轮询环境下的 UIA (pronounced 'U-I-A') 检索断点，最大化缩减 CPU 运算开销
    auto.uiautomation.DEBUG_SEARCH_TIME = 0.01
    auto.SetGlobalSearchTimeout(0.04)

    print("TaskbarX Pro v3.0 (Windows 11 全组件自适应父域绝对居中版) 启动")
    print("当前架构：已切断硬编码依赖，全面托管 [开始] + [搜索] + [任务视图] + [图标流]")
    print("Ctrl+C 退出")
    print("-" * 65)

    try:
        while True:
            center_all_elements()
            time.sleep(0.04)  # 40毫秒黄金高频刷新率，确保流畅度达到硬件级水准
    except KeyboardInterrupt:
        print("\n已退出，控制权交还给 Windows 系统系统外壳。")