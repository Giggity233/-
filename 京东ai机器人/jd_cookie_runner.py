"""使用一份京东 Cookie 运行一个消息机器人连接。"""

from __future__ import annotations

import asyncio
import json
import secrets
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import requests
import websockets

from jd_logging import get_shop_logger
from jd_message_listener import decode_packets
from jd_robot import JdCustomerRobot


CHECKIN_URL = "https://dongdong.jd.com/workbench/checkin.json"
WEBSOCKET_URL = "wss://dongdong.jd.com/workbench/websocket"
CHECKIN_PARAMS = {"version": "2.6.3", "client": "openweb"}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)
StatusCallback = Callable[[str], None]


class CookieAuthenticationError(RuntimeError):
    """签到或 WebSocket 鉴权拒绝当前 Cookie。"""


def _packet_id() -> str:
    return secrets.token_hex(16)


def _encode_packet(packet: Mapping[str, Any]) -> str:
    return json.dumps(packet, ensure_ascii=False, separators=(",", ":"))


class _SerializedWebSocket:
    """让心跳、ACK 和回复共用顺序发送通道。"""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self._send_lock = asyncio.Lock()

    async def send(self, packet: str) -> None:
        async with self._send_lock:
            await self.connection.send(packet)

    async def recv(self) -> Any:
        return await self.connection.recv()


