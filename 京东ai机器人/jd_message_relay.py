"""按买家会话固定等待八秒，聚合后调用独立回复策略。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Optional

from loguru import logger

from jd_message_listener import ReceivedMessage
from jd_message_sender import JdMessageSender
from jd_reply_handler import ReplyAction
from jd_text import normalize_jd_emoticons
from jd_media import (
    MediaProbeError,
    parse_image_directive,
    parse_video_directive,
    probe_image_metadata,
    probe_video_metadata,
)


ReplyHandler = Callable[[Mapping[str, Any]], Awaitable[Optional[str] | ReplyAction]]
CookieProvider = Callable[[], str]
ReplyContextProvider = Callable[[], Mapping[str, Any]]
ChatHistoryProvider = Callable[[ReceivedMessage], Awaitable[str]]
TransferHandler = Callable[[ReceivedMessage, str], Awaitable[bool]]


@dataclass
class _PendingBatch:
    messages: list[ReceivedMessage] = field(default_factory=list)
    task: Optional[asyncio.Task[None]] = None


class JdMessageRelay:
    def __init__(
        self,
        sender: JdMessageSender,
        reply_handler: ReplyHandler,
        *,
        wait_seconds: float = 8.0,
        cookie_provider: Optional[CookieProvider] = None,
        reply_context_provider: Optional[ReplyContextProvider] = None,
        chat_history_provider: Optional[ChatHistoryProvider] = None,
        transfer_handler: Optional[TransferHandler] = None,
        log=logger,
    ) -> None:
        if wait_seconds <= 0:
            raise ValueError("wait_seconds must be greater than zero")
        self.sender = sender
        self.reply_handler = reply_handler
        self.wait_seconds = wait_seconds
        self.cookie_provider = cookie_provider or (lambda: "")
        self.reply_context_provider = reply_context_provider
        self.chat_history_provider = chat_history_provider
        self.transfer_handler = transfer_handler
        self.log = log
        self._lock = asyncio.Lock()
        self._pending: dict[str, _PendingBatch] = {}
        self._transferring_sessions: set[str] = set()
        self._transferred_sessions: set[str] = set()

    async def receive(self, message: ReceivedMessage) -> None:
        await self.sender.acknowledge_received(message)
        async with self._lock:
            if message.session_id in self._transferred_sessions or message.session_id in self._transferring_sessions:
                self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).info(
                    "转人工会话忽略后续消息 | 买家={}", message.buyer_id
                )
                return
            batch = self._pending.get(message.session_id)
            if batch is None:
                batch = _PendingBatch()
                self._pending[message.session_id] = batch
                batch.task = asyncio.create_task(
                    self._flush(message.session_id, batch),
                    name="jd-reply-batch-{}".format(message.session_id),
                )
            batch.messages.append(message)

    async def close(self) -> None:
        async with self._lock:
            tasks = [batch.task for batch in self._pending.values() if batch.task is not None]
            self._pending.clear()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _flush(self, session_id: str, expected: _PendingBatch) -> None:
        try:
            await asyncio.sleep(self.wait_seconds)
            async with self._lock:
                batch = self._pending.get(session_id)
                if batch is not expected:
                    return
                self._pending.pop(session_id, None)
            if not batch.messages:
                return
            latest = batch.messages[-1]
            combined_text = normalize_jd_emoticons(
                "\n".join(message.content for message in batch.messages if message.content)
            )
            chathistory = normalize_jd_emoticons(await self._chat_history(latest))
            context = self._reply_context()
            payload = {
                "aid": str(context.get("aid") or ""),
                "buyer_name": latest.buyer_name or latest.buyer_id,
                "chathistory": chathistory,
                "cookie": self.cookie_provider(),
                "input": combined_text,
                "shopid": latest.vender_id,
                "username": str(context.get("username") or context.get("waiter_pin") or ""),
                "waiter_pin": str(context.get("waiter_pin") or ""),
            }
            self.log.bind(log_channel="chat", buyer_id=latest.buyer_id).info(
                "8秒拼接消息 | 买家={} | 内容={}", latest.buyer_id, combined_text
            )
            result = await self.reply_handler(payload)
            if isinstance(result, ReplyAction):
                if result.needs_transfer:
                    await self._transfer_to_human(latest, result.transfer_reason)
                    return
                reply: Optional[str] = result.text
            else:
                reply = result
            if reply is not None:
                if not isinstance(reply, str):
                    raise TypeError("reply handler must return str, ReplyAction, or None")
                await self._send_reply(latest, reply)
        except asyncio.CancelledError:
            return
        except Exception as error:
            self.log.bind(log_channel="runtime", session_id=session_id).exception(
                "回复处理失败 | 会话={} | 原因={}", session_id, error
            )

    async def _send_reply(self, message: ReceivedMessage, reply: str) -> None:
        try:
            image = parse_image_directive(reply)
            if image is not None:
                metadata = await asyncio.to_thread(probe_image_metadata, image)
                await self.sender.send_image(
                    message,
                    url=image.image_url,
                    width=metadata.width,
                    height=metadata.height,
                )
                return

            video = parse_video_directive(reply)
            if video is not None:
                metadata = await asyncio.to_thread(probe_video_metadata, video)
                await self.sender.send_video(
                    message,
                    url=video.video_url,
                    size=metadata.size,
                    duration=metadata.duration,
                    thumbnail=video.thumbnail_url,
                    thumb_width=metadata.thumb_width,
                    thumb_height=metadata.thumb_height,
                )
                return
        except MediaProbeError as error:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).error(
                "媒体发送失败 | 买家={} | 原因={}", message.buyer_id, error
            )
            return
        except Exception as error:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).exception(
                "媒体发送异常 | 买家={} | 原因={}", message.buyer_id, error
            )
            return
        await self.sender.send_text(message, reply)

    async def _transfer_to_human(self, message: ReceivedMessage, reason: str) -> None:
        handler = self.transfer_handler
        if handler is None:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).error(
                "无法转人工 | 买家={} | 原因=未配置转人工处理器", message.buyer_id
            )
            return
        async with self._lock:
            self._transferring_sessions.add(message.session_id)
        try:
            transferred = await handler(message, reason)
            if transferred:
                async with self._lock:
                    if len(self._transferred_sessions) >= 10000:
                        self._transferred_sessions.clear()
                    self._transferred_sessions.add(message.session_id)
        finally:
            async with self._lock:
                self._transferring_sessions.discard(message.session_id)

    def _reply_context(self) -> Mapping[str, Any]:
        provider = self.reply_context_provider
        if provider is None:
            return {}
        try:
            context = provider()
        except Exception:
            return {}
        return context if isinstance(context, Mapping) else {}

    async def _chat_history(self, message: ReceivedMessage) -> str:
        provider = self.chat_history_provider
        if provider is None:
            return ""
        try:
            history = await provider(message)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.log.bind(log_channel="runtime", buyer_id=message.buyer_id).exception(
                "聊天记录获取失败 | 买家={} | 原因={}", message.buyer_id, error
            )
            return ""
        if not isinstance(history, str):
            return ""
        if history:
            self.log.bind(
                log_channel="chat",
                buyer_id=message.buyer_id,
                console_silent=True,
            ).info(
                "聊天记录 | 买家={} | 内容={}", message.buyer_id, history
            )
        return history
