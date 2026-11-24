"""仅发送抖店客服纯文本的 WebSocket 工具。

本模块不会监听消息、查询订单或商品、调用 AI，也不会更新 Cookie。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import re
import subprocess
import time
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import websockets


_BASE_DIR = Path(__file__).resolve().parent
_ENCODER_SCRIPT = _BASE_DIR / "js" / "encode_ws_message.js"
_PROTOC = _BASE_DIR / "protoc" / "bin" / "protoc.exe"
_DEVICE_ID = "1469396562216643"
_ACCESS_KEY_SALT = "f8a69f1719916z"

_HTTP_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://im.jinritemai.com",
    "referer": "https://im.jinritemai.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/138.0.0.0 Safari/537.36"
    ),
}

_WS_HEADERS = {
    "Origin": "https://im.jinritemai.com",
    "User-Agent": _HTTP_HEADERS["user-agent"],
    "Sec-WebSocket-Protocol": "binary, base64",
}

_TEXT_DIMENSION = (
    '{"dynamic_dimension":"4541_1131_8272_6599_9420_6832_4050_3823_3994_8564_1528_0388_8667_2179_'
    '7948_1870_1948_0989_8012_6240_7898_7548_8852_6245_9393_3650_1549_4026_4034_4057_6537_8632_'
    '2068_8958_0363_2216_2387_0676_9033_0210_3425_2239_0982_1935_8188_3817_8557_7931_3278_4065_'
    '1894_6049_6961_3814_4883_4401_6638_7282_3652_0568_9354_0438_4769_4815_9572_7230_5054_7510_'
    '4852_2188_3505_6813_2570_5394_0729","goofy_id":"1.0.1.1625","desk_version":"0.0.0",'
    '"open_stores":"0","memL":"","cpuL":"","session_throughput":0,"message_throughput_send":0,'
    '"message_throughput_revice":0}'
)


class BuyerMessageSenderError(RuntimeError):
    """Cookie、连接参数或 Protobuf 解码不符合要求时抛出。"""


def _parse_cookie(cookie: str | Mapping[str, Any]) -> dict[str, str]:
    """把浏览器导出的 Cookie 字符串或字典规范化为 requests 可用的字典。"""
    if isinstance(cookie, Mapping):
        result = {str(key).strip(): str(value).strip() for key, value in cookie.items() if str(key).strip()}
    elif isinstance(cookie, str):
        cookie_text = cookie.strip()
        if cookie_text.lower().startswith("cookie:"):
            cookie_text = cookie_text.split(":", 1)[1].strip()
        result = {}
        for part in cookie_text.replace("\n", ";").split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key:
                result[key] = value.strip()
    else:
        raise TypeError("cookie 必须是完整的 Cookie 字符串或 dict")

    missing = [key for key in ("PIGEON_CID", "SHOP_ID") if not result.get(key)]
    if missing:
        raise BuyerMessageSenderError(
            "Cookie 缺少 " + ", ".join(missing) + "。请从抖店客服页面导出完整 Cookie。"
        )
    return result


def _get_link_info(cookies: dict[str, str]) -> tuple[str, str, str, str, str]:
    """使用 Cookie 获取本次 WebSocket 连接必需的临时参数。"""
    response = requests.get(
        "https://pigeon.jinritemai.com/chat/api/backstage/conversation/get_link_info",
        headers=_HTTP_HEADERS,
        cookies=cookies,
        params={
            "PIGEON_BIZ_TYPE": ["2", "2"],
            "biz_type": "4",
            "_ts": str(int(time.time() * 1000)),
            "_pms": "1",
            "FUSION": "true",
        },
        timeout=30,
    )
    response.raise_for_status()

    try:
        payload = response.json()
        data = payload["data"]
        if payload.get("code") not in (0, None) or not isinstance(data, dict):
            raise KeyError("data")
        frontier = data["frontierConfig"]
        return (
            str(data["token"]),
            str(data["appId"]),
            str(data["pigeon_sign"]),
            str(frontier["fpId"]),
            str(frontier["appKey"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise BuyerMessageSenderError("Cookie 无效、已过期，或获取 WebSocket 连接参数失败") from error


def _build_websocket_url(token: str, app_id: str, pigeon_sign: str, fp_id: str, app_key: str) -> str:
    access_key_source = f"{fp_id}{app_key}{_DEVICE_ID}{_ACCESS_KEY_SALT}"
    access_key = hashlib.md5(access_key_source.encode("utf-8")).hexdigest()
    query = urlencode(
        {
            "token": token,
            "aid": app_id,
            "fpid": fp_id,
            "device_id": _DEVICE_ID,
            "access_key": access_key,
            "device_platform": "web",
            "version_code": "10000",
            "pigeon_source": "web",
            "PIGEON_BIZ_TYPE": "2",
            "pigeon_sign": pigeon_sign,
        }
    )
    return f"wss://ws.fxg.jinritemai.com/ws/v2?{query}"


def _run_node_json(script: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """执行本地 Node 协议脚本，并只接受一个 JSON 对象结果。"""
    if not script.is_file():
        raise BuyerMessageSenderError(f"缺少协议文件：{script}")
    try:
        completed = subprocess.run(
            ["node", str(script)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    except FileNotFoundError as error:
        raise BuyerMessageSenderError("未找到 Node.js。请安装 Node.js 后执行 npm install。") from error
    except subprocess.TimeoutExpired as error:
        raise BuyerMessageSenderError("WebSocket 协议处理超时") from error

    if completed.returncode != 0:
        details = completed.stderr.strip() or "未知 Node.js 解码错误"
        raise BuyerMessageSenderError(f"WebSocket 协议处理失败：{details}")
    try:
        decoded = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BuyerMessageSenderError("Node.js 协议脚本没有返回有效 JSON") from error
    if not isinstance(decoded, dict):
        raise BuyerMessageSenderError("Node.js 协议脚本返回的不是 JSON 对象")
    return decoded


def _encode_send_frame(
    message_request: dict[str, Any],
    token: str,
    pigeon_sign: str,
    pigeon_cid: str,
    app_id: str,
) -> bytes:
    """用原项目的 Protobuf 编码器生成一条 WebSocket 发送帧。"""
    result = _run_node_json(
        _ENCODER_SCRIPT,
        {
            "request": message_request,
            "token": token,
            "pigeon_sign": pigeon_sign,
            "pigeon_cid": pigeon_cid,
            "app_id": app_id,
        },
    )
    frame = result.get("frame")
    if not isinstance(frame, str):
        raise BuyerMessageSenderError("发送帧编码结果缺少 frame")
    try:
        return base64.b64decode(frame, validate=True)
    except ValueError as error:
        raise BuyerMessageSenderError("发送帧编码结果不是有效 base64") from error


def _encode_varint(value: int) -> bytes:
    if value < 0:
        raise ValueError("Protobuf varint 不支持负数")
    output = bytearray()
    while value > 0x7F:
        output.append((value & 0x7F) | 0x80)
        value >>= 7
    output.append(value)
    return bytes(output)


def _varint_field(number: int, value: int) -> bytes:
    return _encode_varint(number << 3) + _encode_varint(value)


def _bytes_field(number: int, value: bytes | str) -> bytes:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    return _encode_varint((number << 3) | 2) + _encode_varint(len(raw)) + raw


def _header_entry(key: str, value: str) -> bytes:
    return _bytes_field(1, key) + _bytes_field(2, value)


def _build_ticket_request(token: str, pigeon_sign: str, app_id: str, pigeon_cid: str) -> bytes:
    """构造获取会话 ticket 所需的 Protobuf 请求，不含任何业务逻辑。"""
    headers = {
        "pigeon_source": "web",
        "PIGEON_BIZ_TYPE": "2",
        "pigeon_sign": pigeon_sign + "z",
        "session_aid": app_id,
        "session_did": pigeon_cid,
        "app_name": "im",
        "priority_region": "cn",
        "user_agent": _HTTP_HEADERS["user-agent"],
        "cookie_enabled": "true",
        "browser_language": "zh-CN",
        "browser_platform": "Win32",
        "browser_name": "Mozilla",
        "browser_version": _HTTP_HEADERS["user-agent"].removeprefix("Mozilla/"),
        "browser_online": "true",
        "screen_width": "1366",
        "screen_height": "768",
        "referer": f"https://im.jinritemai.com/pc_seller/?selfId={pigeon_cid}",
        "timezone_name": "Asia/Shanghai",
    }
    parts = [
        _varint_field(1, 203),
        _varint_field(2, 10001),
        _bytes_field(3, "1.0.5-beta.0"),
        _bytes_field(4, token),
        _varint_field(5, 3),
        _varint_field(6, 3),
        _bytes_field(7, "b118b58:fix/export_info"),
        _bytes_field(8, b"\xda\x0c\x02\x08\x00"),
        _bytes_field(9, pigeon_cid),
        _bytes_field(11, "web"),
    ]
    parts.extend(_bytes_field(15, _header_entry(key, value)) for key, value in headers.items())
    parts.append(_varint_field(18, 2))
    return b"".join(parts)


def _looks_like_ticket(value: str) -> bool:
    return bool(
        value
        and ":" not in value
        and len(value) >= 40
        and re.fullmatch(r"[A-Za-z0-9_\-+/=\.]+", value)
    )


def _extract_uid_ticket_pairs(raw_protobuf_text: str) -> dict[str, str]:
    """从 protoc --decode_raw 的输出中提取安全 UID 和动态 ticket。"""
    pairs: dict[str, str] = {}
    candidate_ticket: str | None = None
    remaining_lines = 0
    previous_non_empty = ""

    for raw_line in raw_protobuf_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        ticket_match = re.match(r'^4:\s*"([^"]+)"$', line)
        if ticket_match:
            value = ticket_match.group(1).strip()
            if _looks_like_ticket(value) and re.match(r"^3:\s*\d+$", previous_non_empty):
                candidate_ticket = value
                remaining_lines = 220
            else:
                candidate_ticket = None
                remaining_lines = 0
        elif candidate_ticket and remaining_lines > 0:
            uid_match = re.match(r'^50:\s*"(AQ[^"]+)"$', line)
            if uid_match:
                pairs.setdefault(uid_match.group(1).strip(), candidate_ticket)
                candidate_ticket = None
                remaining_lines = 0
            else:
                remaining_lines -= 1
                if remaining_lines <= 0:
                    candidate_ticket = None
        previous_non_empty = line
    return pairs


def _fetch_security_uid_conversation_map(cookies: dict[str, str]) -> dict[str, str]:
    """把 ticket 响应中的安全 UID 映射为聊天消息中的会话 ID。"""
    headers = dict(_HTTP_HEADERS)
    csrf_token = cookies.get("x-secsdk-csrf-token")
    if csrf_token:
        headers["x-secsdk-csrf-token"] = csrf_token
    response = requests.get(
        "https://pigeon.jinritemai.com/chat/api/backstage/conversation/get_current_conversation_list",
        headers=headers,
        cookies=cookies,
        params={
            "biz_type": "4",
            "PIGEON_BIZ_TYPE": "2",
            "pageNo": "0",
            "pageSize": "200",
            "_pms": "1",
            "device_platform": "web",
            "FUSION": "true",
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json().get("data")
    if not isinstance(data, list):
        return {}

    mapping: dict[str, str] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        security_uid = item.get("securityPigeonUid")
        conversation_id = item.get("securityBizConversationId")
        if not security_uid or not conversation_id:
            for message in item.get("msgList") or []:
                body = message.get("messageBody") if isinstance(message, dict) else None
                ext = body.get("ext") if isinstance(body, dict) else None
                if not isinstance(ext, dict):
                    continue
                security_uid = security_uid or ext.get("security_src_user_id") or ext.get("security_pigeon_uid")
                conversation_id = conversation_id or ext.get("security_biz_conversation_id") or ext.get("security_conversation_id")
                if security_uid and conversation_id:
                    break
        if (
            isinstance(security_uid, str)
            and isinstance(conversation_id, str)
            and security_uid.startswith("AQ")
            and "::" in conversation_id
            and conversation_id.endswith(":pigeon")
        ):
            mapping[security_uid.strip()] = conversation_id.strip()
    return mapping


def _get_conversation_ticket(
    cookies: dict[str, str], token: str, pigeon_sign: str, app_id: str, conversation_id: str
) -> str:
    if not _PROTOC.is_file():
        raise BuyerMessageSenderError(f"缺少 ticket 解码器：{_PROTOC}")
    ticket_request = _build_ticket_request(token, pigeon_sign, app_id, cookies["PIGEON_CID"])
    response = requests.post(
        "https://fxg.jinritemai.com/pigeon_im/v2/message/get_by_user_init",
        params={"pigeon_source": "web", "PIGEON_BIZ_TYPE": "2"},
        headers={
            "accept": "application/x-protobuf",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/x-protobuf",
            "origin": "https://im.jinritemai.com",
            "referer": "https://im.jinritemai.com/",
            "user-agent": _HTTP_HEADERS["user-agent"],
        },
        cookies=cookies,
        data=ticket_request,
        timeout=30,
    )
    response.raise_for_status()
    if not response.content:
        raise BuyerMessageSenderError("未获取到动态 ticket")

    try:
        decoded = subprocess.run(
            [str(_PROTOC), "--decode_raw"],
            input=response.content,
            capture_output=True,
            timeout=20,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise BuyerMessageSenderError("动态 ticket 解码超时") from error
    if decoded.returncode != 0:
        raise BuyerMessageSenderError("动态 ticket 解码失败")

    uid_tickets = _extract_uid_ticket_pairs(decoded.stdout.decode("utf-8", errors="replace"))
    uid_conversations = _fetch_security_uid_conversation_map(cookies)
    for security_uid, ticket in uid_tickets.items():
        if uid_conversations.get(security_uid) == conversation_id:
            return ticket
    raise BuyerMessageSenderError("没有找到该买家当前会话的动态 ticket")


def _extract_buyer_conversation(buyer_message: Mapping[str, Any]) -> tuple[str, str, Any, Any]:
    """从监听器打印的原始 JSON 中取出发送文本必需的会话字段。"""
    try:
        message = buyer_message["body"]["has_new_message_notify"]["message"]
        ext = message["ext"]
        if ext.get("s:sender_biz_role") != "Buyer":
            raise BuyerMessageSenderError("buyer_message 不是买家消息")
        conversation_id = str(ext["security_biz_conversation_id"])
        uid, shop_id = conversation_id.split("::", 1)[0].split(":")
        return uid, shop_id, message["conversation_short_id"], message["sub_conversation_short_id"]
    except BuyerMessageSenderError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise BuyerMessageSenderError("buyer_message 缺少发送文本所需的会话字段") from error


def _build_text_message_request(
    uid: str, shop_id: str, conversation_short_id: Any, sub_conversation_short_id: Any, ticket: str, text: str
) -> dict[str, Any]:
    client_message_id = str(uuid.uuid4())
    conversation_id = f"{uid}:{shop_id}::2:1:pigeon"
    return {
        "body": {
            "send_message_body": {
                "conversation_id": "",
                "security_conversation_id": conversation_id,
                "conversation_short_id": conversation_short_id,
                "sub_conversation_short_id": sub_conversation_short_id,
                "conversation_type": 11,
                "content": text,
                "mentioned_users": [],
                "client_message_id": client_message_id,
                "ticket": ticket,
                "message_type": 1000,
                "ext": {
                    "type": "text",
                    "shop_id": shop_id,
                    "sender_role": "2",
                    "PIGEON_BIZ_TYPE": "2",
                    "src": "pc",
                    "srcType": "1",
                    "source": "pc-web",
                    "security_receiver_id": uid.split(":", 1)[0],
                    "hierarchical_dimension": _TEXT_DIMENSION,
                    "p:check_Send": str(uuid.uuid1()),
                    "track_info": json.dumps(
                        {"send_time": str(int(time.time() * 1000)), "_send_delta": "394", "_send_delta_2": "475"}
                    ),
                    "user_agent": _HTTP_HEADERS["user-agent"],
                    "sender_id": "",
                    "biz_ext": "{}",
                    "p:from_source": "web",
                    "s:mentioned_users": "",
                    "s:client_message_id": client_message_id,
                },
            }
        },
        "cmd": 100,
        "inboxType": 3,
        "seqId": 10001,
    }


def _connect_arguments() -> dict[str, Any]:
    """同时兼容旧版及 websockets 16+ 的请求头参数名。"""
    parameters = inspect.signature(websockets.connect).parameters
    if "additional_headers" in parameters:
        return {
            "additional_headers": _WS_HEADERS,
            "user_agent_header": None,
        }
    return {"extra_headers": _WS_HEADERS}


async def _send_text(
    cookies: dict[str, str], buyer_message: Mapping[str, Any], text: str
) -> None:
    uid, shop_id, conversation_short_id, sub_conversation_short_id = _extract_buyer_conversation(buyer_message)
    conversation_id = f"{uid}:{shop_id}::2:1:pigeon"
    token, app_id, pigeon_sign, fp_id, app_key = _get_link_info(cookies)
    ticket = _get_conversation_ticket(cookies, token, pigeon_sign, app_id, conversation_id)
    request_data = _build_text_message_request(
        uid,
        shop_id,
        conversation_short_id,
        sub_conversation_short_id,
        ticket,
        text,
    )
    frame = _encode_send_frame(request_data, token, pigeon_sign, cookies["PIGEON_CID"], app_id)
    websocket_url = _build_websocket_url(token, app_id, pigeon_sign, fp_id, app_key)
    async with websockets.connect(
        websocket_url,
        ping_interval=20,
        ping_timeout=60,
        close_timeout=5,
        open_timeout=30,
        **_connect_arguments(),
    ) as websocket:
        await websocket.send(frame)


def send_text_message(
    cookie: str | Mapping[str, Any], buyer_message: Mapping[str, Any], text: str
) -> None:
    """向一条已监听到的买家消息所属会话发送纯文本。

    参数:
        cookie: 抖店客服页面导出的完整 Cookie。
        buyer_message: 监听函数打印或回调传入的那条完整买家 JSON。
        text: 需要发送的纯文本内容。

    函数仅发送这一次文本。它不执行自动回复、订单/商品查询、AI 调用或 Cookie 更新。
    成功返回只代表发送帧已交给已连接的 WebSocket；平台最终送达状态以抖店后台为准。
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text 必须是非空字符串")
    cookies = _parse_cookie(cookie)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("当前线程已有运行中的事件循环；请在普通 Python 线程中调用此函数。")
    asyncio.run(_send_text(cookies, buyer_message, text))


