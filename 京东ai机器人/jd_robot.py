"""将京东消息监听、八秒聚合和发送回复组合为可复用机器人。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from jd_chat_history import JdChatHistory
from jd_human_transfer import JdHumanTransfer
from jd_message_listener import JdMessageListener, ReceivedMessage
from jd_message_relay import JdMessageRelay
from jd_message_sender import JdMessageSender
from jd_reply_handler import build_reply_handler
from loguru import logger


class JdCustomerRobot:
    def __init__(
        self,
        websocket: Any,
        *,
        waiter_pin: str,
        aid: str,
        art: str = "",
        fallback_vender_id: str = "",
        wait_seconds: float = 8.0,
        cookies: Mapping[str, str] | None = None,
        workflow_id: str = "",
        human_account_id: str = "",
        human_account_name: str = "",
        log=logger,
    ) -> None:
        self.websocket = websocket
        self.cookies = cookies or {}
        self.waiter_pin = waiter_pin
        self.aid = aid
        self.log = log
        self.sender = JdMessageSender(
            websocket.send,
            waiter_pin=waiter_pin,
            aid=aid,
            art=art,
            log=log,
        )
        self.chat_history = JdChatHistory(
            self.sender.send_packet,
            waiter_pin=waiter_pin,
            aid=aid,
            log=log,
        )
        self.human_transfer = JdHumanTransfer(
            self.sender.send_packet,
            waiter_pin=waiter_pin,
            aid=aid,
            art=art,
            human_account_id=human_account_id,
            human_account_name=human_account_name,
            log=log,
        )
        self.relay = JdMessageRelay(
            self.sender,
            build_reply_handler(workflow_id, log=log),
            wait_seconds=wait_seconds,
            cookie_provider=self._cookie_text,
            reply_context_provider=self._reply_context,
            chat_history_provider=self.chat_history.get_history,
            transfer_handler=self.human_transfer.transfer_to_human,
            log=log,
        )
        self.listener = JdMessageListener(
            waiter_pin,
            self._receive,
            fallback_vender_id=fallback_vender_id,
            on_packet=self._handle_packet,
            log=log,
        )

    async def run(self) -> None:
        await self.listener.listen(self.websocket)

    async def close(self) -> None:
        try:
            await self.relay.close()
        finally:
            self.chat_history.close()
            self.human_transfer.close()

    async def log_transfer_account_names(self) -> list[str]:
        return await self.human_transfer.log_transfer_account_names()

    async def _receive(self, message: ReceivedMessage) -> None:
        await self.relay.receive(message)

    def _cookie_text(self) -> str:
        return "; ".join(
            "{}={}".format(name, value) for name, value in self.cookies.items()
        )

    def _reply_context(self) -> Mapping[str, str]:
        return {
            "username": self.waiter_pin,
            "waiter_pin": self.waiter_pin,
            "aid": self.aid,
        }

    def _handle_packet(self, packet: Mapping[str, Any]) -> None:
        self.chat_history.handle_packet(packet)
        self.human_transfer.handle_packet(packet)
