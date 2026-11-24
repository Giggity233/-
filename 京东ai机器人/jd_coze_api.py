"""京东机器人使用的 Coze 工作流客户端。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

import requests


TOKEN_FILE = Path(__file__).resolve().parent / "data" / "COZE_TOKEN.txt"
CONVERSATION_URL = "https://api.coze.cn/v1/conversation/create"
WORKFLOW_URL = "https://api.coze.cn/v1/workflows/chat"
COZE_PARAMETER_FIELDS = (
    "aid",
    "buyer_name",
    "chathistory",
    "cookie",
    "input",
    "shopid",
    "username",
    "waiter_pin",
)


class CozeApiError(RuntimeError):
    """Coze 工作流调用无法完成。"""


def get_coze_token() -> str:
    """优先使用本项目 data/COZE_TOKEN.txt，并兼容 COZE_TOKEN 环境变量。"""
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if not token:
        token = os.environ.get("COZE_TOKEN", "").strip()
    if not token:
        raise CozeApiError("未设置 Coze Token：请写入 data/COZE_TOKEN.txt")
    return token


def build_workflow_parameters(payload: Mapping[str, Any]) -> dict[str, str]:
    """仅生成工作流约定的八个参数，不混入内部字段。"""
    if not isinstance(payload, Mapping):
        raise CozeApiError("Coze 参数必须是对象")
    return {
        field: "" if payload.get(field) is None else str(payload.get(field))
        for field in COZE_PARAMETER_FIELDS
    }


class CozeWorkflowClient:
    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        token_getter=get_coze_token,
        timeout_seconds: float = 60.0,
    ) -> None:
        self.session = session or requests.Session()
        self.token_getter = token_getter
        self.timeout_seconds = timeout_seconds

    def chat(self, payload: Mapping[str, Any], workflow_id: str) -> str:
        workflow = str(workflow_id or "").strip()
        if not workflow:
            raise CozeApiError("未选择 Coze 工作流")
        parameters = build_workflow_parameters(payload)
        token = self.token_getter()
        headers = {"Authorization": "Bearer {}".format(token), "Content-Type": "application/json"}
        conversation_id = self._create_conversation(headers)
        request_data = {
            "workflow_id": workflow,
            "parameters": parameters,
            "additional_messages": [{
                "content": parameters["input"],
                "content_type": "text",
                "role": "user",
                "type": "question",
            }],
            "conversation_id": conversation_id,
        }
        answer = self._stream_answer(headers, request_data)
        if answer is None:
            raise CozeApiError("Coze 未返回 answer 内容")
        return answer

    def _create_conversation(self, headers: Mapping[str, str]) -> str:
        try:
            response = self.session.post(
                CONVERSATION_URL,
                headers=dict(headers),
                timeout=min(self.timeout_seconds, 15.0),
            )
            response.raise_for_status()
            payload = response.json()
            conversation_id = payload["data"]["id"]
        except (requests.RequestException, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise CozeApiError("Coze 创建会话失败") from error
        if not isinstance(conversation_id, str) or not conversation_id.strip():
            raise CozeApiError("Coze 未返回有效 conversation_id")
        return conversation_id.strip()

    def _stream_answer(self, headers: Mapping[str, str], request_data: Mapping[str, Any]) -> str | None:
        answer: str | None = None
        try:
            with self.session.post(
                WORKFLOW_URL,
                json=dict(request_data),
                headers=dict(headers),
                stream=True,
                timeout=self.timeout_seconds,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    decoded = line.decode("utf-8") if isinstance(line, bytes) else str(line or "")
                    if not decoded.startswith("data:"):
                        continue
                    try:
                        event = json.loads(decoded[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "answer" and isinstance(event.get("content"), str):
                        answer = event["content"]
        except requests.RequestException as error:
            raise CozeApiError("Coze 工作流请求失败") from error
        return answer


__all__ = [
    "COZE_PARAMETER_FIELDS",
    "CozeApiError",
    "CozeWorkflowClient",
    "build_workflow_parameters",
    "get_coze_token",
]
