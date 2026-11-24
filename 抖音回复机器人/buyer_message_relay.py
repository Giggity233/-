"""买家消息中转：按会话拼接 8 秒消息，并在每个拼接批次中独立处理。"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from buyer_ws_listener import listen_buyer_messages
from buyer_ws_sender import send_text_message
from coze_api import cozeduihua
from loggerset import merchant_log
from pdzrg import zhuanrg


ReplyFunction = Callable[[str | Mapping[str, Any], str, dict[str, Any], str], str | None]
_NON_TEXT_TEMPLATE_NAMES = {"【商品】", "【订单】", "【卡片】", "【图片】", "【视频】"}
_MEDIA_TEXT_SEPARATOR = "》》》》"
_CARD_MESSAGE_LOG_DIR = Path(__file__).resolve().parent / "logs" / "card_messages"
_LOG_FILENAME = "自动回复对话"


def _template_name_from_buyerstr(buyerstr: str) -> str:
    """返回单一模板分类；任意普通文字优先归为【文字】。"""
    first_non_text_template: str | None = None
    lines = buyerstr.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line in _NON_TEXT_TEMPLATE_NAMES:
            first_non_text_template = first_non_text_template or line
            if (
                line in {"【图片】", "【视频】"}
                and index + 1 < len(lines)
                and lines[index + 1].startswith(("http://", "https://"))
            ):
                index += 2
                continue
            index += 1
            continue
        return "【文字】"
    return first_non_text_template or "【卡片】"


def _content_only_buyerstr(buyerstr: str) -> str:
    """移除卡片/媒体标记，只保留实际文字及可用的媒体链接。"""
    lines = buyerstr.splitlines()
    result: list[str] = []
    pending_separator = False
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if line in {"【图片】", "【视频】"}:
            if index + 1 < len(lines) and lines[index + 1].startswith(("http://", "https://")):
                if pending_separator and result:
                    result.append(_MEDIA_TEXT_SEPARATOR)
                result.append(lines[index + 1])
                pending_separator = False
                index += 2
                continue
            index += 1
            continue
        if line in {"【商品】", "【订单】", "【卡片】"}:
            index += 1
            continue
        if line == _MEDIA_TEXT_SEPARATOR:
            pending_separator = bool(result)
            index += 1
            continue
        if line:
            if pending_separator and result:
                result.append(_MEDIA_TEXT_SEPARATOR)
            result.append(lines[index])
            pending_separator = False
        index += 1
    return "\n".join(result) or "nothing"


def _save_card_message_log(parsed_msg: Mapping[str, Any], buyer_message: Mapping[str, Any]) -> Path | None:
    """保存未知卡片的解析结果，供后续确认其消息结构。"""
    try:
        _CARD_MESSAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_path = _CARD_MESSAGE_LOG_DIR / f"{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns()}.json"
        log_path.write_text(
            json.dumps(
                {
                    "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "template_name": "【卡片】",
                    "parsed_msg": parsed_msg,
                    "buyer_message": buyer_message,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return log_path
    except (OSError, TypeError, ValueError):
        return None


def _cookie_text(cookie: str | Mapping[str, Any]) -> str:
    if isinstance(cookie, str):
        return cookie
    return "; ".join(f"{key}={value}" for key, value in cookie.items() if value is not None)


def _coze_output(raw_response: str) -> str:
    """校验 Coze answer 为 {\"output\": \"...\"} 并取出 output。"""
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise ValueError("Coze 返回为空")
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as error:
        raise ValueError("Coze 返回不是 JSON") from error
    output = payload.get("output") if isinstance(payload, dict) else None
    if not isinstance(output, str) or not output.strip():
        raise ValueError("Coze JSON 缺少非空 output")
    return output.strip()


def _transfer_to_human(
    cookie: str | Mapping[str, Any],
    uid: str,
    human_cid: str,
    shop_name: str,
    reason: str,
) -> None:
    """执行并记录转人工；失败只记日志，不抛回中转线程。"""
    try:
        result = zhuanrg(cookie, uid, human_cid)
        merchant_log.success(
            f"转人工结果 | 原因={reason} | CID={human_cid} | 接口响应={result}",
            shop_name,
            _LOG_FILENAME,
        )
    except Exception as error:
        merchant_log.error(
            f"转人工失败 | 原因={reason} | CID={human_cid} | 错误={error}",
            shop_name,
            _LOG_FILENAME,
        )


def conversation_reply(
    cookie: str | Mapping[str, Any],
    nickname: str,
    buyer_message: dict[str, Any],
    buyerstr: str,
    *,
    workflow_id: str,
    human_cid: str | None,
    shop_name: str,
    collaborative_reply: bool = False,
) -> str | None:
    """调用 Coze；协同回复在需要转人工时静默，不发送任何消息。"""
    def no_reply(reason: str) -> None:
        if collaborative_reply:
            merchant_log.info(f"协同回复静默 | 原因={reason}", shop_name, _LOG_FILENAME)
            return
        if human_cid:
            _transfer_to_human(cookie, uid, human_cid, shop_name, reason)
        else:
            merchant_log.error(f"无法转人工 | 原因={reason} | 缺少人工 CID", shop_name, _LOG_FILENAME)

    try:
        message = buyer_message["body"]["has_new_message_notify"]["message"]
        ext = message["ext"]
        security_conversation_id = str(ext["security_biz_conversation_id"])
        uid = security_conversation_id.split("::", 1)[0].split(":", 1)[0].strip()
        talk_id = str(ext.get("talk_id") or ext.get("talkid") or "").strip()
    except (KeyError, TypeError, ValueError) as error:
        merchant_log.error(f"无法解析买家会话，无法调用 Coze：{error}", shop_name, _LOG_FILENAME)
        return None

    if not uid:
        merchant_log.error("买家会话 UID 为空，无法继续处理", shop_name, _LOG_FILENAME)
        return None
    if not talk_id:
        merchant_log.error("消息缺少 talk_id，无法调用 Coze", shop_name, _LOG_FILENAME)
        no_reply("缺少 talk_id")
        return None

    template_name = _template_name_from_buyerstr(buyerstr)
    coze_input = _content_only_buyerstr(buyerstr)
    try:
        raw_response = cozeduihua(
            {
                "input": coze_input,
                "uid": uid,
                "cookieyuan": _cookie_text(cookie),
                "talkid": talk_id,
                "template_name": template_name,
            },
            workflow_id,
        )
        merchant_log.info(f"Coze 返回 | 买家={nickname} | 内容={raw_response}", shop_name, _LOG_FILENAME)
        output = _coze_output(raw_response)
    except Exception as error:
        merchant_log.error(f"Coze 异常 | 买家={nickname} | 错误={error}", shop_name, _LOG_FILENAME)
        no_reply("Coze 调用或返回异常")
        return None

    if "转人工" in output:
        no_reply("Coze output 包含转人工")
        return None
    if "@@@@" not in output:
        no_reply("Coze output 未包含 @@@@")
        return None

    reply_text = output.split("@@@@", 1)[1].strip()
    if not reply_text:
        no_reply("@@@@ 后没有可发送文字")
        return None
    return reply_text


@dataclass
class _PendingBuyer:
    nickname: str
    latest_message_json: dict[str, Any]
    texts: list[str] = field(default_factory=list)
    timer: threading.Timer | None = None
    timer_id: int = 0


class BuyerMessageRelay:
    """仅在消息拼接期按会话暂存；每个到期批次创建一个独立处理线程。"""

    def __init__(
        self,
        cookie: str | Mapping[str, Any],
        reply_function: ReplyFunction,
        *,
        shop_name: str = "未知店铺",
        wait_seconds: float = 8,
    ) -> None:
        if wait_seconds <= 0:
            raise ValueError("wait_seconds 必须大于 0")
        self.cookie = cookie
        self.reply_function = reply_function
        self.shop_name = shop_name or "未知店铺"
        self.wait_seconds = wait_seconds
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingBuyer] = {}

    @staticmethod
    def _card_or_media_text(
        message: Mapping[str, Any], ext: Mapping[str, Any], *, is_first_buyer_message: bool
    ) -> str | None:
        content = message.get("content")
        text = content.strip() if isinstance(content, str) else ""
        message_type = message.get("message_type")
        ext_type = str(ext.get("type") or "").lower()
        if ext_type in {"file_image", "image"} or text in {"[图片]", "【图片】", "图片"}:
            image_url = ext.get("imageUrl")
            if not is_first_buyer_message and isinstance(image_url, str) and image_url.strip():
                return f"【图片】\n{image_url.strip()}"
            return "【图片】"
        if ext_type in {"file_video", "video"} or text in {"[视频]", "【视频】", "视频"}:
            video_url = next(
                (
                    str(ext[key]).strip()
                    for key in ("videoUrl", "video_url", "videoURL")
                    if isinstance(ext.get(key), str) and ext[key].strip()
                ),
                "",
            )
            if not is_first_buyer_message and video_url:
                return f"【视频】\n{video_url}"
            return "【视频】"

        card_hint = " ".join(
            str(ext.get(key) or "") for key in ("customer_hint", "hint_content", "card_header", "type")
        ).lower()
        if message_type == 50002 or "订单" in card_hint or "order" in card_hint:
            if "订单" in card_hint or "order" in card_hint or ext.get("shark_order_id"):
                return "【订单】"
            if "商品" in card_hint or "goods" in card_hint or ext.get("goods_id"):
                return "【商品】"
            return "【卡片】"
        if "商品" in card_hint or "goods" in card_hint or ext.get("goods_id"):
            return "【商品】"
        if ext_type == "template_card":
            return "【卡片】"
        if text:
            return text
        return str(message_type) if message_type is not None else None

    @staticmethod
    def _extract_text_message(message_json: Mapping[str, Any]) -> tuple[str, str, str] | None:
        try:
            message = message_json["body"]["has_new_message_notify"]["message"]
            ext = message["ext"]
            if ext.get("s:sender_biz_role") != "Buyer":
                return None
            content = message.get("content")
            if isinstance(content, str) and ("接入" in content or "平台温馨提示" in content):
                return None
            text = BuyerMessageRelay._card_or_media_text(
                message, ext, is_first_buyer_message=bool(message_json.get("_is_first_buyer_message"))
            )
            raw_buyer_key = (
                ext.get("security_biz_conversation_id")
                or ext.get("security_pigeon_uid")
                or message.get("sec_sender")
            )
            buyer_key = str(raw_buyer_key or "").strip()
            if text is None or not buyer_key:
                return None
            nickname = str(ext.get("nickname") or ext.get("uname") or "未知买家").strip()
            return buyer_key, nickname or "未知买家", text.strip()
        except (KeyError, TypeError):
            return None

    def receive_buyer_message(self, message_json: dict[str, Any]) -> None:
        """收集同一会话的消息；从第一句起固定等待 8 秒后生成一个处理批次。"""
        extracted = self._extract_text_message(message_json)
        if extracted is None:
            return
        conversation_key, nickname, text = extracted
        with self._lock:
            pending = self._pending.get(conversation_key)
            if pending is None:
                pending = _PendingBuyer(nickname=nickname, latest_message_json=message_json)
                self._pending[conversation_key] = pending
                pending.timer_id += 1
                pending.timer = threading.Timer(
                    self.wait_seconds, self._flush_batch, args=(conversation_key, pending.timer_id)
                )
                pending.timer.daemon = True
                pending.timer.start()
            else:
                pending.nickname = nickname
                pending.latest_message_json = message_json
            pending.texts.append(text)

    @staticmethod
    def _deduplicate_special_messages(buyerstr: str) -> str:
        lines = buyerstr.splitlines()
        result: list[str] = []
        seen: set[str] = set()
        index = 0
        previous_kind: str | None = None

        def append_group(kind: str, group: list[str]) -> None:
            nonlocal previous_kind
            if {previous_kind, kind} == {"media", "text"}:
                result.append(_MEDIA_TEXT_SEPARATOR)
            result.extend(group)
            previous_kind = kind

        while index < len(lines):
            line = lines[index]
            if line in {"【商品】", "【订单】", "【卡片】"}:
                key = f"card:{line}"
                if key not in seen:
                    seen.add(key)
                    append_group("card", [line])
            elif line in {"【图片】", "【视频】"}:
                url = ""
                if index + 1 < len(lines) and lines[index + 1].startswith(("http://", "https://")):
                    url = lines[index + 1]
                    index += 1
                key = f"media:{line}:{url or line}"
                if key not in seen:
                    seen.add(key)
                    append_group("media", [line, url] if url else [line])
            else:
                append_group("text", [line])
            index += 1
        return "\n".join(result)

    def _flush_batch(self, conversation_key: str, timer_id: int) -> None:
        with self._lock:
            pending = self._pending.get(conversation_key)
            if pending is None or pending.timer_id != timer_id:
                return
            self._pending.pop(conversation_key, None)
        buyerstr = self._deduplicate_special_messages("\n".join(text for text in pending.texts if text != "50002"))
        worker = threading.Thread(
            target=self._process_batch,
            args=(pending, buyerstr),
            name=f"reply-{conversation_key[-12:]}",
            daemon=True,
        )
        worker.start()

    def _process_batch(self, pending: _PendingBuyer, buyerstr: str) -> None:
        merchant_log.info(
            f"接到对话 | 买家={pending.nickname} | 8秒拼接内容={buyerstr}",
            self.shop_name,
            _LOG_FILENAME,
        )
        try:
            reply_text = self.reply_function(
                self.cookie, pending.nickname, pending.latest_message_json, buyerstr
            )
        except Exception as error:
            merchant_log.error(f"会话处理失败 | 买家={pending.nickname} | 错误={error}", self.shop_name, _LOG_FILENAME)
            return
        if reply_text is None or not str(reply_text).strip():
            return
        try:
            send_text_message(self.cookie, pending.latest_message_json, str(reply_text).strip())
            merchant_log.success(
                f"发送结果 | 买家={pending.nickname} | 发送内容={str(reply_text).strip()} | 已提交 WebSocket",
                self.shop_name,
                _LOG_FILENAME,
            )
        except Exception as error:
            merchant_log.error(
                f"发送失败 | 买家={pending.nickname} | 发送内容={str(reply_text).strip()} | 错误={error}",
                self.shop_name,
                _LOG_FILENAME,
            )


def run_reply_relay(
    cookie: str | Mapping[str, Any],
    reply_function: ReplyFunction,
    *,
    shop_name: str = "未知店铺",
    wait_seconds: float = 8,
    stop_event: threading.Event | None = None,
) -> None:
    """启动一个店铺监听器；停止事件触发后安全退出。"""
    relay = BuyerMessageRelay(
        cookie, reply_function, shop_name=shop_name, wait_seconds=wait_seconds
    )
    listen_buyer_messages(
        cookie,
        on_buyer_message=relay.receive_buyer_message,
        print_messages=False,
        stop_event=stop_event,
    )


__all__ = ["BuyerMessageRelay", "conversation_reply", "run_reply_relay"]
