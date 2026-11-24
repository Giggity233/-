"""京东 WebSocket 人工转接。"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

from loguru import logger

from jd_message_listener import ReceivedMessage


PacketWriter = Callable[[Mapping[str, Any]], Awaitable[None]]
TRANSFER_RETRY_DELAYS_SECONDS = (5, 10, 20)


class JdHumanTransfer:
    """将买家转给当前店铺首个人工账号的 ID。"""

    def __init__(
        self,
        send_packet: PacketWriter,
        *,
        waiter_pin: str,
        aid: str,
        art: str = "",
        human_account_id: str = "",
        human_account_name: str = "",
        timeout_seconds: float = 10.0,
        log=logger,
    ) -> None:
        if not waiter_pin.strip() or not aid.strip():
            raise ValueError("waiter_pin and aid must not be empty")
        self._send_packet = send_packet
        self.waiter_pin = waiter_pin
        self.aid = aid
        self.art = art
        self.human_account_id = str(human_account_id or "").strip()
        self.human_account_name = str(human_account_name or "").strip()
        self.timeout_seconds = timeout_seconds
        self.log = log
        self._pending_transfer: dict[str, asyncio.Future[Mapping[str, Any]]] = {}

    async def transfer_to_human(self, message: ReceivedMessage, reason: str) -> bool:
        """取得店铺人工账号 ID 后直接转接，失败按 5/10/20 秒重试。"""
        failure_reason = "人工转接失败"
        for attempt in range(1, len(TRANSFER_RETRY_DELAYS_SECONDS) + 2):
            target_waiter, failure_reason = await self._select_transfer_waiter()
            succeeded = False
            if target_waiter:
                succeeded = await self._transfer(message.buyer_id, target_waiter, reason)
                if not succeeded:
                    failure_reason = "京东转接接口未成功"
            if succeeded:
                self.log.bind(log_channel="runtime", buyer_id=message.buyer_id, target_waiter=target_waiter).info(
                    "转人工成功 | 买家={} | 目标人工={} | 原因={}",
                    message.buyer_id,
                    target_waiter,
                    reason,
                )
                return True
            if attempt <= len(TRANSFER_RETRY_DELAYS_SECONDS):
                delay = TRANSFER_RETRY_DELAYS_SECONDS[attempt - 1]
                self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).warning(
                    "转人工失败，将重试 | 买家={} | 第{}次 | {} 秒后重试 | 原因={}",
                    message.buyer_id,
                    attempt,
                    delay,
                    failure_reason,
                )
                await asyncio.sleep(delay)

        self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).error(
            "转人工最终失败 | 买家={} | 原因={}", message.buyer_id, failure_reason
        )
        return False

    async def log_transfer_account_names(self) -> list[str]:
        """启动后显示页面读取并缓存的当前店铺首个人工账号。"""
        account_names = [self.human_account_name or self.human_account_id] if self.human_account_id else []
        self.log.bind(log_channel="runtime").info(
            "可转接人工账号 | 当前客服={} | 账号名称={} | 账号ID={}",
            self.waiter_pin,
            "、".join(account_names) if account_names else "未配置",
            self.human_account_id or "未配置",
        )
        return account_names

    async def _select_transfer_waiter(self) -> tuple[str | None, str]:
        if not self.human_account_id:
            return None, "当前店铺首个人工账号没有有效 ID"
        return self.human_account_id, ""

    async def _transfer(self, buyer_id: str, target_waiter: str, reason: str) -> bool:
        request_id = secrets.token_hex(16)
        future: asyncio.Future[Mapping[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending_transfer[request_id] = future
        packet = {
            "id": request_id,
            "aid": self.aid,
            "lang": "zh_CN",
            "timestamp": int(time.time() * 1000),
            "from": {
                "app": "im.waiter",
                "pin": self.waiter_pin,
                "art": self.art,
                "clientType": "comet",
            },
            "type": "chat_transfer_partern",
            "body": {
                "customer": buyer_id,
                "cappId": "im.customer",
                "waiter": target_waiter,
                # 转接接口保留该必填字段，但按业务要求不填写转接原因；
                # 同时不传订单号或商品号相关字段。
                "reason": "",
            },
        }
        try:
            await self._send_packet(packet)
            response = await asyncio.wait_for(asyncio.shield(future), self.timeout_seconds)
            body = response.get("body")
            if not isinstance(body, Mapping):
                return False
            biz_code = body.get("bizCode")
            result_code = biz_code.get("code") if isinstance(biz_code, Mapping) else None
            return str(body.get("code")) == "1" and str(result_code) == "1"
        except asyncio.TimeoutError:
            self.log.bind(log_channel="runtime", buyer_id=buyer_id, target_waiter=target_waiter).error(
                "转人工等待结果超时 | 买家={} | 目标人工={}", buyer_id, target_waiter
            )
            return False
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.log.bind(log_channel="runtime", buyer_id=buyer_id, target_waiter=target_waiter).exception(
                "转人工请求异常 | 买家={} | 目标人工={} | 原因={}", buyer_id, target_waiter, error
            )
            return False
        finally:
            self._pending_transfer.pop(request_id, None)
            if not future.done():
                future.cancel()

    def handle_packet(self, packet: Mapping[str, Any]) -> bool:
        packet_id = packet.get("id")
        if not isinstance(packet_id, str):
            return False
        if packet.get("type") == "chat_transfer_result":
            return self._resolve(self._pending_transfer, packet_id, packet)
        return False

    @staticmethod
    def _resolve(
        pending: dict[str, asyncio.Future[Mapping[str, Any]]],
        packet_id: str,
        packet: Mapping[str, Any],
    ) -> bool:
        future = pending.pop(packet_id, None)
        if future is None or future.done():
            return False
        future.set_result(packet)
        return True

    def close(self) -> None:
        for pending in (self._pending_transfer,):
            futures = list(pending.values())
            pending.clear()
            for future in futures:
                if not future.done():
                    future.set_exception(ConnectionError("WebSocket connection closed"))

__all__ = ["JdHumanTransfer", "TRANSFER_RETRY_DELAYS_SECONDS"]
