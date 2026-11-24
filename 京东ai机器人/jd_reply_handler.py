"""Coze 回复解析：仅发送 ``@@@@`` 之后的内容，必要时转人工。"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from loguru import logger

from jd_coze_api import CozeWorkflowClient


@dataclass(frozen=True)
class ReplyAction:
    """回复策略的结果；转人工时不应发送任何文字。"""

    text: str = ""
    transfer_reason: str = ""

    @property
    def needs_transfer(self) -> bool:
        return bool(self.transfer_reason)

    @classmethod
    def transfer(cls, reason: str) -> "ReplyAction":
        return cls(transfer_reason=reason)


def _coze_output(raw_response: str) -> str:
    """返回 Coze 工作流的原始文本结果。

    工作流约定直接返回 ``前缀@@@@发送内容``，不使用 JSON 包装。
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise ValueError("Coze 返回为空")
    return raw_response.strip()


async def reply_for_message(
    payload: Mapping[str, Any],
    *,
    workflow_id: str,
    client: CozeWorkflowClient | None = None,
    log=logger,
) -> ReplyAction:
    """调用 Coze 并转换为“回复”或“转人工”动作。"""
    coze_client = client or CozeWorkflowClient()
    try:
        raw_response = await asyncio.to_thread(coze_client.chat, payload, workflow_id)
        output = _coze_output(raw_response)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        log.bind(log_channel="runtime").exception("Coze 调用或解析失败 | 原因={}", error)
        return ReplyAction.transfer("Coze 调用或返回异常")

    if output.startswith("{") and output.endswith("}"):
        log.bind(log_channel="runtime").warning("Coze 回复不是约定的原始文本格式，转人工")
        return ReplyAction.transfer("Coze 回复格式错误")
    if "@@@@" not in output:
        log.bind(log_channel="runtime").warning("Coze 回复未包含 @@@@，转人工")
        return ReplyAction.transfer("Coze 回复未包含 @@@@")
    text = output.split("@@@@", 1)[1].strip()
    if not text:
        log.bind(log_channel="runtime").warning("Coze 回复 @@@@ 后为空，转人工")
        return ReplyAction.transfer("Coze 回复 @@@@ 后为空")
    if "人工" in text:
        log.bind(log_channel="runtime").info("Coze 回复包含人工，转人工")
        return ReplyAction.transfer("Coze 回复包含人工")
    log.bind(log_channel="chat").info("Coze 回复 | 内容={}", text)
    return ReplyAction(text=text)


def build_reply_handler(
    workflow_id: str,
    *,
    client: CozeWorkflowClient | None = None,
    log=logger,
) -> Callable[[Mapping[str, Any]], Awaitable[ReplyAction]]:
    """将启动时选择的工作流固定到当前店铺机器人的回复函数。"""

    async def handler(payload: Mapping[str, Any]) -> ReplyAction:
        return await reply_for_message(payload, workflow_id=workflow_id, client=client, log=log)

    return handler


__all__ = ["ReplyAction", "build_reply_handler", "reply_for_message"]
