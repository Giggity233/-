"""Coze 工作流调用封装。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dpchatjl import huoqudiyijuhua
from pdgoodscjansc import huoqushangp
from pdorder import goodsmain
from session_manager import get_session


class CozeApiError(RuntimeError):
    """Coze 或生成工作流上下文失败时抛出。"""


TOKEN_FILE = Path(__file__).resolve().parent / "data" / "COZE_TOKEN.txt"


def _coze_token() -> str:
    """优先读取 data/COZE_TOKEN.txt，未配置时兼容环境变量。"""
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        token = ""
    if not token:
        token = os.environ.get("COZE_TOKEN", "").strip()
    if not token:
        raise CozeApiError("未设置 Coze Token：请写入 data/COZE_TOKEN.txt")
    return token


def cozehuoquid() -> str:
    """创建一次 Coze 会话并返回 conversation_id。"""
    response = get_session().post(
        "https://api.coze.cn/v1/conversation/create",
        headers={"Authorization": f"Bearer {_coze_token()}", "Content-Type": "application/json"},
        timeout=15,
    )
    try:
        response.raise_for_status()
        conversation_id = response.json()["data"]["id"]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise CozeApiError("Coze 创建会话返回格式异常") from error
    if not isinstance(conversation_id, str) or not conversation_id.strip():
        raise CozeApiError("Coze 未返回有效 conversation_id")
    return conversation_id


def _workflow_context(testdata: Mapping[str, Any]) -> dict[str, Any]:
    """补齐工作流需要的订单、商品和首句上下文。"""
    required_fields = ("input", "uid", "cookieyuan", "talkid", "template_name")
    missing = [field for field in required_fields if not str(testdata.get(field, "")).strip()]
    if missing:
        raise CozeApiError(f"Coze 上下文缺少字段：{', '.join(missing)}")

    try:
        order = goodsmain(testdata["cookieyuan"], testdata["uid"], testdata["talkid"])
        huoqushangp(testdata["cookieyuan"], order["goodsid"])
        first_message = huoqudiyijuhua(testdata["cookieyuan"], testdata["uid"])
        chat_history = first_message[1]
        return {
            "CONVERSATION_NAME": "Default",
            "input": str(testdata["input"]),
            "uid": str(testdata["uid"]),
            "cookieyuan": str(testdata["cookieyuan"]),
            "talkid": str(testdata["talkid"]),
            "template_name": str(testdata["template_name"]),
            "chatjl": chat_history,
            "orderid": order["orderid"],
            "goodsid": order["goodsid"],
            "wuliu": order["wuliustate"],
        }
    except CozeApiError:
        raise
    except Exception as error:
        raise CozeApiError(f"准备 Coze 工作流上下文失败：{error}") from error


def cozeduihua(testdata: Mapping[str, Any], workflow_id: str) -> str:
    """调用工作流并返回最后一个 answer 事件的文本内容。"""
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        raise CozeApiError("workflow_id 不能为空")

    payload = {
        "workflow_id": workflow_id.strip(),
        "parameters": _workflow_context(testdata),
        "additional_messages": [
            {
                "content": str(testdata["input"]),
                "content_type": "text",
                "role": "user",
                "type": "question",
            }
        ],
        "conversation_id": cozehuoquid(),
    }
    try:
        with get_session().post(
            "https://api.coze.cn/v1/workflows/chat",
            json=payload,
            headers={"Authorization": f"Bearer {_coze_token()}", "Content-Type": "application/json"},
            stream=True,
            timeout=60,
        ) as response:
            response.raise_for_status()
            answer_content: str | None = None
            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data:"):
                    continue
                try:
                    event = json.loads(decoded[5:])
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "answer":
                    content = event.get("content")
                    if isinstance(content, str):
                        answer_content = content
    except CozeApiError:
        raise
    except Exception as error:
        raise CozeApiError(f"Coze 调用异常：{error}") from error

    if answer_content is None:
        raise CozeApiError("Coze 未返回 answer 内容")
    return answer_content


__all__ = ["CozeApiError", "cozeduihua", "cozehuoquid"]