class JdCookieRunner:
    def __init__(
        self,
        cookies: Mapping[str, object],
        *,
        reconnect_seconds: float = 5.0,
        connect_timeout_seconds: float = 30.0,
        wait_seconds: float = 8.0,
        status_callback: StatusCallback | None = None,
        shop_id: str = "",
        shop_name: str = "",
        workflow_id: str = "",
        human_account_id: str = "",
        human_account_name: str = "",
    ) -> None:
        self.cookies = self._normalize_cookies(cookies)
        self.reconnect_seconds = reconnect_seconds
        self.connect_timeout_seconds = connect_timeout_seconds
        self.wait_seconds = wait_seconds
        self.workflow_id = workflow_id
        self.human_account_id = human_account_id
        self.human_account_name = human_account_name
        self.log = get_shop_logger(shop_id, shop_name)
        self.status_callback = status_callback or self._log_status

    async def run_forever(self, stop_event: threading.Event | None = None) -> str:
        while not self._stopped(stop_event):
            try:
                self._emit_status("正在签到")
                stopped = await self._run_connection(stop_event)
                if stopped:
                    return "已停止"
            except CookieAuthenticationError as error:
                result = "Cookie 无效：{}".format(error)
                self._emit_status(result)
                self.log.bind(log_channel="runtime").error("Cookie 鉴权失败 | 原因={}", error)
                return result
            except asyncio.CancelledError:
                raise
            except Exception as error:
                status = "连接失败：{}；{} 秒后重连".format(
                    error,
                    self.reconnect_seconds,
                )
                self._emit_status(status)
                self.log.bind(log_channel="runtime").exception(
                    "连接断开，将重连 | 原因={} | {} 秒后重连",
                    error,
                    self.reconnect_seconds,
                )
            if await self._wait_for_stop(stop_event):
                return "已停止"
        return "已停止"

    async def _run_connection(self, stop_event: threading.Event | None) -> bool:
        checkin = await asyncio.to_thread(self._check_in)
        aid = str(checkin["aid"])
        waiter_pin = str(checkin["pin"])
        art = "customerGroupMsg"
        fallback_vender_id = str(checkin.get("venderId") or "")
        self._emit_status("签到成功，正在连接 WebSocket")
        self.log.bind(log_channel="runtime").info("签到成功，准备建立 WebSocket 连接")
        headers = {
            "Cookie": self._cookie_header(),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }

        async with websockets.connect(
            WEBSOCKET_URL,
            origin="https://dongdong.jd.com",
            additional_headers=headers,
            user_agent_header=USER_AGENT,
            open_timeout=self.connect_timeout_seconds,
            ping_interval=None,
            close_timeout=5,
        ) as connection:
            websocket = _SerializedWebSocket(connection)
            robot: JdCustomerRobot | None = None
            heartbeat_task: asyncio.Task[None] | None = None
            listen_task: asyncio.Task[None] | None = None
            stop_task: asyncio.Task[bool] | None = None
            try:
                self._emit_status("WebSocket 已连接，正在鉴权")
                self.log.bind(log_channel="runtime").info("WebSocket 已连接，开始鉴权")
                await websocket.send(_encode_packet(self._heartbeat_packet(aid, waiter_pin, art)))
                await self._authenticate(websocket, checkin, aid, waiter_pin)
                await websocket.send(_encode_packet(self._online_packet(aid, waiter_pin, art)))

                robot = JdCustomerRobot(
                    websocket,
                    waiter_pin=waiter_pin,
                    aid=aid,
                    art=art,
                    fallback_vender_id=fallback_vender_id,
                    wait_seconds=self.wait_seconds,
                    cookies=self.cookies,
                    workflow_id=self.workflow_id,
                    human_account_id=self.human_account_id,
                    human_account_name=self.human_account_name,
                    log=self.log,
                )
                await robot.log_transfer_account_names()
                heartbeat_task = asyncio.create_task(
                    self._heartbeat_loop(websocket, aid, waiter_pin, art),
                    name="jd-heartbeat",
                )
                listen_task = asyncio.create_task(robot.run(), name="jd-listener")
                self._emit_status("运行中")
                self.log.bind(log_channel="runtime").info("连接鉴权完成，机器人运行中")
                if stop_event is None:
                    await listen_task
                    return False

                stop_task = asyncio.create_task(
                    self._wait_until_stopped(stop_event),
                    name="jd-stop-waiter",
                )
                done, _ = await asyncio.wait(
                    {listen_task, stop_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if stop_task in done:
                    return True
                await listen_task
                return False
            finally:
                for task in (listen_task, stop_task, heartbeat_task):
                    if task is not None and not task.done():
                        task.cancel()
                tasks = [task for task in (listen_task, stop_task, heartbeat_task) if task is not None]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                if robot is not None:
                    await robot.close()

    def _check_in(self) -> dict[str, Any]:
        response = requests.get(
            CHECKIN_URL,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Referer": "https://dongdong.jd.com/",
                "User-Agent": USER_AGENT,
                "X-Requested-With": "XMLHttpRequest",
            },
            params=CHECKIN_PARAMS,
            cookies=self.cookies,
            timeout=self.connect_timeout_seconds,
        )
        self.cookies.update(
            {
                str(name): str(value)
                for name, value in response.cookies.items()
                if name and value
            }
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError(
                "签到接口未返回 JSON（HTTP {}）。".format(response.status_code)
            ) from error

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not data.get("aid") or not data.get("pin"):
            code = payload.get("code") if isinstance(payload, dict) else None
            if response.status_code in {401, 403} or str(code) == "412001":
                raise CookieAuthenticationError("Cookie 已失效，请重新获取。")
            raise RuntimeError(
                "签到失败：HTTP {}，业务码 {}。".format(response.status_code, code)
            )
        return data

    async def _authenticate(
        self,
        websocket: _SerializedWebSocket,
        checkin: Mapping[str, Any],
        aid: str,
        waiter_pin: str,
    ) -> None:
        auth_id = _packet_id()
        await websocket.send(
            _encode_packet(
                {
                    "id": auth_id,
                    "aid": aid,
                    "lang": "zh_CN",
                    "timestamp": int(time.time() * 1000),
                    "type": "auth",
                    "body": {
                        "presence": checkin.get("presence", "dnd"),
                        "clientVersion": str(checkin.get("clientVersion", "2.6.3")),
                    },
                    "to": {"app": "im.waiter"},
                    "from": {
                        "app": "im.waiter",
                        "pin": waiter_pin,
                        "clientType": "comet",
                        "dvc": _packet_id(),
                    },
                }
            )
        )
        auth_result = await self._receive_until_auth_result(websocket, auth_id)
        body = auth_result.get("body")
        code = body.get("code") if isinstance(body, Mapping) else None
        if code != "1":
            raise CookieAuthenticationError("WebSocket 鉴权被拒绝，返回码：{}。".format(code))

    async def _receive_until_auth_result(
        self,
        websocket: _SerializedWebSocket,
        auth_id: str,
    ) -> Mapping[str, Any]:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.connect_timeout_seconds
        while True:
            remaining = deadline - loop.time()
            if remaining <= 0:
                raise TimeoutError("等待 WebSocket 鉴权结果超时。")
            raw = await asyncio.wait_for(websocket.recv(), timeout=remaining)
            for packet in decode_packets(raw):
                if packet.get("type") == "auth_result" and packet.get("id") == auth_id:
                    return packet

    async def _heartbeat_loop(
        self,
        websocket: _SerializedWebSocket,
        aid: str,
        waiter_pin: str,
        art: str,
    ) -> None:
        await asyncio.sleep(2)
        while True:
            await websocket.send(
                _encode_packet(self._heartbeat_packet(aid, waiter_pin, art))
            )
            await asyncio.sleep(9)

    @staticmethod
    def _normalize_cookies(values: Mapping[str, object]) -> dict[str, str]:
        cookies = {
            str(name).strip(): str(value).strip()
            for name, value in values.items()
            if str(name).strip() and value is not None and str(value).strip()
        }
        if not cookies:
            raise ValueError("Cookie 为空")
        return cookies

    def _cookie_header(self) -> str:
        return "; ".join("{}={}".format(name, value) for name, value in self.cookies.items())

    def _emit_status(self, status: str) -> None:
        try:
            self.status_callback(status)
        except Exception:
            pass

    def _log_status(self, status: str) -> None:
        self.log.bind(log_channel="runtime").info("连接状态 | {}", status)

    @staticmethod
    def _stopped(stop_event: threading.Event | None) -> bool:
        return stop_event is not None and stop_event.is_set()

    async def _wait_for_stop(self, stop_event: threading.Event | None) -> bool:
        if stop_event is None:
            await asyncio.sleep(self.reconnect_seconds)
            return False
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.reconnect_seconds
        while not stop_event.is_set():
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(remaining, 0.2))
        return True

    @staticmethod
    async def _wait_until_stopped(stop_event: threading.Event) -> bool:
        while not stop_event.is_set():
            await asyncio.sleep(0.2)
        return True

    @staticmethod
    def _heartbeat_packet(aid: str, waiter_pin: str, art: str) -> dict[str, Any]:
        return {
            "id": _packet_id(),
            "type": "client_heartbeat",
            "aid": aid,
            "ver": "4.1",
            "lang": "zh_CN",
            "from": {
                "pin": waiter_pin,
                "app": "im.waiter",
                "art": art,
                "clientType": "comet",
            },
        }

    @staticmethod
    def _online_packet(aid: str, waiter_pin: str, art: str) -> dict[str, Any]:
        return {
            "id": _packet_id(),
            "aid": aid,
            "lang": "zh_CN",
            "timestamp": int(time.time() * 1000),
            "from": {
                "app": "im.waiter",
                "pin": waiter_pin,
                "art": art,
                "clientType": "comet",
            },
            "type": "waiter_status_switch",
            "body": {"s": 1},
        }
