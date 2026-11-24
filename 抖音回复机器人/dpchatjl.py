# -*- coding: utf-8 -*-
import datetime
import time
import json
import requests
from urllib.parse import urlparse

# 允许作为 chatimg 的后缀
MEDIA_EXTS = {
    # 图片
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg",
    # 视频
    ".mp4", ".mov", ".avi", ".mkv", ".webm", ".flv", ".wmv", ".m3u8",
}


def is_media_url(url: str) -> bool:
    """判断 URL 的路径后缀是否为图片/视频（忽略 query/fragment）"""
    if not isinstance(url, str) or not url:
        return False
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return False
    return any(path.endswith(ext) for ext in MEDIA_EXTS)


def extract_media_url(message_body: dict) -> str:
    """从单条消息里提取第一个图片/视频 URL，找不到返回空串"""
    # 1) content 本身可能就是媒体 URL
    content = (message_body.get("content") or "").strip()
    if is_media_url(content):
        return content

    # 2) ext 里常见的媒体字段
    ext = message_body.get("ext") or {}
    for key in ("image_url", "video_url", "url", "file_url", "thumb_url", "origin_url"):
        val = ext.get(key)
        if isinstance(val, str) and is_media_url(val):
            return val
        # 有些字段是 JSON 字符串，里面含 url
        if isinstance(val, str) and val.startswith("{"):
            try:
                inner = json.loads(val)
                for k2 in ("url", "image_url", "video_url", "origin_url"):
                    v2 = inner.get(k2)
                    if isinstance(v2, str) and is_media_url(v2):
                        return v2
            except Exception:
                pass

    return ""


def get_today_timestamp():
    """
    获取当天00:00:00 ~ 23:59:59的毫秒级时间戳
    返回:
        tuple: (零点时间戳, 23:59:59时间戳)
    """
    today = datetime.date.today()
    zero_time = datetime.datetime.combine(today, datetime.time(0, 0, 0))
    end_time = datetime.datetime.combine(today, datetime.time(23, 59, 59))
    zero_timestamp = int(time.mktime(zero_time.timetuple())) * 1000
    end_timestamp = int(time.mktime(end_time.timetuple())) * 1000
    return zero_timestamp, end_timestamp


def parse_cookie_string(cookie_str: str) -> dict:
    """将标准Cookie字符串解析为字典"""
    cookie_dict = {}
    if not isinstance(cookie_str, str) or not cookie_str.strip():
        return cookie_dict

    cookie_pairs = [pair.strip() for pair in cookie_str.split(';') if pair.strip()]

    for pair in cookie_pairs:
        if '=' not in pair:
            cookie_dict[pair.strip()] = ""
            continue

        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()

        if value.lower() == 'null':
            value = None

        cookie_dict[key] = value

    return cookie_dict


def huoqudiyijuhua(cookiesyuan, user_id):
    """
    返回: (chatimg, chatjl, error, total_count)
        chatimg    : 聊天记录里出现的第一个图片/视频链接（后缀校验通过），否则 ""
        chatjl     : 聊天记录，形如 "卖家:xxx,\\r买家:xxx"
        error      : 异常信息，正常为 ""
        total_count: 来回数量，一个"买家→卖家"配对算 1
    """
    cookies_dict = parse_cookie_string(cookiesyuan)
    timeyou = get_today_timestamp()
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://im.jinritemai.com",
        "priority": "u=1, i",
        "referer": "https://im.jinritemai.com/",
        "sec-ch-ua": "\"Google Chrome\";v=\"143\", \"Chromium\";v=\"143\", \"Not A(Brand\";v=\"24\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "x-secsdk-csrf-token": "00010000000102ab1fde4e1a54e0b8fd728619e6c9d350cfd19f4a73ccb9f4725e900042b6b6188ac5160aa6e91d,efe51fdd1624f6e2dab4ed8aaf41f3b2"
    }
    url = "https://pigeon.jinritemai.com/backstage/conversation_search/message_fuzzy_search"
    params = {
        "biz_type": "4",
        "PIGEON_BIZ_TYPE": "2",
        "_pms": "1",
        "FUSION": "true",
        "verifyFp": "verify_mm4qebzj_YGFq5ZBE_gjeb_4GXF_ADER_W4BvigkNrnsi",
        "_v": "1.0.1.8643",
    }
    data = {
        "security_user_id": user_id,
        "keyword": "",
        "start_time": timeyou[0],
        "end_time": timeyou[1],
        "limit": 20,
        "message_search_type": 1
    }
    data = json.dumps(data, separators=(',', ':'))

    response = requests.post(url, headers=headers, cookies=cookies_dict,
                             params=params, data=data, timeout=30)
    response.raise_for_status()
    result = response.json()

    chats = result.get('data', {}).get('chats', []) or []
    if not chats:
        return "", "", "", 0

    chat_lines = []
    chatimg = ""
    total_count = 0
    pending_buyer = False  # 是否有一段买家消息等待卖家回复

    # API 按时间倒序，反转为正序
    for chat in reversed(chats):
        body = chat.get('message_body') or {}
        ext = body.get('ext') or {}
        content = (body.get('content') or '').strip()
        if not content or '接入' in content:
            continue

        role = ext.get('s:sender_biz_role', '')
        if role == 'Buyer':
            chat_lines.append(f'买家:{content}')
            pending_buyer = True  # 买家发起，等待卖家回复
        elif role == 'CurrentServer':
            chat_lines.append(f'卖家:{content}')
            if pending_buyer:  # 卖家回复，一来一回记 1 次
                total_count += 1
                pending_buyer = False

        # 取第一个通过后缀校验的图片/视频链接
        if not chatimg:
            media = extract_media_url(body)
            if media:
                chatimg = media

    chatjl = ',\r'.join(chat_lines)
    return chatimg, chatjl, "", total_count


