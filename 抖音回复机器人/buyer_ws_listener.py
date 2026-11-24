"""仅监听并打印抖店买家消息的 WebSocket 工具。"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import inspect
import json
import subprocess
import time
from collections.abc import Callable, Mapping
from datetime import datetime, time as datetime_time
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
import websockets


_BASE_DIR = Path(__file__).resolve().parent
_DECODER_SCRIPT = _BASE_DIR / "js" / "decode_ws_message.js"
_UNDECODABLE_FRAME_LOG_DIR = _BASE_DIR / "logs" / "undecodable_frames"
_MESSAGE_SEARCH_URL = "https://pigeon.jinritemai.com/backstage/conversation_search/message_fuzzy_search"
_FIRST_MESSAGE_WS_WAIT_SECONDS = 2
_DEVICE_ID = "1469396562216643"
_ACCESS_KEY_SALT = "f8a69f1719916z"

_HTTP_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "origin": "https://im.jinritemai.com",
    "referer": "https://im.jinritemai.com/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    ),
}
_WS_HEADERS = {
    "Origin": "https://im.jinritemai.com",
    "User-Agent": _HTTP_HEADERS["user-agent"],
    "Sec-WebSocket-Protocol": "binary, base64",
}


class BuyerMessageListenerError(RuntimeError):
    """Cookie、连接参数或 Protobuf 解码不符合要求时抛出。"""


def _parse_cookie(cookie: str | Mapping[str, Any]) -> dict[str, str]:
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
            if key.strip():
                result[key.strip()] = value.strip()
    else:
        raise TypeError("cookie 必须是完整的 Cookie 字符串或 dict")

    missing = [key for key in ("PIGEON_CID", "SHOP_ID") if not result.get(key)]
    if missing:
        raise BuyerMessageListenerError(
            "Cookie 缺少 " + ", ".join(missing) + "。请从抖店客服页面导出完整 Cookie。"
        )
    return result


def _get_link_info(cookies: dict[str, str]) -> tuple[str, str, str, str, str]:
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
        raise BuyerMessageListenerError("Cookie 无效、已过期，或获取 WebSocket 连接参数失败") from error


def _build_websocket_url(token: str, app_id: str, pigeon_sign: str, fp_id: str, app_key: str) -> str:
    access_key = hashlib.md5(f"{fp_id}{app_key}{_DEVICE_ID}{_ACCESS_KEY_SALT}".encode("utf-8")).hexdigest()
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


def _decode_frame(raw_frame: bytes) -> dict[str, Any] | None:
    if not _DECODER_SCRIPT.is_file():
        raise BuyerMessageListenerError(f"缺少解码器文件：{_DECODER_SCRIPT}")
    try:
        completed = subprocess.run(
            ["node", str(_DECODER_SCRIPT)],
            input=json.dumps({"frame": base64.b64encode(raw_frame).decode("ascii")}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=15,
            check=False,
        )
    except FileNotFoundError as error:
        raise BuyerMessageListenerError("未找到 Node.js。请安装 Node.js 后执行 npm install。") from error
    except subprocess.TimeoutExpired as error:
        raise BuyerMessageListenerError("WebSocket 帧解码超时") from error
    if completed.returncode != 0:
        raise BuyerMessageListenerError(f"WebSocket 帧解码失败：{completed.stderr.strip() or '未知错误'}")
    try:
        decoded = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise BuyerMessageListenerError("解码器没有返回有效 JSON") from error
    return decoded if isinstance(decoded, dict) else None


def _save_undecodable_frame(raw_frame: bytes, error: Exception) -> Path | None:
    """保存无法解码的原始帧，供后续排查协议问题。"""
    try:
        _UNDECODABLE_FRAME_LOG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        log_path = _UNDECODABLE_FRAME_LOG_DIR / f"{timestamp}_{time.time_ns()}.json"
        log_path.write_text(
            json.dumps(
                {
                    "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "error": str(error),
                    "frame_length": len(raw_frame),
                    "frame_base64": base64.b64encode(raw_frame).decode("ascii"),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return log_path
    except OSError:
        return None


def _is_buyer_message(decoded: Mapping[str, Any]) -> bool:
    try:
        message = decoded["body"]["has_new_message_notify"]["message"]
        return message["ext"].get("s:sender_biz_role") == "Buyer"
    except (KeyError, TypeError):
        return False


def _is_ignored_platform_message(content: Any) -> bool:
    return isinstance(content, str) and ("接入" in content or "平台温馨提示" in content)


def _attention_notification_info(decoded: Mapping[str, Any]) -> tuple[str, str] | None:
    """从接入提醒 JSON 中提取买家 ID 和会话键。"""
    data = decoded.get("data")
    if not isinstance(data, Mapping) or not data.get("attention_content"):
        return None
    conversation_key = data.get("security_biz_conversation_id")
    user_id = data.get("customer_id")
    if isinstance(conversation_key, str):
        try:
            user_id = conversation_key.split("::", 1)[0].split(":", 1)[0]
        except IndexError:
            pass
    conversation_key = conversation_key or user_id
    if user_id is None or conversation_key is None:
        return None
    return str(user_id), str(conversation_key)


def _buyer_message_info(decoded: Mapping[str, Any]) -> tuple[str, str, bool] | None:
    """返回买家 ID、会话键及是否为实际文本，接入事件不视为实际文本。"""
    try:
        message = decoded["body"]["has_new_message_notify"]["message"]
        ext = message["ext"]
        if ext.get("s:sender_biz_role") != "Buyer":
            return None
        conversation_key = str(ext["security_biz_conversation_id"])
        user_id = conversation_key.split("::", 1)[0].split(":", 1)[0]
        content = message.get("content")
        message_type = message.get("message_type")
        is_actual_text = (
            (isinstance(content, str) and bool(content.strip()) or message_type is not None)
            and not _is_ignored_platform_message(content)
        )
        return user_id, conversation_key, is_actual_text
    except (KeyError, TypeError, ValueError):
        return None


def _first_buyer_message_from_search(search_response: Mapping[str, Any]) -> dict[str, Any] | None:
    """从会话历史搜索结果中取第一条有效买家消息，并转为监听器使用的格式。"""
    try:
        chats = search_response["data"]["chats"]
    except (KeyError, TypeError):
        return None
    if not isinstance(chats, list):
        return None
    for chat in chats:
        if not isinstance(chat, Mapping):
            continue
        message = chat.get("message_body")
        if not isinstance(message, dict):
            continue
        ext = message.get("ext")
        content = message.get("content")
        message_type = message.get("message_type")
        if (
            not isinstance(ext, Mapping)
            or ext.get("s:sender_biz_role") != "Buyer"
            or (not isinstance(content, str) or not content.strip()) and message_type is None
            or _is_ignored_platform_message(content)
        ):
            continue
        return {"body": {"has_new_message_notify": {"message": message}}}
    return None


def _fetch_first_buyer_message(cookies: dict[str, str], user_id: str) -> dict[str, Any] | None:
    """通过会话历史接口补取接入时未随 WebSocket 推送的第一条买家消息。"""
    now = datetime.now()
    start_time = int(datetime.combine(now.date(), datetime_time.min).timestamp() * 1000)
    end_time = int(datetime.combine(now.date(), datetime_time.max).timestamp() * 1000)
    try:
        response = requests.post(
            _MESSAGE_SEARCH_URL,
            headers={**_HTTP_HEADERS, "content-type": "application/json;charset=UTF-8"},
            cookies=cookies,
            params={"biz_type": "4", "PIGEON_BIZ_TYPE": "2", "_pms": "1", "FUSION": "true"},
            data=json.dumps(
                {
                    "user_id": user_id,
                    "keyword": "",
                    "start_time": start_time,
                    "end_time": end_time,
                    "limit": 20,
                    "message_search_type": 1,
                },
                separators=(",", ":"),
            ),
            timeout=30,
        )
        response.raise_for_status()
        search_response = response.json()
    except (requests.RequestException, ValueError) as error:
        print(f"补取接入前第一条消息失败，买家={user_id}：{error}")
        return None
    if not isinstance(search_response, Mapping):
        return None
    return _first_buyer_message_from_search(search_response)


def _connect_arguments() -> dict[str, Any]:
    if "additional_headers" in inspect.signature(websockets.connect).parameters:
        return {"additional_headers": _WS_HEADERS, "user_agent_header": None}
    return {"extra_headers": _WS_HEADERS}


async def _listen(
    cookies: dict[str, str],
    on_buyer_message: Callable[[dict[str, Any]], None] | None,
    print_messages: bool,
    reconnect_delay: float,
    stop_event: Any | None,
) -> None:
    websocket_text_conversations: set[str] = set()
    delivered_buyer_conversations: set[str] = set()
    recovered_attention_conversations: set[str] = set()
    pending_attention_tasks: dict[str, asyncio.Task[None]] = {}

    async def dispatch_buyer_message(message: dict[str, Any], *, is_first_buyer_message: bool) -> None:
        message = {**message, "_is_first_buyer_message": is_first_buyer_message}
        if print_messages:
            print(json.dumps(message, ensure_ascii=False, indent=2))
        if on_buyer_message is not None:
            await asyncio.to_thread(on_buyer_message, message)

    async def recover_first_message_if_missing(user_id: str, conversation_key: str) -> None:
        try:
            await asyncio.sleep(_FIRST_MESSAGE_WS_WAIT_SECONDS)
            if conversation_key in websocket_text_conversations:
                return
            recovered_message = await asyncio.to_thread(_fetch_first_buyer_message, cookies, user_id)
            if recovered_message is None or conversation_key in websocket_text_conversations:
                return
            recovered_attention_conversations.add(conversation_key)
            print(f"已通过会话历史补取接入前第一条消息，买家={user_id}")
            is_first_buyer_message = conversation_key not in delivered_buyer_conversations
            delivered_buyer_conversations.add(conversation_key)
            await dispatch_buyer_message(recovered_message, is_first_buyer_message=is_first_buyer_message)
        except Exception as error:
            print(f"补取接入前第一条消息失败，买家={user_id}：{error}")
        finally:
            pending_attention_tasks.pop(conversation_key, None)

    def schedule_first_message_recovery(user_id: str, conversation_key: str) -> None:
        if (
            on_buyer_message is None
            or conversation_key in websocket_text_conversations
            or conversation_key in recovered_attention_conversations
            or conversation_key in pending_attention_tasks
        ):
            return
        pending_attention_tasks[conversation_key] = asyncio.create_task(
            recover_first_message_if_missing(user_id, conversation_key)
        )

    while stop_event is None or not stop_event.is_set():
        try:
            token, app_id, pigeon_sign, fp_id, app_key = _get_link_info(cookies)
            websocket_url = _build_websocket_url(token, app_id, pigeon_sign, fp_id, app_key)
            async with websockets.connect(
                websocket_url,
                ping_interval=20,
                ping_timeout=60,
                close_timeout=5,
                open_timeout=30,
                **_connect_arguments(),
            ) as websocket:
                print("WebSocket 已连接，正在监听买家消息。按 Ctrl+C 可停止。")
                while stop_event is None or not stop_event.is_set():
                    try:
                        raw_message = await asyncio.wait_for(websocket.recv(), timeout=1)
                    except TimeoutError:
                        continue
                    if isinstance(raw_message, str):
                        continue
                    raw_frame = bytes(raw_message)
                    try:
                        decoded = _decode_frame(raw_frame)
                    except BuyerMessageListenerError as error:
                        log_path = _save_undecodable_frame(raw_frame, error)
                        if log_path is not None:
                            print(f"无法解码的原始帧已保存：{log_path}")
                        raise
                    if decoded is None:
                        continue
                    if _is_buyer_message(decoded):
                        buyer_info = _buyer_message_info(decoded)
                        if buyer_info is None:
                            continue
                        user_id, conversation_key, is_actual_text = buyer_info
                        if not is_actual_text:
                            schedule_first_message_recovery(user_id, conversation_key)
                            continue
                        websocket_text_conversations.add(conversation_key)
                    else:
                        attention_info = _attention_notification_info(decoded)
                        if attention_info is None:
                            continue
                        user_id, conversation_key = attention_info
                        schedule_first_message_recovery(user_id, conversation_key)
                        continue
                    is_first_buyer_message = conversation_key not in delivered_buyer_conversations
                    delivered_buyer_conversations.add(conversation_key)
                    await dispatch_buyer_message(decoded, is_first_buyer_message=is_first_buyer_message)
        except asyncio.CancelledError:
            raise
        except BuyerMessageListenerError as error:
            print(f"监听错误：{error}")
        except Exception as error:
            print(f"WebSocket 断开或连接失败：{error}")

        if stop_event is not None and stop_event.is_set():
            break
        print(f"{reconnect_delay:g} 秒后重连；如果持续失败，请重新导出 Cookie。")
        await asyncio.sleep(reconnect_delay)


def listen_buyer_messages(
    cookie: str | Mapping[str, Any],
    on_buyer_message: Callable[[dict[str, Any]], None] | None = None,
    *,
    print_messages: bool = False,
    reconnect_delay: float = 5,
    stop_event: Any | None = None,
) -> None:
    """监听买家消息；print_messages=True 时才打印完整原始 JSON。"""
    if reconnect_delay < 0:
        raise ValueError("reconnect_delay 不能小于 0")
    cookies = _parse_cookie(cookie)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError("当前线程已有运行中的事件循环；请在普通 Python 线程中调用此函数。")
    try:
        asyncio.run(_listen(cookies, on_buyer_message, print_messages, reconnect_delay, stop_event))
    except KeyboardInterrupt:
        print("已停止监听买家消息。")


__all__ = ["BuyerMessageListenerError", "listen_buyer_messages"]


# 调用示例：把完整 Cookie 粘贴到本地变量后运行此文件或复制到你的业务代码中。
# cookie = "PIGEON_CID=...; SHOP_ID=...; 其余完整 Cookie..."
# listen_buyer_messages(cookie)

# 如果要把买家消息交给别的逻辑处理，可使用回调：
# def handle_buyer_message(buyer_message: dict) -> None:
#     print(buyer_message["body"]["has_new_message_notify"]["message"]["content"])
#
# cookie="s_v_web_id=verify_mvkqgb6n_7wFQymbv_8fbR_4vfq_B6AX_mCJjvrK0k7d8; PHPSESSID=64b38d4e4c06a3e83ddf6fe8b754d7e8; PHPSESSID_SS=64b38d4e4c06a3e83ddf6fe8b754d7e8; ecom_gray_shop_id=266072853; ecom_us_lt=e3d45b008756c54c3f2ae42c2d80383ff133c3c85e8402a0d74fcbb7f6de0ec6; ecom_us_lt_ss=e3d45b008756c54c3f2ae42c2d80383ff133c3c85e8402a0d74fcbb7f6de0ec6; gd_random=eyJtYXRjaCI6ZmFsc2UsInBlcmNlbnQiOjAuNjU2NDMyMjE3MTAzNDEzOH0=.r8P5H4QRuEIdStSBr/ql2s9mGBap5qQrqiQ1o7Wq20M=; gd_random=eyJtYXRjaCI6dHJ1ZSwicGVyY2VudCI6MC45MjgwNzk2NTQ1ODY1MjA1fQ==.8CnCO/9itbQ0BV6UjgvrGn+cWJtwV2hGWSdOM9/eJrQ=; gd_random=eyJtYXRjaCI6ZmFsc2UsInBlcmNlbnQiOjAuNzg1NjcwNDYxNjg3NTIzN30=.AtU/9etTvmtbnHD/AoMddxVlVXxsMSRixnJKOpCCIQw=; has_biz_token=false; is_staff_user=false; odin_tt=084d5e0d721a3e0ac0336a40de982e38a875321d646379db3aa84eac8b62ccce4ffd6d88f8291229eabb8793d43932586e1100c9dffbd472ccab82093d9dbdb1; passport_auth_status=14d562a3d9febffa5f599ae979b59854%2C; passport_auth_status_ss=14d562a3d9febffa5f599ae979b59854%2C; passport_csrf_token=d262aaa68594d267a65db1ee1ef55d0d; passport_csrf_token_default=d262aaa68594d267a65db1ee1ef55d0d; passport_mfa_token=Cjc8zCB3hbUHNAxVfY7gyGdLa9IvqncZMAeHGp2g%2ByRO%2BYoIK1zjv3%2BOj2PujX5UOLyMzv0YhXB8GkoKPAAAAAAAAAAAAABRDc6tseS3Pk39krKCUaWKZB0O8MT9cYHt1ZSJl%2Bjz0Z9mmcuPs5x%2FbYaUD8m2yO0aYRCs1p8OGPax0WwgAiIBAwGnvMk%3D; session_tlb_tag=sttt%7C17%7Ch3wueAeXFcoiyNwhGyuiTP_________kWfZ5uc8t1WGeHasXZkNcrAyiLIC_bRY9XzRymbVlE3I%3D; sessionid=877c2e78079715ca22c8dc211b2ba24c; sessionid_ss=877c2e78079715ca22c8dc211b2ba24c; sid_guard=877c2e78079715ca22c8dc211b2ba24c%7C1792746187%7C5184002%7CTue%2C+22-Dec-2026+09%3A03%3A09+GMT; sid_tt=877c2e78079715ca22c8dc211b2ba24c; sid_ucp_v1=1.0.0-KGViM2I4MWFjOGRkMzJlMTIzOTczZWVlYjFlZTExZjRjMmVjNTlkZjkKGQjA79Cwls3QAxDLxezWBhiwISAMOAJA8QcaAmxmIiA4NzdjMmU3ODA3OTcxNWNhMjJjOGRjMjExYjJiYTI0Yw; ssid_ucp_v1=1.0.0-KGViM2I4MWFjOGRkMzJlMTIzOTczZWVlYjFlZTExZjRjMmVjNTlkZjkKGQjA79Cwls3QAxDLxezWBhiwISAMOAJA8QcaAmxmIiA4NzdjMmU3ODA3OTcxNWNhMjJjOGRjMjExYjJiYTI0Yw; ttwid=1%7CqVKmH-fG7vSRsEUKDLT1xQQ-6-gn4hC5PGKp25FV6Ms%7C1792745618%7Cfb44aa1fc5506c0f67fa9d13d0e7a674f5c8d606fc23fa201c5ba50a90cad2a0; ucas_c0=CkEKBTEuMC4wEJqIgebI2cjtahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DOxezWBkjO-ajZBlCavL7M0J7902lYbxIUAFlCOuLHT37TnZeDSQg3YReqG6I; ucas_c0_ss=CkEKBTEuMC4wEJqIgebI2cjtahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DOxezWBkjO-ajZBlCavL7M0J7902lYbxIUAFlCOuLHT37TnZeDSQg3YReqG6I; uid_tt=304cef868209f27b4ac28c7faa394967; uid_tt_ss=304cef868209f27b4ac28c7faa394967; zsgw_business_data=%7B%22uuid%22%3A%227273b473-4589-47dc-8b7c-e361084efb83%22%2C%22platform%22%3A%22pc%22%2C%22source%22%3A%22seo.fxg.jinritemai.com%22%7D; PIGEON_CID=7613323028357684762; SHOP_ID=266072853"
# if __name__ == "__main__":
#     listen_buyer_messages(cookie, on_buyer_message=handle_buyer_message)
