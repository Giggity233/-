"""抖店会话转人工接口。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests


class TransferToHumanError(RuntimeError):
    """转人工请求无法完成时抛出。"""


def parse_cookie_string(cookie_str: str | Mapping[str, Any]) -> dict[str, str]:
    """将 Cookie 字符串或字典转换为 requests 可用的字典。"""
    if isinstance(cookie_str, Mapping):
        return {str(key): str(value) for key, value in cookie_str.items() if value is not None}
    if not isinstance(cookie_str, str) or not cookie_str.strip():
        return {}

    cookies: dict[str, str] = {}
    for pair in (item.strip() for item in cookie_str.split(";") if item.strip()):
        if "=" not in pair:
            cookies[pair] = ""
            continue
        key, value = pair.split("=", 1)
        cookies[key.strip()] = value.strip()
    return cookies


def zhuanrg(
    cookesyuan: str | Mapping[str, Any],
    uid: str,
    to_cid: str,
    *,
    timeout: float = 15,
) -> dict[str, Any]:
    """把指定买家会话转给人工账号，并返回接口状态和响应体。"""
    cookies = parse_cookie_string(cookesyuan)
    shop_id = cookies.get("SHOP_ID", "").strip()
    if not shop_id:
        raise TransferToHumanError("Cookie 中没有 SHOP_ID，无法转人工")
    if not str(uid).strip() or not str(to_cid).strip():
        raise TransferToHumanError("转人工缺少买家会话 UID 或人工账号 CID")

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "origin": "https://im.jinritemai.com",
        "referer": "https://im.jinritemai.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/156.0.0.0 Safari/537.36",
        "x-secsdk-csrf-token": "DOWNGRADE",
    }
    response = requests.post(
        "https://pigeon.jinritemai.com/chat/api/backstage/conversation/transfer_conversation",
        headers=headers,
        cookies=cookies,
        params={"PIGEON_BIZ_TYPE": "2", "device_platform": "web"},
        json={
            "securityBizConversationId": f"{uid}:{shop_id}::2:1:pigeon",
            "toCid": str(to_cid),
            "extParams": "{}",
        },
        timeout=timeout,
    )
    try:
        body: Any = response.json()
    except ValueError:
        body = {"raw_response": response.text[:500]}
    if not response.ok:
        raise TransferToHumanError(f"转人工 HTTP {response.status_code}：{body}")
    return {"status_code": response.status_code, "body": body}


__all__ = ["TransferToHumanError", "parse_cookie_string", "zhuanrg"]
