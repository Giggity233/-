import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import queue
import sqlite3
import sys
from pathlib import Path

import psutil
import win32api
import win32clipboard
import win32gui
import win32con
import win32process

from flask import Flask, request, jsonify


# ==================== 基础路径与去重数据库 ====================
def application_directory() -> Path:
    """开发运行时使用源码目录，打包后使用 exe 所在目录。"""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


SENT_HISTORY_DATABASE = application_directory() / "wechat_send_history.db"


def initialize_send_history() -> None:
    """保存已成功执行的消息编号，供调用端超时重试时去重。"""

    with sqlite3.connect(SENT_HISTORY_DATABASE) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_messages (
                message_id TEXT PRIMARY KEY,
                group_name TEXT NOT NULL,
                message_text TEXT NOT NULL,
                sent_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def has_sent_message(message_id: str) -> bool:
    if not message_id:
        return False
    with sqlite3.connect(SENT_HISTORY_DATABASE) as connection:
        return connection.execute(
            "SELECT 1 FROM sent_messages WHERE message_id = ? LIMIT 1", (message_id,)
        ).fetchone() is not None


def record_sent_message(message_id: str, group_name: str, text: str) -> None:
    if not message_id:
        return
    with sqlite3.connect(SENT_HISTORY_DATABASE) as connection:
        connection.execute(
            """
            INSERT INTO sent_messages (message_id, group_name, message_text)
            VALUES (?, ?, ?)
            ON CONFLICT(message_id) DO NOTHING
            """,
            (message_id, group_name, text),
        )


initialize_send_history()


# ==================== 微信窗口控制（热键唤起方案） ====================
WECHAT_PROCESS_NAMES = ("weixin.exe", "wechat.exe", "微信.exe")
WECHAT_MAIN_WINDOW_CLASSES = ("WeChatMainWndForPC", "WeixinMainWndForPC")

# 微信「设置 → 快捷键」中的"打开微信"默认热键。
# 如果你在微信里改过，请同步修改这里（只支持 ctrl/alt/shift 修饰键）。
WECHAT_WAKE_MODIFIERS = (win32con.VK_CONTROL, win32con.VK_MENU)  # Ctrl + Alt
WECHAT_WAKE_KEY = ord("W")
WECHAT_WAKE_HOTKEY_DESC = "Ctrl+Alt+W"


def wechat_process_running() -> bool:
    """判断微信进程是否存在。"""

    for proc in psutil.process_iter(["name"]):
        try:
            name = (proc.info["name"] or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name in WECHAT_PROCESS_NAMES:
            return True
    return False


def get_wechat_hwnd():
    """根据进程名 Weixin.exe / WeChat.exe 查找微信主窗口句柄。

    注意：这里不再用 IsWindowVisible 做硬过滤，因为微信缩进托盘时
    主窗口是隐藏的，过滤掉会导致永远找不到窗口。
    """

    target_pids = set()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            name = (proc.info["name"] or "").lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        if name in WECHAT_PROCESS_NAMES:
            target_pids.add(proc.info["pid"])

    if not target_pids:
        return None

    candidates = []

    def enum_cb(hwnd, _):
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return
        if pid in target_pids:
            candidates.append(hwnd)

    win32gui.EnumWindows(enum_cb, None)
    if not candidates:
        return None

    # 1) 已知主窗口类名优先
    for hwnd in candidates:
        try:
            if win32gui.GetClassName(hwnd) in WECHAT_MAIN_WINDOW_CLASSES:
                return hwnd
        except Exception:
            continue

    # 2) 有标题且可见
    for hwnd in candidates:
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                return hwnd
        except Exception:
            continue

    # 3) 有标题（含最小化到任务栏 / 托盘隐藏的情况）
    for hwnd in candidates:
        try:
            if win32gui.GetWindowText(hwnd):
                return hwnd
        except Exception:
            continue

    return candidates[0]


def _press_combo(modifier_vks, key_vk) -> None:
    """按下修饰键 + 主键，再逆序释放，模拟一次组合键。"""

    for vk in modifier_vks:
        win32api.keybd_event(vk, 0, 0, 0)
        time.sleep(0.02)
    win32api.keybd_event(key_vk, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(key_vk, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)
    for vk in reversed(modifier_vks):
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        time.sleep(0.02)


def send_wechat_wake_hotkey() -> None:
    """发送微信「打开微信」全局热键，把托盘 / 任务栏里的窗口唤到前台。"""

    _press_combo(WECHAT_WAKE_MODIFIERS, WECHAT_WAKE_KEY)


def wait_for_wechat_window(timeout: float = 3.0):
    """热键发出后轮询等待窗口出现，返回 hwnd 或 None。"""

    deadline = time.time() + timeout
    while time.time() < deadline:
        hwnd = get_wechat_hwnd()
        if hwnd and win32gui.IsWindowVisible(hwnd):
            return hwnd
        time.sleep(0.1)
    return get_wechat_hwnd()


def force_foreground(hwnd) -> bool:
    """把窗口拉到前台。绕过 Windows 前台锁，比单纯 SetForegroundWindow 稳。"""

    try:
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        foreground = win32gui.GetForegroundWindow()
        if foreground == hwnd:
            return True

        current_tid = win32api.GetCurrentThreadId()
        foreground_tid = (
            win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
        )
        target_tid = win32process.GetWindowThreadProcessId(hwnd)[0]

        attached = []
        for tid in (foreground_tid, target_tid):
            if tid and tid != current_tid:
                try:
                    win32process.AttachThreadInput(current_tid, tid, True)
                    attached.append(tid)
                except Exception:
                    pass

        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        finally:
            for tid in attached:
                try:
                    win32process.AttachThreadInput(current_tid, tid, False)
                except Exception:
                    pass
        return True
    except Exception:
        return False


def maximize_wechat() -> bool:
    """用全局热键打开微信，然后最大化并置前。"""

    if not wechat_process_running():
        return False

    hwnd = get_wechat_hwnd()
    need_wake = (
        hwnd is None
        or not win32gui.IsWindowVisible(hwnd)
        or win32gui.IsIconic(hwnd)
    )

    if need_wake:
        send_wechat_wake_hotkey()
        hwnd = wait_for_wechat_window(timeout=3.0)

    if not hwnd:
        return False

    try:
        # 先 RESTORE（托盘 / 最小化状态下直接 MAXIMIZE 可能不生效）
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.2)
        win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        force_foreground(hwnd)
        time.sleep(0.2)
        return win32gui.IsWindowVisible(hwnd)
    except Exception:
        return False


def minimize_wechat() -> bool:
    """最小化微信窗口（微信没有最小化热键，用窗口消息实现）。"""

    hwnd = get_wechat_hwnd()
    if not hwnd:
        return False
    try:
        if win32gui.IsIconic(hwnd):
            return True
        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        return True
    except Exception:
        return False


def click_screen(x: int, y: int) -> None:
    """使用 pywin32 点击指定屏幕坐标，避免依赖额外的 pyautogui 包。"""

    win32api.SetCursorPos((x, y))
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def press_ctrl_key(key: str) -> None:
    """发送 Ctrl+A、Ctrl+V 等组合键。"""

    virtual_key = ord(key.upper())
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    time.sleep(0.02)
    win32api.keybd_event(virtual_key, 0, 0, 0)
    time.sleep(0.05)
    win32api.keybd_event(virtual_key, 0, win32con.KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def copy_to_clipboard(text: str) -> None:
    """复制 Unicode 文本；剪贴板临时被其他程序占用时短暂重试。"""

    last_error = None
    for _ in range(5):
        opened = False
        try:
            win32clipboard.OpenClipboard()
            opened = True
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
            return
        except Exception as error:
            last_error = error
            time.sleep(0.2)
        finally:
            if opened:
                win32clipboard.CloseClipboard()
    raise RuntimeError(f"无法写入剪贴板：{last_error}")


# ==================== 自动化发送流程 ====================
def send_to_group(coords: dict, group_name: str, text: str, log_func):
    """
    coords 包含 search, enter, input, send 四个 (x, y) 元组
    """
    log_func(f"开始执行：发送 {WECHAT_WAKE_HOTKEY_DESC} 热键唤起微信并最大化")
    if not maximize_wechat():
        log_func(
            f"❌ 未能唤起微信窗口：请确认微信已登录，"
            f"且微信「设置 → 快捷键」中的打开微信为 {WECHAT_WAKE_HOTKEY_DESC}"
        )
        return False
    time.sleep(1)

    # 1. 点击搜索栏
    log_func(f"点击搜索栏 {coords['search']}")
    click_screen(*coords["search"])
    time.sleep(1)

    # 清空可能存在的旧内容，再粘贴群名
    press_ctrl_key("a")
    time.sleep(0.1)
    copy_to_clipboard(group_name)
    press_ctrl_key("v")
    time.sleep(1)

    # 2. 点击进群
    log_func(f"点击进群 {coords['enter']}")
    click_screen(*coords["enter"])
    time.sleep(1)

    # 3. 点击输入框
    log_func(f"点击输入框 {coords['input']}")
    click_screen(*coords["input"])
    time.sleep(1)

    # 4. 粘贴文本
    copy_to_clipboard(text)
    press_ctrl_key("v")
    time.sleep(1)

    # 5. 点击发送
    log_func(f"点击发送 {coords['send']}")
    click_screen(*coords["send"])
    time.sleep(1)

    # 6. 最小化
    log_func("最小化微信")
    minimize_wechat()
    log_func("✅ 发送流程结束")
    return True


# ==================== Flask 服务 ====================
app = Flask(__name__)
_app_instance = {"coords": None, "log_func": None, "lock": threading.Lock()}


@app.route("/send", methods=["GET", "POST"])
def api_send():
    group = request.values.get("group", "").strip()
    text = request.values.get("text", "").strip()
    message_id = request.values.get("message_id", "").strip()

    if not group or not text:
        return jsonify({"ok": False, "msg": "group 和 text 不能为空"}), 400

    coords = _app_instance["coords"]
    log_func = _app_instance["log_func"]
    lock = _app_instance["lock"]

    if not coords:
        return jsonify({"ok": False, "msg": "坐标未配置"}), 500

    with lock:  # 防止并发请求同时操作鼠标键盘
        try:
            if message_id and has_sent_message(message_id):
                log_func(f"♻️ 消息 {message_id} 已发送过，跳过重复操作")
                return jsonify({"ok": True, "duplicate": True, "msg": "该消息已发送过"})
            success = send_to_group(coords, group, text, log_func)
            if success:
                record_sent_message(message_id, group, text)
            return jsonify(
                {"ok": success, "msg": "已执行" if success else "微信窗口未找到"}
            )
        except Exception as e:
            log_func(f"❌ 执行异常: {e}")
            return jsonify({"ok": False, "msg": str(e)}), 500


def run_flask(log_func):
    _app_instance["log_func"] = log_func
    log_func(
        "Flask 服务已启动，端口 1818，接口: /send?group=xxx&text=yyy"
    )
    app.run(host="0.0.0.0", port=1818, debug=False, use_reloader=False)


# ==================== Tkinter 界面 ====================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("微信发群助手 · 坐标配置")
        self.root.geometry("520x680")
        self.root.resizable(False, False)

        self.coord_entries = {}
        self.show_coord = False
        self.flask_started = False
        self.log_queue = queue.Queue()

        self._build_ui()
        self._poll_log()
        self._poll_mouse()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- 坐标配置区 ---
        frm = ttk.LabelFrame(self.root, text="坐标配置（屏幕绝对坐标）")
        frm.pack(fill="x", **pad)

        items = [
            ("search", "搜索栏"),
            ("enter", "进群结果"),
            ("input", "输入框"),
            ("send", "发送按钮"),
        ]
        for i, (key, label) in enumerate(items):
            ttk.Label(frm, text=label + ":").grid(
                row=i, column=0, sticky="e", padx=5, pady=4
            )
            x_var, y_var = tk.StringVar(), tk.StringVar()
            ttk.Entry(frm, textvariable=x_var, width=7).grid(
                row=i, column=1, padx=2
            )
            ttk.Label(frm, text=",").grid(row=i, column=2)
            ttk.Entry(frm, textvariable=y_var, width=7).grid(
                row=i, column=3, padx=2
            )
            ttk.Button(
                frm,
                text="捕获",
                width=6,
                command=lambda k=key, xv=x_var, yv=y_var: self._capture(k, xv, yv),
            ).grid(row=i, column=4, padx=6)
            self.coord_entries[key] = (x_var, y_var)

        # --- 鼠标坐标追踪 ---
        coord_frm = ttk.Frame(self.root)
        coord_frm.pack(fill="x", **pad)
        self.coord_label = ttk.Label(
            coord_frm, text="鼠标坐标: --, --", font=("Consolas", 11)
        )
        self.coord_label.pack(side="left")
        self.btn_track = ttk.Button(
            coord_frm, text="显示鼠标XY", command=self._toggle_track
        )
        self.btn_track.pack(side="right")

        # --- 唤起方式提示 ---
        ttk.Label(
            self.root,
            text=f"唤起方式：全局热键 {WECHAT_WAKE_HOTKEY_DESC}（需与微信快捷键设置一致）",
            foreground="#1f6feb",
        ).pack(anchor="w", padx=10)

        # --- 控制按钮 ---
        ctrl_frm = ttk.Frame(self.root)
        ctrl_frm.pack(fill="x", **pad)
        self.btn_start = ttk.Button(
            ctrl_frm, text="开启服务", command=self._start_flask
        )
        self.btn_start.pack(side="left", expand=True, fill="x", padx=2)
        ttk.Button(ctrl_frm, text="清空日志", command=self._clear_log).pack(
            side="left", expand=True, fill="x", padx=2
        )

        # --- 状态 ---
        self.status_var = tk.StringVar(value="服务未启动")
        ttk.Label(
            self.root, textvariable=self.status_var, foreground="gray"
        ).pack(anchor="w", **pad)

        # --- 日志 ---
        log_frm = ttk.LabelFrame(self.root, text="运行日志")
        log_frm.pack(fill="both", expand=True, **pad)
        self.log_text = scrolledtext.ScrolledText(
            log_frm, height=18, state="disabled", font=("Consolas", 9)
        )
        self.log_text.pack(fill="both", expand=True, padx=4, pady=4)

    # -------- 鼠标坐标追踪 --------
    def _toggle_track(self):
        self.show_coord = not self.show_coord
        self.btn_track.config(
            text="隐藏鼠标XY" if self.show_coord else "显示鼠标XY"
        )
        if not self.show_coord:
            self.coord_label.config(text="鼠标坐标: --, --")

    def _poll_mouse(self):
        if self.show_coord:
            x, y = self.root.winfo_pointerxy()
            self.coord_label.config(text=f"鼠标坐标: {x}, {y}")
        self.root.after(50, self._poll_mouse)

    def _capture(self, key, x_var, y_var):
        x, y = self.root.winfo_pointerxy()
        x_var.set(str(x))
        y_var.set(str(y))
        self.log(f"已捕获 {key} 坐标: ({x}, {y})")

    # -------- 启动 Flask --------
    def _start_flask(self):
        if self.flask_started:
            messagebox.showinfo("提示", "服务已在运行中")
            return

        coords = {}
        for key in ("search", "enter", "input", "send"):
            xv, yv = self.coord_entries[key]
            try:
                coords[key] = (int(xv.get()), int(yv.get()))
            except ValueError:
                messagebox.showerror("坐标错误", f"请填写完整的 {key} 坐标")
                return

        _app_instance["coords"] = coords
        self.flask_started = True
        self.btn_start.config(state="disabled", text="服务运行中")
        self.status_var.set("服务运行中 · 端口 1818 · 接口 /send")

        threading.Thread(target=run_flask, args=(self.log,), daemon=True).start()

    # -------- 日志 --------
    def log(self, msg):
        self.log_queue.put(msg)

    def _poll_log(self):
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_text.config(state="normal")
                self.log_text.insert(
                    "end", f"[{time.strftime('%H:%M:%S')}] {msg}\n"
                )
                self.log_text.see("end")
                self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()