"""京东机器人 Cookie 店铺的 Tkinter 控制台。"""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Any, Mapping

from jd_cookie_runner import JdCookieRunner
from jd_robot_cookie_api import (
    DEFAULT_API_BASE_URL,
    DEFAULT_PLATFORM,
    Customer,
    RobotCookieApi,
    RobotCookieShop,
    parse_cookie_string,
)


@dataclass
class _RunningRobot:
    stop_event: threading.Event
    thread: threading.Thread


@dataclass
class _ShopRowWidgets:
    selected: tk.BooleanVar
    status_label: ttk.Label
    action_button: ttk.Button


class JdRobotControlApp:
    def __init__(
        self,
        root: tk.Tk,
        *,
        api_base_url: str = DEFAULT_API_BASE_URL,
        platform: str = DEFAULT_PLATFORM,
        workflow_name: str = "",
        workflow_id: str = "",
    ) -> None:
        self.root = root
        self.api = RobotCookieApi(base_url=api_base_url)
        self.platform = platform
        self.workflow_name = workflow_name
        self.workflow_id = workflow_id
        self.customers: dict[str, str] = {}
        self.shops: dict[str, RobotCookieShop] = {}
        self.running: dict[str, _RunningRobot] = {}
        self.row_widgets: dict[str, _ShopRowWidgets] = {}
        self._ui_events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.status_var = tk.StringVar(value="正在读取客户…")
        self.customer_var = tk.StringVar()

        title = "京东机器人中控"
        if workflow_name:
            title = "{} - {}".format(title, workflow_name)
        root.title(title)
        root.geometry("1040x650")
        root.minsize(800, 460)
        root.protocol("WM_DELETE_WINDOW", self.close)

        top = ttk.Frame(root, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="客户：").grid(row=0, column=0, sticky="w")
        self.customer_box = ttk.Combobox(
            top,
            textvariable=self.customer_var,
            state="disabled",
            width=36,
        )
        self.customer_box.grid(row=0, column=1, sticky="w")
        self.load_shop_button = ttk.Button(
            top,
            text="加载店铺",
            command=self.load_selected_customer_shops,
            state="disabled",
        )
        self.load_shop_button.grid(row=0, column=2, padx=(8, 0))
        if workflow_name:
            ttk.Label(top, text="当前工作流：{}".format(workflow_name)).grid(
                row=0,
                column=4,
                padx=(16, 0),
                sticky="w",
            )
        ttk.Button(top, text="重新读取客户", command=self.load_customers).grid(
            row=0,
            column=3,
            padx=(8, 0),
        )
        ttk.Button(top, text="启动勾选", command=self.start_selected).grid(
            row=1,
            column=0,
            pady=(10, 0),
            sticky="w",
        )
        ttk.Button(top, text="停止勾选", command=self.stop_selected).grid(
            row=1,
            column=1,
            pady=(10, 0),
            sticky="w",
        )
        ttk.Button(top, text="启动全部可用", command=self.start_all).grid(
            row=1,
            column=2,
            pady=(10, 0),
            sticky="w",
        )
        ttk.Button(top, text="停止全部", command=self.stop_all).grid(
            row=1,
            column=3,
            pady=(10, 0),
            sticky="w",
        )
        ttk.Label(top, textvariable=self.status_var).grid(
            row=2,
            column=0,
            columnspan=4,
            sticky="w",
            pady=(10, 0),
        )

        table = ttk.Frame(root, padding=(12, 0, 12, 12))
        table.pack(fill="both", expand=True)
        header = ttk.Frame(table)
        header.pack(fill="x")
        ttk.Label(header, text="选择", width=8).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(header, text="店铺", width=38).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(header, text="店铺 ID", width=18).grid(row=0, column=2, sticky="w", padx=4)
        ttk.Label(header, text="Cookie", width=18).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Label(header, text="状态", width=20).grid(row=0, column=4, sticky="w", padx=4)
        ttk.Label(header, text="操作", width=12).grid(row=0, column=5, sticky="w", padx=4)

        self.canvas = tk.Canvas(table, highlightthickness=0)
        scrollbar = ttk.Scrollbar(table, orient="vertical", command=self.canvas.yview)
        self.rows_frame = ttk.Frame(self.canvas)
        self.rows_frame.bind(
            "<Configure>",
            lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        ttk.Label(
            root,
            text="先选择客户，再点击“加载店铺”。每家店铺右侧均可单独启动/停止；也可勾选多家批量控制。Cookie 不会显示在界面或日志中。",
            padding=(12, 0, 12, 12),
        ).pack(anchor="w")

        self.root.after(100, self._drain_ui_events)
        self.load_customers()

    def load_customers(self) -> None:
        if self.running:
            messagebox.showinfo("请先停止", "请先停止所有运行中的店铺，再重新读取客户。", parent=self.root)
            return
        self.status_var.set("正在读取客户…")
        self.customer_box.configure(state="disabled")
        self.load_shop_button.configure(state="disabled")
        self.api.clear_cache()

        def worker() -> None:
            try:
                customers = self.api.list_customers_with_robot_shops(platform=self.platform)
            except Exception as error:
                self._ui_events.put(("customers_failed", str(error)))
                return
            self._ui_events.put(("customers_loaded", customers))

        threading.Thread(target=worker, name="load-jd-customers", daemon=True).start()

    def load_selected_customer_shops(self) -> None:
        customer_name = self.customer_var.get().strip()
        customer_id = self.customers.get(customer_name)
        if not customer_id:
            messagebox.showinfo("请选择客户", "请先选择一个客户。", parent=self.root)
            return
        if self.running:
            messagebox.showinfo("请先停止", "请先停止所有运行中的店铺，再加载其他客户。", parent=self.root)
            return
        self.status_var.set("正在读取客户“{}”的机器人 Cookie 店铺…".format(customer_name))
        self.customer_box.configure(state="disabled")
        self.load_shop_button.configure(state="disabled")

        def worker() -> None:
            try:
                shops = self.api.list_shops(
                    platform=self.platform,
                    customer_id=customer_id,
                )
            except Exception as error:
                self._ui_events.put(("shops_failed", str(error)))
                return
            self._ui_events.put(("shops_loaded", (customer_name, shops)))

        threading.Thread(
            target=worker,
            name="load-jd-shops-{}".format(customer_id),
            daemon=True,
        ).start()

    def start_selected(self) -> None:
        self._start_keys(
            [key for key, widgets in self.row_widgets.items() if widgets.selected.get()]
        )

    def stop_selected(self) -> None:
        self._stop_keys(
            [key for key, widgets in self.row_widgets.items() if widgets.selected.get()]
        )

    def start_all(self) -> None:
        self._start_keys([key for key, shop in self.shops.items() if shop.can_start])

    def stop_all(self) -> None:
        self._stop_keys(list(self.running))

    def toggle_robot(self, key: str) -> None:
        if key in self.running:
            self._stop_keys([key])
        else:
            self._start_keys([key])

    def _start_keys(self, keys: list[str]) -> None:
        if not keys:
            messagebox.showinfo("请选择店铺", "请先勾选一个或多个店铺。", parent=self.root)
            return
        started = sum(1 for key in keys if self._start_shop(key))
        self.status_var.set("已启动 {} 家店铺。".format(started))

    def _stop_keys(self, keys: list[str]) -> None:
        if not keys:
            messagebox.showinfo("请选择店铺", "请先勾选一个或多个店铺。", parent=self.root)
            return
        stopped = 0
        for key in keys:
            robot = self.running.get(key)
            widgets = self.row_widgets.get(key)
            if robot is None or widgets is None:
                continue
            robot.stop_event.set()
            widgets.status_label.configure(text="正在停止")
            widgets.action_button.configure(state="disabled")
            stopped += 1
        self.status_var.set("正在停止 {} 家店铺。".format(stopped))

    def _start_shop(self, key: str) -> bool:
        shop = self.shops.get(key)
        widgets = self.row_widgets.get(key)
        if shop is None or widgets is None or key in self.running:
            return False
        if not shop.can_start:
            widgets.status_label.configure(text=self._unavailable_status(shop))
            return False
        try:
            cookies = parse_cookie_string(shop.cookie)
        except ValueError:
            widgets.status_label.configure(text="Cookie 格式错误")
            return False

        stop_event = threading.Event()

        def runner() -> None:
            try:
                result = asyncio.run(
                    JdCookieRunner(
                        cookies,
                        status_callback=lambda status: self._ui_events.put(
                            ("robot_status", (key, stop_event, status))
                        ),
                        shop_id=shop.shop_id,
                        shop_name=shop.shop_name,
                        workflow_id=self.workflow_id,
                        human_account_id=shop.human_account_id,
                        human_account_name=shop.human_account_name,
                    ).run_forever(stop_event=stop_event)
                )
            except Exception as error:
                result = "运行异常：{}".format(error)
            self._ui_events.put(("robot_stopped", (key, stop_event, result)))

        thread = threading.Thread(
            target=runner,
            name="jd-robot-{}".format(shop.shop_id),
            daemon=True,
        )
        self.running[key] = _RunningRobot(stop_event=stop_event, thread=thread)
        widgets.status_label.configure(text="连接中")
        widgets.action_button.configure(text="停止", state="normal")
        thread.start()
        return True

    def _drain_ui_events(self) -> None:
        while True:
            try:
                event_name, value = self._ui_events.get_nowait()
            except queue.Empty:
                break
            if event_name == "customers_loaded":
                self._show_customers(value)
            elif event_name == "customers_failed":
                self._load_failed("读取客户失败", value)
            elif event_name == "shops_loaded":
                customer_name, shops = value
                self._show_shops(customer_name, shops)
            elif event_name == "shops_failed":
                self._load_failed("读取店铺失败", value)
            elif event_name == "robot_stopped":
                key, stop_event, reason = value
                self._robot_stopped(key, stop_event, reason)
            elif event_name == "robot_status":
                key, stop_event, status = value
                self._robot_status_changed(key, stop_event, status)
        self.root.after(100, self._drain_ui_events)

    def _show_customers(self, customers: list[Customer]) -> None:
        choices: dict[str, str] = {}
        for customer in customers:
            display_name = customer.name
            if display_name in choices:
                display_name = "{} ({})".format(customer.name, customer.id)
            choices[display_name] = customer.id
        self.customers = choices
        self.customer_box["values"] = list(choices)
        self.customer_var.set("")
        self.customer_box.configure(state="readonly" if choices else "disabled")
        self.load_shop_button.configure(state="normal" if choices else "disabled")
        self._clear_rows()
        self.status_var.set("已读取 {} 个客户；请选择客户后加载店铺。".format(len(choices)))

    def _show_shops(self, customer_name: str, shops: list[RobotCookieShop]) -> None:
        self.customer_box.configure(state="readonly" if self.customers else "disabled")
        self.load_shop_button.configure(state="normal" if self.customers else "disabled")
        self._clear_rows()
        self.shops = {shop.key: shop for shop in shops}
        for row_index, shop in enumerate(shops):
            self._add_shop_row(row_index, shop)
        self.status_var.set("客户“{}”共有 {} 家机器人 Cookie 店铺。".format(customer_name, len(shops)))

    def _add_shop_row(self, row_index: int, shop: RobotCookieShop) -> None:
        row = ttk.Frame(self.rows_frame, padding=(2, 5))
        row.grid(row=row_index, column=0, sticky="ew")
        selected = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, variable=selected).grid(row=0, column=0, sticky="w", padx=4)
        ttk.Label(row, text=shop.shop_name, width=38).grid(row=0, column=1, sticky="w", padx=4)
        ttk.Label(row, text=shop.shop_id, width=18).grid(row=0, column=2, sticky="w", padx=4)
        cookie_status = "可用" if shop.can_start else self._unavailable_status(shop)
        ttk.Label(row, text=cookie_status, width=18).grid(row=0, column=3, sticky="w", padx=4)
        status_label = ttk.Label(
            row,
            text="未启动" if shop.can_start else cookie_status,
            width=20,
        )
        status_label.grid(row=0, column=4, sticky="w", padx=4)
        button = ttk.Button(
            row,
            text="启动",
            width=10,
            state="normal" if shop.can_start else "disabled",
            command=lambda current_key=shop.key: self.toggle_robot(current_key),
        )
        button.grid(row=0, column=5, sticky="w", padx=4)
        self.row_widgets[shop.key] = _ShopRowWidgets(
            selected=selected,
            status_label=status_label,
            action_button=button,
        )

    def _load_failed(self, title: str, error: str) -> None:
        self.customer_box.configure(state="readonly" if self.customers else "disabled")
        self.load_shop_button.configure(state="normal" if self.customers else "disabled")
        self.status_var.set(title)
        messagebox.showerror(title, error, parent=self.root)

    def _robot_stopped(
        self,
        key: str,
        stop_event: threading.Event,
        reason: str,
    ) -> None:
        robot = self.running.get(key)
        widgets = self.row_widgets.get(key)
        shop = self.shops.get(key)
        if robot is None or robot.stop_event is not stop_event or widgets is None or shop is None:
            return
        self.running.pop(key, None)
        widgets.status_label.configure(text=reason)
        widgets.action_button.configure(
            text="启动",
            state="normal" if shop.can_start else "disabled",
        )
        self.status_var.set("店铺已停止：{}".format(reason))

    def _robot_status_changed(
        self,
        key: str,
        stop_event: threading.Event,
        status: str,
    ) -> None:
        robot = self.running.get(key)
        widgets = self.row_widgets.get(key)
        shop = self.shops.get(key)
        if robot is None or robot.stop_event is not stop_event or widgets is None or shop is None:
            return
        widgets.status_label.configure(text=status)
        self.status_var.set("店铺“{}”：{}".format(shop.shop_name, status))

    def _clear_rows(self) -> None:
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self.row_widgets.clear()
        self.shops.clear()

    @staticmethod
    def _unavailable_status(shop: RobotCookieShop) -> str:
        if not shop.cookie:
            return "没有机器人 Cookie"
        return "Cookie 状态：{}".format(shop.cookie_status)

    def close(self) -> None:
        for robot in self.running.values():
            robot.stop_event.set()
        self.root.destroy()


def run_control_panel(
    *,
    api_base_url: str = DEFAULT_API_BASE_URL,
    platform: str = DEFAULT_PLATFORM,
    workflow_name: str = "",
    workflow_id: str = "",
) -> None:
    root = tk.Tk()
    JdRobotControlApp(
        root,
        api_base_url=api_base_url,
        platform=platform,
        workflow_name=workflow_name,
        workflow_id=workflow_id,
    )
    root.mainloop()
