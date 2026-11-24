"""自动回复中控入口：先在黑框选择工作流，再打开 tkinter 店铺控制台。"""

from __future__ import annotations

import json
import queue
import threading
import tkinter as tk
from collections.abc import Mapping
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any

import requests

from buyer_message_relay import conversation_reply, run_reply_relay


API_BASE_URL = "http://117.72.204.36:8000/api/v1"
COOKIE_API_URL = f"{API_BASE_URL}/cookies/"
ROBOT_COOKIE_API_URL = f"{API_BASE_URL}/robot-cookies/"
CUSTOMERS_API_URL = f"{API_BASE_URL}/customers/"
WORKFLOW_FILE = Path(__file__).resolve().parent / "data" / "workflowid.json"


def choose_workflow(path: Path = WORKFLOW_FILE) -> tuple[str, str]:
    """在启动界面前列出 workflowid.json 键名，等待用户按序号选择。"""
    try:
        workflows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"无法读取工作流配置 {path}：{error}") from error
    if not isinstance(workflows, dict) or not workflows:
        raise RuntimeError("workflowid.json 必须是非空对象，格式为“名称: 工作流编号”")

    options = [(str(name), str(workflow_id).strip()) for name, workflow_id in workflows.items()]
    if any(not workflow_id for _, workflow_id in options):
        raise RuntimeError("workflowid.json 中存在空工作流编号")

    print("\n可选 Coze 工作流：")
    for index, (name, _) in enumerate(options, start=1):
        print(f"  {index}. {name}")
    while True:
        choice = input("请输入工作流序号：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print(f"请输入 1 到 {len(options)} 之间的数字。")


def fetch_douyin_shops(
    *, collaborative_reply: bool = False, customer_id: str | int | None = None
) -> list[dict[str, Any]]:
    """读取抖音店铺；协同回复时读取独立保存的机器人 Cookie。"""
    if collaborative_reply and customer_id is None:
        raise ValueError("协同回复必须先选择客户")
    api_url = ROBOT_COOKIE_API_URL if collaborative_reply else COOKIE_API_URL
    params: dict[str, str | int] = {"platform": "douyin"}
    if collaborative_reply:
        params["customer_id"] = customer_id
    response = requests.get(api_url, params=params, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        message = payload.get("message", "接口未返回成功状态") if isinstance(payload, dict) else "接口返回格式异常"
        raise RuntimeError(str(message))
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("接口 data 不是店铺列表")
    return [item for item in data if isinstance(item, dict)]


def fetch_enabled_customers() -> list[dict[str, Any]]:
    """读取可供协同回复选择的启用客户。"""
    response = requests.get(CUSTOMERS_API_URL, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not payload.get("ok"):
        message = payload.get("message", "接口未返回成功状态") if isinstance(payload, dict) else "接口返回格式异常"
        raise RuntimeError(str(message))
    data = payload.get("data")
    if not isinstance(data, list):
        raise RuntimeError("客户接口 data 不是列表")
    return [item for item in data if isinstance(item, dict)]


def _account_names(shop: Mapping[str, Any]) -> set[str]:
    accounts = shop.get("human_accounts")
    if not isinstance(accounts, list):
        return set()
    return {
        str(account.get("account_name", "")).strip()
        for account in accounts
        if isinstance(account, Mapping) and str(account.get("account_name", "")).strip()
    }


def _first_human_cid(shop: Mapping[str, Any]) -> str | None:
    accounts = shop.get("human_accounts")
    if not isinstance(accounts, list) or not accounts or not isinstance(accounts[0], Mapping):
        return None
    cid = str(accounts[0].get("account_id", "")).strip()
    if not cid or "没抓" in cid:
        return None
    return cid


@dataclass
class _RunningRobot:
    stop_event: threading.Event
    thread: threading.Thread


class RobotControlApp:
    def __init__(self, root: tk.Tk, workflow_name: str, workflow_id: str) -> None:
        self.root = root
        self.workflow_name = workflow_name
        self.workflow_id = workflow_id
        self.shops: list[dict[str, Any]] = []
        self.running: dict[str, _RunningRobot] = {}
        self.row_widgets: dict[str, tuple[ttk.Label, ttk.Button]] = {}
        self._ui_events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.collaborative_reply_var = tk.BooleanVar(value=False)
        self._displayed_collaborative_reply = False
        self._customer_ids: dict[str, str] = {}

        root.title(f"抖店自动回复中控 — 工作流：{workflow_name}")
        root.geometry("980x650")
        root.minsize(760, 420)
        root.protocol("WM_DELETE_WINDOW", self.close)

        top = ttk.Frame(root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text=f"当前工作流：{workflow_name}").grid(row=0, column=0, sticky="w")
        self.collaborative_reply_box = ttk.Checkbutton(
            top,
            text="协同回复",
            variable=self.collaborative_reply_var,
            command=self._on_collaborative_reply_changed,
        )
        self.collaborative_reply_box.grid(row=0, column=1, sticky="w", padx=(20, 0))
        self.account_label = ttk.Label(top, text="人工账号：")
        self.account_label.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.account_var = tk.StringVar()
        self.account_box = ttk.Combobox(top, textvariable=self.account_var, state="disabled", width=36)
        self.account_box.grid(row=1, column=1, sticky="w", pady=(10, 0))
        self.show_button = ttk.Button(top, text="列出店铺", command=self.show_selected_shops, state="disabled")
        self.show_button.grid(row=1, column=2, padx=(8, 0), pady=(10, 0))
        self.reload_button = ttk.Button(top, text="重新读取店铺", command=self.load_shops)
        self.reload_button.grid(row=1, column=3, padx=(8, 0), pady=(10, 0))
        self.status_var = tk.StringVar(value="正在读取抖音店铺信息…")
        ttk.Label(top, textvariable=self.status_var).grid(row=2, column=0, columnspan=4, sticky="w", pady=(10, 0))

        table = ttk.Frame(root, padding=(12, 0, 12, 12))
        table.pack(fill="both", expand=True)
        header = ttk.Frame(table)
        header.pack(fill="x")
        ttk.Label(header, text="店铺", width=42).pack(side="left", padx=4)
        ttk.Label(header, text="店铺 ID", width=18).pack(side="left", padx=4)
        ttk.Label(header, text="状态", width=20).pack(side="left", padx=4)
        ttk.Label(header, text="操作", width=14).pack(side="right", padx=4)

        self.canvas = tk.Canvas(table, highlightthickness=0)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_frame.bind(
            "<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.root.after(100, self._drain_ui_events)
        self.load_shops()

    def _drain_ui_events(self) -> None:
        while True:
            try:
                event_name, value = self._ui_events.get_nowait()
            except queue.Empty:
                break
            if event_name == "load_failed":
                error, collaborative_reply = value
                self._load_failed(str(error), collaborative_reply)
            elif event_name == "load_succeeded":
                shops, collaborative_reply = value
                self._load_succeeded(shops, collaborative_reply)
            elif event_name == "customers_loaded":
                customers, collaborative_reply = value
                self._customers_loaded(customers, collaborative_reply)
            elif event_name == "customers_load_failed":
                error, collaborative_reply = value
                self._customers_load_failed(str(error), collaborative_reply)
            elif event_name == "collaborative_shops_loaded":
                shops, customer_name = value
                self._collaborative_shops_loaded(shops, customer_name)
            elif event_name == "collaborative_shops_load_failed":
                error, customer_name = value
                self._collaborative_shops_load_failed(str(error), customer_name)
            elif event_name == "robot_stopped":
                shop_id, stop_event = value
                self._robot_stopped(shop_id, stop_event)
        self.root.after(100, self._drain_ui_events)

    def load_shops(self) -> None:
        if self.running:
            messagebox.showinfo("请先关闭机器人", "请先关闭已启动的店铺机器人，再重新读取店铺。", parent=self.root)
            return
        collaborative_reply = self.collaborative_reply_var.get()
        if collaborative_reply:
            self._load_collaborative_customers()
            return

        source_name = "机器人 Cookie" if collaborative_reply else "人工 Cookie"
        self.status_var.set(f"正在读取抖音店铺{source_name}…")
        self.account_box.configure(state="disabled")
        self.show_button.configure(state="disabled")

        def worker() -> None:
            try:
                shops = fetch_douyin_shops(collaborative_reply=collaborative_reply)
            except Exception as error:
                self._ui_events.put(("load_failed", (str(error), collaborative_reply)))
                return
            self._ui_events.put(("load_succeeded", (shops, collaborative_reply)))

        threading.Thread(target=worker, name="load-douyin-shops", daemon=True).start()

    def _load_collaborative_customers(self) -> None:
        """协同回复先从最新接口读取客户，选择后才读取该客户的机器人 Cookie。"""
        self.status_var.set("正在读取可用客户…")
        self.account_box.configure(state="disabled")
        self.show_button.configure(state="disabled")

        def worker() -> None:
            try:
                customers = fetch_enabled_customers()
            except Exception as error:
                self._ui_events.put(("customers_load_failed", (str(error), True)))
                return
            self._ui_events.put(("customers_loaded", (customers, True)))

        threading.Thread(target=worker, name="load-enabled-customers", daemon=True).start()

    def _load_failed(self, error: str, collaborative_reply: bool) -> None:
        if collaborative_reply != self.collaborative_reply_var.get():
            return
        self.status_var.set("读取店铺失败")
        messagebox.showerror("读取店铺失败", error, parent=self.root)

    def _load_succeeded(self, shops: list[dict[str, Any]], collaborative_reply: bool) -> None:
        if collaborative_reply != self.collaborative_reply_var.get():
            return
        self.shops = shops
        self._displayed_collaborative_reply = collaborative_reply
        self._customer_ids.clear()
        accounts = sorted({name for shop in shops for name in _account_names(shop)})
        self.account_box["values"] = accounts
        self.account_var.set("")
        self.account_label.configure(text="人工账号：")
        self.account_box.configure(state="readonly" if accounts else "disabled")
        self.show_button.configure(state="normal" if accounts else "disabled")
        self.status_var.set(f"已读取 {len(shops)} 家抖音店铺；请选择人工账号后列出对应店铺。")
        self._clear_rows()

    def _customers_loaded(self, customers: list[dict[str, Any]], collaborative_reply: bool) -> None:
        if not collaborative_reply or not self.collaborative_reply_var.get():
            return
        customer_ids: dict[str, str] = {}
        for customer in customers:
            customer_name = str(customer.get("name", "")).strip()
            customer_id = str(customer.get("id", "")).strip()
            if not customer_name or not customer_id:
                continue
            display_name = customer_name
            if display_name in customer_ids:
                display_name = f"{customer_name}（{customer_id}）"
            customer_ids[display_name] = customer_id

        self.shops = []
        self._customer_ids = customer_ids
        self._displayed_collaborative_reply = True
        self.account_label.configure(text="客户：")
        self.account_box["values"] = list(customer_ids)
        self.account_var.set("")
        self.account_box.configure(state="readonly" if customer_ids else "disabled")
        self.show_button.configure(state="normal" if customer_ids else "disabled")
        self.status_var.set(f"已读取 {len(customer_ids)} 个启用客户；请选择客户后列出机器人 Cookie 店铺。")
        self._clear_rows()

    def _customers_load_failed(self, error: str, collaborative_reply: bool) -> None:
        if not collaborative_reply or not self.collaborative_reply_var.get():
            return
        self.status_var.set("读取客户失败")
        messagebox.showerror("读取客户失败", error, parent=self.root)

    def _load_collaborative_shops(self, customer_name: str, customer_id: str) -> None:
        self.status_var.set(f"正在读取客户“{customer_name}”的机器人 Cookie 店铺…")
        self.account_box.configure(state="disabled")
        self.show_button.configure(state="disabled")

        def worker() -> None:
            try:
                shops = fetch_douyin_shops(collaborative_reply=True, customer_id=customer_id)
            except Exception as error:
                self._ui_events.put(("collaborative_shops_load_failed", (str(error), customer_name)))
                return
            self._ui_events.put(("collaborative_shops_loaded", (shops, customer_name)))

        threading.Thread(target=worker, name=f"load-robot-shops-{customer_id}", daemon=True).start()

    def _collaborative_shops_loaded(self, shops: list[dict[str, Any]], customer_name: str) -> None:
        if not self.collaborative_reply_var.get():
            return
        self.shops = shops
        self._displayed_collaborative_reply = True
        self.account_box.configure(state="readonly" if self._customer_ids else "disabled")
        self.show_button.configure(state="normal" if self._customer_ids else "disabled")
        self.status_var.set(f"客户“{customer_name}”有 {len(shops)} 家可使用机器人 Cookie 的店铺。")
        self._clear_rows()
        for row_index, shop in enumerate(shops):
            self._add_shop_row(row_index, shop)

    def _collaborative_shops_load_failed(self, error: str, customer_name: str) -> None:
        if not self.collaborative_reply_var.get():
            return
        self.account_box.configure(state="readonly" if self._customer_ids else "disabled")
        self.show_button.configure(state="normal" if self._customer_ids else "disabled")
        self.status_var.set("读取机器人 Cookie 店铺失败")
        messagebox.showerror("读取机器人 Cookie 店铺失败", f"客户“{customer_name}”：{error}", parent=self.root)

    def _on_collaborative_reply_changed(self) -> None:
        """切换 Cookie 来源；协同回复不需要人工账号或转接人。"""
        if self.running:
            self.collaborative_reply_var.set(self._displayed_collaborative_reply)
            messagebox.showinfo("请先关闭机器人", "请先关闭已启动的店铺机器人，再切换协同回复。", parent=self.root)
            return
        self._clear_rows()
        if self.collaborative_reply_var.get():
            self.account_label.configure(text="客户：")
            self.account_var.set("")
            self.account_box.configure(state="disabled")
            self.reload_button.configure(text="重新读取客户")
        else:
            self.account_label.configure(text="人工账号：")
            self.reload_button.configure(text="重新读取店铺")
        self.load_shops()

    def _clear_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.row_widgets.clear()

    def show_selected_shops(self) -> None:
        if self._displayed_collaborative_reply:
            customer_name = self.account_var.get().strip()
            customer_id = self._customer_ids.get(customer_name)
            if not customer_id:
                messagebox.showinfo("请选择客户", "协同回复请先选择一个客户。", parent=self.root)
                return
            self._load_collaborative_shops(customer_name, customer_id)
            return

        account_name = self.account_var.get().strip()
        if not account_name:
            messagebox.showinfo("请选择账号", "请先选择一个人工 account_name。", parent=self.root)
            return
        self._clear_rows()
        matched = [shop for shop in self.shops if account_name in _account_names(shop)]
        self.status_var.set(f"账号“{account_name}”对应 {len(matched)} 家店铺。")
        for row_index, shop in enumerate(matched):
            self._add_shop_row(row_index, shop)

    @staticmethod
    def _shop_key(shop: Mapping[str, Any]) -> str:
        return str(shop.get("shop_id", "")).strip()

    def _add_shop_row(self, row_index: int, shop: dict[str, Any]) -> None:
        shop_id = self._shop_key(shop)
        shop_name = str(shop.get("shop_name", "未命名店铺")).strip() or "未命名店铺"
        row = ttk.Frame(self.rows_frame, padding=(2, 5))
        row.grid(row=row_index, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        ttk.Label(row, text=shop_name).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(row, text=shop_id or "—").grid(row=0, column=1, sticky="w", padx=4)

        cookie = shop.get("cookie")
        cookie_status = str(shop.get("cookie_status", "")).strip()
        if not self._displayed_collaborative_reply and not _first_human_cid(shop):
            status = "首个人工账号没有有效 ID"
            state = "disabled"
        elif not isinstance(cookie, str) or not cookie.strip():
            status = "没有可用 Cookie"
            state = "disabled"
        elif cookie_status and cookie_status != "valid":
            status = f"Cookie 状态：{cookie_status}"
            state = "disabled"
        else:
            status = "未启动"
            state = "normal"
        status_label = ttk.Label(row, text=status, width=20)
        status_label.grid(row=0, column=2, sticky="w", padx=4)
        button = ttk.Button(row, text="启动", width=12, state=state)
        button.configure(command=lambda current_shop=shop: self.toggle_robot(current_shop))
        button.grid(row=0, column=3, sticky="e", padx=4)
        self.row_widgets[shop_id] = (status_label, button)

    def toggle_robot(self, shop: dict[str, Any]) -> None:
        shop_id = self._shop_key(shop)
        if not shop_id:
            messagebox.showerror("无法启动", "店铺缺少 shop_id。", parent=self.root)
            return
        if shop_id in self.running:
            self.stop_robot(shop_id)
        else:
            self.start_robot(shop)

    def start_robot(self, shop: dict[str, Any]) -> None:
        shop_id = self._shop_key(shop)
        shop_name = str(shop.get("shop_name", "未命名店铺")).strip() or "未命名店铺"
        cookie = shop.get("cookie")
        collaborative_reply = self._displayed_collaborative_reply
        human_cid = None if collaborative_reply else _first_human_cid(shop)
        if not isinstance(cookie, str) or not cookie.strip() or (not collaborative_reply and not human_cid):
            requirement = "完整机器人 Cookie" if collaborative_reply else "完整 Cookie 或首个人工账号 ID"
            messagebox.showerror("无法启动", f"该店铺缺少{requirement}。", parent=self.root)
            return

        stop_event = threading.Event()
        reply_function = partial(
            conversation_reply,
            workflow_id=self.workflow_id,
            human_cid=human_cid,
            shop_name=shop_name,
            collaborative_reply=collaborative_reply,
        )

        def runner() -> None:
            try:
                run_reply_relay(
                    cookie,
                    reply_function,
                    shop_name=shop_name,
                    wait_seconds=8,
                    stop_event=stop_event,
                )
            finally:
                self._ui_events.put(("robot_stopped", (shop_id, stop_event)))

        thread = threading.Thread(target=runner, name=f"shop-listener-{shop_id}", daemon=True)
        self.running[shop_id] = _RunningRobot(stop_event=stop_event, thread=thread)
        status_label, button = self.row_widgets[shop_id]
        status_label.configure(text="运行中")
        button.configure(text="关闭", state="normal")
        thread.start()

    def stop_robot(self, shop_id: str) -> None:
        robot = self.running.get(shop_id)
        if robot is None:
            return
        robot.stop_event.set()
        status_label, button = self.row_widgets[shop_id]
        status_label.configure(text="正在关闭…")
        button.configure(state="disabled")

    def _robot_stopped(self, shop_id: str, stop_event: threading.Event) -> None:
        robot = self.running.get(shop_id)
        if robot is None or robot.stop_event is not stop_event:
            return
        self.running.pop(shop_id, None)
        widgets = self.row_widgets.get(shop_id)
        if widgets is not None:
            status_label, button = widgets
            status_label.configure(text="未启动")
            button.configure(text="启动", state="normal")

    def close(self) -> None:
        for robot in self.running.values():
            robot.stop_event.set()
        self.root.destroy()


def main() -> None:
    workflow_name, workflow_id = choose_workflow()
    root = tk.Tk()
    RobotControlApp(root, workflow_name, workflow_id)
    root.mainloop()


if __name__ == "__main__":
    main()
