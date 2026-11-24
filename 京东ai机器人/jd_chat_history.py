"""京东 WebSocket 会话历史拉取与格式化。"""

from __future__ import annotations

import asyncio
import json
import math
import secrets
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from loguru import logger

from jd_message_listener import ReceivedMessage
from jd_text import normalize_jd_emoticons


HISTORY_PULL_COUNT = 20
DEFAULT_HISTORY_TIMEOUT_SECONDS = 10.0
Packet = Mapping[str, Any]
PacketWriter = Callable[[Packet], Awaitable[None]]


@dataclass(frozen=True)
class _PendingHistoryRequest:
    session_id: str
    future: asyncio.Future[Packet]


@dataclass(frozen=True)
class _HistoryRecord:
    line: str
    message_id: Optional[str]
    mid: Optional[int]
    sort_key: tuple[int, float, int, int]


def normalize_mid(value: object) -> Optional[int]:
    """将协议中的消息序号规范为正整数。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, float):
        return int(value) if value.is_integer() and value > 0 else None
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            result = int(text)
            return result if result > 0 else None
    return None


def _single_line_text(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.replace("\r\n", " ").replace("\r", " ").replace("\n", " ").strip()
    return normalize_jd_emoticons(text) if text else None


def _message_id(value: object) -> Optional[str]:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _packet_mid(packet: Mapping[str, Any]) -> Optional[int]:
    mid = normalize_mid(packet.get("mid"))
    if mid is not None:
        return mid
    body = packet.get("body")
    return normalize_mid(body.get("mid")) if isinstance(body, Mapping) else None


def _decode_packet(value: object) -> Optional[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _finite_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _sort_key(packet: Mapping[str, Any], mid: Optional[int], index: int) -> tuple[int, float, int, int]:
    timestamp: Optional[float] = None
    for name in ("timestamp", "clientTime", "datetime"):
        timestamp = _finite_number(packet.get(name))
        if timestamp is not None:
            break
    mid_value = mid or 0
    if timestamp is None:
        return 0, float(mid_value), mid_value, index
    return 1, timestamp, mid_value, index


def _history_record(
    packet: Mapping[str, Any],
    current: ReceivedMessage,
    waiter_pin: str,
    *,
    current_id: Optional[str],
    current_mid: Optional[int],
    index: int,
) -> Optional[_HistoryRecord]:
    if packet.get("type") != "chat_message":
        return None
    body = packet.get("body")
    sender = packet.get("from")
    if not isinstance(body, Mapping) or not isinstance(sender, Mapping):
        return None

    message_id = _message_id(packet.get("id"))
    mid = _packet_mid(packet)
    if current_id is not None and message_id == current_id:
        return None
    if current_mid is not None and mid == current_mid:
        return None

    sender_app = sender.get("app")
    sender_pin = sender.get("pin")
    app = sender_app.strip().lower() if isinstance(sender_app, str) else ""
    pin = sender_pin.strip().lower() if isinstance(sender_pin, str) else ""
    buyer_pin = current.buyer_id.strip().lower()
    normalized_waiter = waiter_pin.strip().lower()
    if (pin and pin == buyer_pin) or app == "im.customer":
        label = "【买家】："
    elif app == "im.waiter" or (pin and pin == normalized_waiter):
        label = "【客服】："
    else:
        return None

    message_type = body.get("type")
    if message_type == "text":
        content = _single_line_text(body.get("content"))
        if content is None:
            return None
        line = label + content
    elif message_type == "voice":
        content = _single_line_text(body.get("text"))
        if content is None:
            return None
        line = label + "[语音]" + content
    elif message_type in {"image", "video"}:
        media_url = _single_line_text(body.get("url")) or _single_line_text(body.get("thumbnail"))
        if media_url is None:
            return None
        line = label + ("[图片]" if message_type == "image" else "[视频]") + media_url
    else:
        return None

    return _HistoryRecord(line, message_id, mid, _sort_key(packet, mid, index))


def format_chat_history(
    raw_messages: object,
    current: ReceivedMessage,
    waiter_pin: str,
    *,
    limit: int = HISTORY_PULL_COUNT,
) -> str:
    """把 ``pull_result.body.msgs`` 清洗为供回复策略使用的对话文本。"""
    if not isinstance(raw_messages, list):
        return ""

    current_id = _message_id(current.packet.get("id"))
    current_mid = _packet_mid(current.packet)
    records: list[_HistoryRecord] = []
    for index, value in enumerate(raw_messages):
        packet = _decode_packet(value)
        if packet is None:
            continue
        record = _history_record(
            packet,
            current,
            waiter_pin,
            current_id=current_id,
            current_mid=current_mid,
            index=index,
        )
        if record is not None:
            records.append(record)

    records.sort(key=lambda record: record.sort_key, reverse=True)
    seen_ids: set[str] = set()
    seen_mids: set[int] = set()
    unique_descending: list[_HistoryRecord] = []
    for record in records:
        if record.message_id is not None and record.message_id in seen_ids:
            continue
        if record.mid is not None and record.mid in seen_mids:
            continue
        if record.message_id is not None:
            seen_ids.add(record.message_id)
        if record.mid is not None:
            seen_mids.add(record.mid)
        unique_descending.append(record)

    unique_descending.sort(key=lambda record: record.sort_key)
    return "\n".join(record.line for record in unique_descending[-limit:])


class JdChatHistory:
    """通过当前已认证的 WebSocket 请求并关联会话历史。"""

    def __init__(
        self,
        send_packet: PacketWriter,
        *,
        waiter_pin: str,
        aid: str,
        count: int = HISTORY_PULL_COUNT,
        timeout_seconds: float = DEFAULT_HISTORY_TIMEOUT_SECONDS,
        log=logger,
    ) -> None:
        if not waiter_pin.strip() or not aid.strip():
            raise ValueError("waiter_pin and aid must not be empty")
        if count < 1:
            raise ValueError("count must be greater than zero")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._send_packet = send_packet
        self.waiter_pin = waiter_pin
        self.aid = aid
        self.count = count
        self.timeout_seconds = timeout_seconds
        self.log = log
        self._pending: dict[str, _PendingHistoryRequest] = {}

    async def get_history(self, message: ReceivedMessage) -> str:
        start_mid = _packet_mid(message.packet)
        if start_mid is None:
            return ""

        request_id = secrets.token_hex(16)
        future: asyncio.Future[Packet] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = _PendingHistoryRequest(message.session_id, future)
        payload: Packet = {
            "id": request_id,
            "aid": self.aid,
            "lang": "zh_CN",
            "timestamp": int(time.time() * 1000),
            "from": {
                "app": "im.waiter",
                "pin": self.waiter_pin,
                "clientType": "comet",
            },
            "type": "pull",
            "body": {
                "sessionGroup": 1,
                "showRP": True,
                "count": self.count,
                "sessionId": message.session_id,
                "startMid": start_mid,
            },
        }
        try:
            await self._send_packet(payload)
            result = await asyncio.wait_for(asyncio.shield(future), self.timeout_seconds)
            body = result.get("body")
            if not isinstance(body, Mapping):
                return ""
            history = format_chat_history(
                body.get("msgs"),
                message,
                self.waiter_pin,
                limit=self.count,
            )
            if history:
                self.log.bind(
                    log_channel="chat",
                    buyer_id=message.buyer_id,
                    console_silent=True,
                ).info(
                    "拉取聊天记录 | 买家={} | 内容={}", message.buyer_id, history
                )
            return history
        except asyncio.CancelledError:
            raise
        except (asyncio.TimeoutError, ConnectionError) as error:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).warning(
                "聊天记录获取失败 | 买家={} | 原因={}", message.buyer_id, error
            )
            return ""
        except Exception as error:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).exception(
                "聊天记录获取异常 | 买家={} | 原因={}", message.buyer_id, error
            )
            return ""
        finally:
            pending = self._pending.get(request_id)
            if pending is not None and pending.future is future:
                self._pending.pop(request_id, None)
            if not future.done():
                future.cancel()
            elif not future.cancelled():
                future.exception()

    def handle_packet(self, packet: Mapping[str, Any]) -> bool:
        """由唯一的 WebSocket 接收循环转交 ``pull_result``。"""
        if packet.get("type") != "pull_result":
            return False
        request_id = packet.get("id")
        if not isinstance(request_id, str):
            return False
        pending = self._pending.get(request_id)
        if pending is None:
            return False
        body = packet.get("body")
        if not isinstance(body, Mapping) or body.get("sessionId") != pending.session_id:
            return False
        self._pending.pop(request_id, None)
        if not pending.future.done():
            pending.future.set_result(packet)
        return True

    def close(self) -> None:
        pending = list(self._pending.values())
        self._pending.clear()
        for request in pending:
            if not request.future.done():
                request.future.set_exception(ConnectionError("WebSocket connection closed"))


__all__ = [
    "DEFAULT_HISTORY_TIMEOUT_SECONDS",
    "HISTORY_PULL_COUNT",
    "JdChatHistory",
    "format_chat_history",
    "normalize_mid",
]