__all__ = ["BuyerMessageSenderError", "send_text_message"]


# 调用示例：buyer_message 必须是 buyer_ws_listener.py 打印或回调得到的完整 JSON 对象。
# cookie="s_v_web_id=verify_mvkqgb6n_7wFQymbv_8fbR_4vfq_B6AX_mCJjvrK0k7d8; PHPSESSID=64b38d4e4c06a3e83ddf6fe8b754d7e8; PHPSESSID_SS=64b38d4e4c06a3e83ddf6fe8b754d7e8; ecom_gray_shop_id=266072853; ecom_us_lt=e3d45b008756c54c3f2ae42c2d80383ff133c3c85e8402a0d74fcbb7f6de0ec6; ecom_us_lt_ss=e3d45b008756c54c3f2ae42c2d80383ff133c3c85e8402a0d74fcbb7f6de0ec6; gd_random=eyJtYXRjaCI6ZmFsc2UsInBlcmNlbnQiOjAuNjU2NDMyMjE3MTAzNDEzOH0=.r8P5H4QRuEIdStSBr/ql2s9mGBap5qQrqiQ1o7Wq20M=; gd_random=eyJtYXRjaCI6dHJ1ZSwicGVyY2VudCI6MC45MjgwNzk2NTQ1ODY1MjA1fQ==.8CnCO/9itbQ0BV6UjgvrGn+cWJtwV2hGWSdOM9/eJrQ=; gd_random=eyJtYXRjaCI6ZmFsc2UsInBlcmNlbnQiOjAuNzg1NjcwNDYxNjg3NTIzN30=.AtU/9etTvmtbnHD/AoMddxVlVXxsMSRixnJKOpCCIQw=; has_biz_token=false; is_staff_user=false; odin_tt=084d5e0d721a3e0ac0336a40de982e38a875321d646379db3aa84eac8b62ccce4ffd6d88f8291229eabb8793d43932586e1100c9dffbd472ccab82093d9dbdb1; passport_auth_status=14d562a3d9febffa5f599ae979b59854%2C; passport_auth_status_ss=14d562a3d9febffa5f599ae979b59854%2C; passport_csrf_token=d262aaa68594d267a65db1ee1ef55d0d; passport_csrf_token_default=d262aaa68594d267a65db1ee1ef55d0d; passport_mfa_token=Cjc8zCB3hbUHNAxVfY7gyGdLa9IvqncZMAeHGp2g%2ByRO%2BYoIK1zjv3%2BOj2PujX5UOLyMzv0YhXB8GkoKPAAAAAAAAAAAAABRDc6tseS3Pk39krKCUaWKZB0O8MT9cYHt1ZSJl%2Bjz0Z9mmcuPs5x%2FbYaUD8m2yO0aYRCs1p8OGPax0WwgAiIBAwGnvMk%3D; session_tlb_tag=sttt%7C17%7Ch3wueAeXFcoiyNwhGyuiTP_________kWfZ5uc8t1WGeHasXZkNcrAyiLIC_bRY9XzRymbVlE3I%3D; sessionid=877c2e78079715ca22c8dc211b2ba24c; sessionid_ss=877c2e78079715ca22c8dc211b2ba24c; sid_guard=877c2e78079715ca22c8dc211b2ba24c%7C1792746187%7C5184002%7CTue%2C+22-Dec-2026+09%3A03%3A09+GMT; sid_tt=877c2e78079715ca22c8dc211b2ba24c; sid_ucp_v1=1.0.0-KGViM2I4MWFjOGRkMzJlMTIzOTczZWVlYjFlZTExZjRjMmVjNTlkZjkKGQjA79Cwls3QAxDLxezWBhiwISAMOAJA8QcaAmxmIiA4NzdjMmU3ODA3OTcxNWNhMjJjOGRjMjExYjJiYTI0Yw; ssid_ucp_v1=1.0.0-KGViM2I4MWFjOGRkMzJlMTIzOTczZWVlYjFlZTExZjRjMmVjNTlkZjkKGQjA79Cwls3QAxDLxezWBhiwISAMOAJA8QcaAmxmIiA4NzdjMmU3ODA3OTcxNWNhMjJjOGRjMjExYjJiYTI0Yw; ttwid=1%7CqVKmH-fG7vSRsEUKDLT1xQQ-6-gn4hC5PGKp25FV6Ms%7C1792745618%7Cfb44aa1fc5506c0f67fa9d13d0e7a674f5c8d606fc23fa201c5ba50a90cad2a0; ucas_c0=CkEKBTEuMC4wEJqIgebI2cjtahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DOxezWBkjO-ajZBlCavL7M0J7902lYbxIUAFlCOuLHT37TnZeDSQg3YReqG6I; ucas_c0_ss=CkEKBTEuMC4wEJqIgebI2cjtahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DOxezWBkjO-ajZBlCavL7M0J7902lYbxIUAFlCOuLHT37TnZeDSQg3YReqG6I; uid_tt=304cef868209f27b4ac28c7faa394967; uid_tt_ss=304cef868209f27b4ac28c7faa394967; zsgw_business_data=%7B%22uuid%22%3A%227273b473-4589-47dc-8b7c-e361084efb83%22%2C%22platform%22%3A%22pc%22%2C%22source%22%3A%22seo.fxg.jinritemai.com%22%7D; PIGEON_CID=7613323028357684762; SHOP_ID=266072853"
# buyer_message = {
#     "body": {
#     "has_new_message_notify": {
#       "conversation_type": 11,
#       "notify_type": 1,
#       "message": {
#         "ext": {
#           "sender_app_id": "1128",
#           "s:add_ext": "{\"biz_ext\":\"{}\",\"point_info\":\"{\\\"shop_order_id\\\":6952773035962471795,\\\"sku_order_id\\\":6952773035962471795,\\\"product_id\\\":3809245018825294754}\"}",
#           "sender_os_type": "android",
#           "iid": "955939301662954",
#           "type": "text",
#           "s:direct_call_rpc": "true",
#           "version_code": "40.6.0",
#           "security_biz_conversation_id": "AQC_w0X3L8qy9M4sgyFU5rhjECX69Vv362a-WoFvwa_vPUvy-g4yTwIiv496xq-7oduS_0XiklyPUrpQ0_bs2sXc:266072853::2:1:pigeon",
#           "s:client_message_id": "19e8e811-74eb-4071-9863-e3c25b41ff3f",
#           "shark_order_id": "",
#           "avatar_uri": "https://p9-pigeon-sign.ecombdimg.com/aweme-avatar/tos-cn-i-0813_okeewAGnKENGshgeDAAG3AEoBBGSbphAS7I7B4~tplv-jxcbcipi3j-image-limit.image?lk3s=c879ea0d&x-expires=1797939476&x-signature=oy9GSjDDXJnAoa6SMR%2BoJMdIIus%3D",
#           "point_info": "{\"shop_order_id\":6952773035962471795,\"sku_order_id\":6952773035962471795,\"product_id\":3809245018825294754}",
#           "p:open_countdown": "true",
#           "flow_extra": "{\"direction\":1,\"msg_type\":1000,\"phase\":10,\"sponsor\":1,\"write_from\":\"callback\"}",
#           "message_logid": "021792755476643fdbddc03000f040800000000000000228db377",
#           "src": "dy",
#           "shop_tag": "",
#           "text_msg_sub_type": "default",
#           "platform": "0",
#           "source": "1",
#           "store_id": "",
#           "sender_app_version": "400601",
#           "uname": "神兔唯乐",
#           "s:base_scene": "default",
#           "s:msg_priority": "1",
#           "fromSource": "1",
#           "s:sender_biz_role": "Buyer",
#           "s:cur_sub_conv_version": "1792755476166451",
#           "track_info": "{\"message_client_id\":\"19e8e811-74eb-4071-9863-e3c25b41ff3f\",\"timestamp_offset\":\"1791529027435\",\"send_time\":\"1226449199\",\"paas_start_time\":\"1226449199\",\"paas_end_time\":\"1226449202\",\"duration_paas_create_sub_conv\":\"0\",\"send_server_time\":1226449205}",
#           "s:cur_sub_conv_status": "0",
#           "receiver_id": "266072853",
#           "a:smp_token_fetch": "0",
#           "channel": "huawei_1128_64",
#           "nickname": "神兔唯乐",
#           "displayType": "0",
#           "security_receiver_id": "266072853",
#           "s:need_bcp": "1",
#           "uaid": "1128",
#           "PIGEON_BIZ_TYPE": "2",
#           "sender_role": "1",
#           "store_name": "",
#           "eccs_tech_stack": "android_native",
#           "encode_shop_id": "BztpsYYD",
#           "shark_product_id": "3806612059991441467",
#           "b_temp_track_message_id": "1879840366366827",
#           "s:server_message_id": "1879840366366827",
#           "s:is_stranger": "false",
#           "user_agent": "",
#           "talk_id": "7699826113937294633",
#           "src_id": "2",
#           "srcId": "2",
#           "attention": "true",
#           "device_platform": "android",
#           "os_version": "31",
#           "host_app_id": "1128",
#           "shop_id": "266072853",
#           "biz_ext": "{}",
#           "s:biz_aid": "1383",
#           "did": "3730007436561096"
#         },
#         "property_list": {},
#         "user_profile": {},
#         "conversation_type": 11,
#         "server_message_id": {
#           "low": -117012445,
#           "high": 1792755476,
#           "unsigned": False
#         },
#         "index_in_conversation": {
#           "low": 0,
#           "high": 0,
#           "unsigned": False
#         },
#         "conversation_short_id": {
#           "low": -1509817082,
#           "high": 1772610766,
#           "unsigned": False
#         },
#         "message_type": 50002,
#         "content": "",
#         "create_time": {
#           "low": 1754114865,
#           "high": 417,
#           "unsigned": False
#         },
#         "version": {
#           "low": 1754114863,
#           "high": 417,
#           "unsigned": False
#         },
#         "status": 0,
#         "order_in_conversation": {
#           "low": 0,
#           "high": 0,
#           "unsigned": False
#         },
#         "sec_sender": "MS4wLjABAAAAQOxxT6H-9JZ6L8PAHuIL67EweKZsPjNYx8t2Jreay3EkLx6rd3R1BgfXwruAY0Kz",
#         "index_in_conversation_v2": {
#           "low": 0,
#           "high": 0,
#           "unsigned": False
#         },
#         "sub_conversation_short_id": {
#           "low": 562185513,
#           "high": 1792755470,
#           "unsigned": False
#         }
#       },
#       "previous_cursor": {
#         "low": 1533165269,
#         "high": 417408,
#         "unsigned": False
#       },
#       "next_cursor": {
#         "low": 1768555668,
#         "high": 417408,
#         "unsigned": False
#       },
#       "index_in_conversation": {
#         "low": 0,
#         "high": 0,
#         "unsigned": False
#       },
#       "index_in_conversation_v2": {
#         "low": 0,
#         "high": 0,
#         "unsigned": False
#       },
#       "cmd_message_index": {
#         "low": 2075,
#         "high": 0,
#         "unsigned": False
#       },
#       "trace": {
#         "metrics": {
#           "4": {
#             "low": 1768516762,
#             "high": 417408,
#             "unsigned": False
#           },
#           "5": {
#             "low": 1768533041,
#             "high": 417408,
#             "unsigned": False
#           },
#           "7": {
#             "low": 1768599636,
#             "high": 417408,
#             "unsigned": False
#           }
#         },
#         "path": 0
#       },
#       "sub_conversation_short_id": {
#         "low": 562185513,
#         "high": 1792755470,
#         "unsigned": False
#       }
#     }
#   },
# }
# send_text_message(cookie, buyer_message, "您好，已收到您的消息。")
