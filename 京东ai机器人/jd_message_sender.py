"""向已认证的京东 WebSocket 串行发送确认包和文本回复。"""

from __future__ import annotations

import asyncio
import json
import secrets
import time
from typing import Any, Awaitable, Callable, Mapping

from loguru import logger

from jd_message_listener import ReceivedMessage


PacketWriter = Callable[[str], Awaitable[None]]


class JdMessageSender:
    def __init__(self, write_packet: PacketWriter, *, waiter_pin: str, aid: str, art: str = "", log=logger) -> None:
        if not waiter_pin.strip() or not aid.strip():
            raise ValueError("waiter_pin and aid must not be empty")
        self.write_packet = write_packet
        self.waiter_pin = waiter_pin
        self.aid = aid
        self.art = art
        self.log = log
        self._send_lock = asyncio.Lock()

    async def acknowledge_received(self, message: ReceivedMessage) -> None:
        packet = message.packet
        body = packet.get("body") if isinstance(packet.get("body"), Mapping) else {}
        sender = packet.get("from") if isinstance(packet.get("from"), Mapping) else {}
        mid = packet.get("mid", body.get("mid"))
        if not isinstance(mid, int):
            raise ValueError("incoming message does not contain a numeric mid")
        await self._send({
            "type": "msg_receive_ack",
            "aid": self.aid,
            "from": {
                "art": self.art,
                "pin": self.waiter_pin,
                "app": "im.waiter",
                "clientType": "comet",
            },
            "lang": "zh_CN",
            "body": [{
                "mid": mid,
                "sender": sender.get("pin", "@im.jd.com"),
                "app": sender.get("app", "im.customer"),
                "sessionId": message.session_id,
                "id": packet.get("id"),
                "datetime": packet.get("datetime"),
            }],
            "ver": "4.3",
        })

    async def send_text(self, message: ReceivedMessage, text: str) -> bool:
        reply = text.strip()
        if not reply:
            return False
        await self._send({
            "ver": "4.3",
            "type": "chat_message",
            "from": {
                "pin": self.waiter_pin,
                "app": "im.waiter",
                "clientType": "comet",
            },
            "to": {"app": "im.customer", "pin": message.buyer_id},
            "id": secrets.token_hex(16),
            "lang": "zh_CN",
            "aid": self.aid,
            "timestamp": int(time.time() * 1000),
            "readFlag": 0,
            "body": {
                "content": reply,
                "translated": False,
                "param": {"cusVenderId": message.vender_id},
                "type": "text",
            },
        })
        self.log.bind(log_channel="chat", buyer_id=message.buyer_id).info(
            "发送文本 | 买家={} | 内容={}", message.buyer_id, reply
        )
        return True

    async def send_image(
        self,
        message: ReceivedMessage,
        *,
        url: str,
        width: int,
        height: int,
        thumbnail: str = "",
    ) -> bool:
        if not url.strip() or width <= 0 or height <= 0:
            raise ValueError("image url, width, and height must be valid")
        await self._send({
            "ver": "4.3",
            "type": "chat_message",
            "from": {
                "pin": self.waiter_pin,
                "app": "im.waiter",
                "clientType": "comet",
            },
            "to": {"app": "im.customer", "pin": message.buyer_id},
            "id": secrets.token_hex(16),
            "lang": "zh_CN",
            "aid": self.aid,
            "timestamp": int(time.time() * 1000),
            "body": {
                "url": url,
                "width": width,
                "height": height,
                "thumbnail": thumbnail,
                "param": {"cusVenderId": message.vender_id},
                "type": "image",
            },
        })
        self.log.bind(log_channel="chat", buyer_id=message.buyer_id).info(
            "发送图片 | 买家={} | 地址={}", message.buyer_id, url
        )
        return True

    async def send_video(
        self,
        message: ReceivedMessage,
        *,
        url: str,
        size: int,
        duration: int,
        thumbnail: str,
        thumb_width: int,
        thumb_height: int,
        desc: str = "",
        reupload: bool = False,
    ) -> bool:
        if not url.strip() or not thumbnail.strip():
            raise ValueError("video url and thumbnail must not be empty")
        if any(value < 0 for value in (size, duration, thumb_width, thumb_height)):
            raise ValueError("video metadata must not be negative")
        await self._send({
            "ver": "4.3",
            "type": "chat_message",
            "from": {
                "pin": self.waiter_pin,
                "app": "im.waiter",
                "clientType": "comet",
            },
            "to": {"app": "im.customer", "pin": message.buyer_id},
            "id": secrets.token_hex(16),
            "lang": "zh_CN",
            "aid": self.aid,
            "timestamp": int(time.time() * 1000),
            "body": {
                "url": url,
                "size": size,
                "desc": desc,
                "duration": duration,
                "thumbnail": thumbnail,
                "thumbHeight": thumb_height,
                "thumbWidth": thumb_width,
                "reupload": reupload,
                "param": {},
                "type": "video",
            },
        })
        self.log.bind(log_channel="chat", buyer_id=message.buyer_id).info(
            "发送视频 | 买家={} | 地址={}", message.buyer_id, url
        )
        return True

    async def _send(self, packet: Mapping[str, Any]) -> None:
        encoded = json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
        async with self._send_lock:
            await self.write_packet(encoded)

    async def send_packet(self, packet: Mapping[str, Any]) -> None:
        """发送协议包，供会话历史等共享同一 WebSocket 的服务使用。"""
        await self._send(packet)
