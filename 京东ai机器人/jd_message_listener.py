"""监听已认证的京东 WebSocket，并提取买家消息。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Optional

from loguru import logger

from jd_text import normalize_jd_emoticons

@dataclass(frozen=True)
class ReceivedMessage:
    session_id: str
    buyer_id: str
    vender_id: str
    content: str
    message_type: str
    packet: Mapping[str, Any]
    buyer_name: str = ""


MessageCallback = Callable[[ReceivedMessage], Awaitable[None]]
PacketCallback = Callable[[Mapping[str, Any]], None]


def decode_packets(raw: Any) -> list[Mapping[str, Any]]:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    if not isinstance(raw, str) or not raw:
        raise ConnectionError("WebSocket connection closed")
    payload = json.loads(raw)
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list) and all(isinstance(packet, dict) for packet in payload):
        return payload
    raise ValueError("received an unexpected WebSocket payload")


def parse_customer_message(
    packet: Mapping[str, Any],
    *,
    waiter_pin: str,
    fallback_vender_id: str = "",
) -> Optional[ReceivedMessage]:
    sender = packet.get("from")
    recipient = packet.get("to")
    body = packet.get("body")
    if not isinstance(sender, Mapping) or not isinstance(recipient, Mapping) or not isinstance(body, Mapping):
        return None
    if packet.get("type") != "chat_message" or sender.get("app") != "im.customer":
        return None
    buyer_id = sender.get("pin")
    recipient_pin = recipient.get("pin")
    message_type = body.get("type")
    if (
        not isinstance(buyer_id, str)
        or not buyer_id.strip()
        or not isinstance(recipient_pin, str)
        or recipient_pin.lower() != waiter_pin.lower()
        or message_type not in {"text", "image", "video", "voice"}
    ):
        return None

    param = body.get("param") if isinstance(body.get("param"), Mapping) else {}
    chatinfo = body.get("chatinfo") if isinstance(body.get("chatinfo"), Mapping) else {}
    request_data = body.get("requestData") if isinstance(body.get("requestData"), Mapping) else {}
    vender_id = (
        param.get("venderId")
        or chatinfo.get("venderId")
        or request_data.get("venderId")
        or fallback_vender_id
    )
    if vender_id is None or not str(vender_id).strip():
        return None

    if message_type in {"image", "video"}:
        content = body.get("url") or body.get("thumbnail")
        if not isinstance(content, str) or not content.strip():
            return None
        content = content.strip()
    elif message_type == "voice":
        content = str(body.get("text") or "").strip()
    else:
        content = str(body.get("content") or "").strip()
    content = normalize_jd_emoticons(content)

    vender_id_text = str(vender_id).strip()
    buyer_name = _buyer_name(sender, body, param, chatinfo, request_data, buyer_id)
    session_id = "{}:{}:{}".format(buyer_id.lower(), sender["app"].lower(), vender_id_text)
    return ReceivedMessage(
        session_id=session_id,
        buyer_id=buyer_id,
        vender_id=vender_id_text,
        content=content,
        message_type=str(message_type),
        packet=dict(packet),
        buyer_name=buyer_name,
    )


def _buyer_name(
    sender: Mapping[str, Any],
    body: Mapping[str, Any],
    param: Mapping[str, Any],
    chatinfo: Mapping[str, Any],
    request_data: Mapping[str, Any],
    buyer_id: str,
) -> str:
    for context in (sender, body, param, chatinfo, request_data):
        for field_name in ("nickname", "nickName", "buyerName", "customerName", "name"):
            value = context.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return buyer_id


class JdMessageListener:
    def __init__(
        self,
        waiter_pin: str,
        on_message: MessageCallback,
        *,
        fallback_vender_id: str = "",
        on_packet: Optional[PacketCallback] = None,
        log=logger,
    ) -> None:
        if not waiter_pin.strip():
            raise ValueError("waiter_pin must not be empty")
        self.waiter_pin = waiter_pin
        self.on_message = on_message
        self.fallback_vender_id = fallback_vender_id
        self.on_packet = on_packet
        self.log = log

    async def listen(self, websocket: Any) -> None:
        while True:
            raw = await websocket.recv()
            for packet in decode_packets(raw):
                if self.on_packet is not None:
                    self.on_packet(packet)
                message = parse_customer_message(
                    packet,
                    waiter_pin=self.waiter_pin,
                    fallback_vender_id=self.fallback_vender_id,
                )
                if message is None:
                    continue
                self.log.bind(log_channel="chat", buyer_id=message.buyer_id).info(
                    "收到信息 | 买家={} | 内容={}", message.buyer_id, message.content
                )
                await self.on_message(message)
