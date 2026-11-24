"""拼多多 Cookie 同步所需的中控与店铺信息接口。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests

DEFAULT_PROFILE_ROOT = Path(r"D:\aibot")
DEFAULT_API_CONFIG_FILE = DEFAULT_PROFILE_ROOT / "ipyuan.json"
DEFAULT_LOGIN_INFO_FILE = DEFAULT_PROFILE_ROOT / "user_login_info.json"
HTTP_TIMEOUT = 15

PDD_MERCHANT_INFO_URL = (
    "https://mms.pinduoduo.com/earth/api/merchant/queryMerchantInfoByMallId"
)
PDD_MERCHANT_INFO_HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "max-age=0",
    "content-type": "application/json",
    "origin": "https://mms.pinduoduo.com",
    "referer": "https://mms.pinduoduo.com/mallcenter/info/basic",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


class ConfigError(ValueError):
    """本地中控配置不可用。"""


class CookieExpiredError(RuntimeError):
    """浏览器中没有可用的拼多多会话。"""


@dataclass(frozen=True)
class ServerConfig:
    base_url: str
    interval: int
    thread: int


def load_server_config(path: str | Path = DEFAULT_API_CONFIG_FILE) -> ServerConfig:
    """读取 ``ipyuan.json`` 中的 ip、port、interval 和 thread。"""
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8-sig") as file:
            raw_config = json.load(file)
    except FileNotFoundError as exc:
        raise ConfigError(f"未找到中控配置文件：{config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"中控配置文件不是合法 JSON：{config_path}") from exc

    if not isinstance(raw_config, dict):
        raise ConfigError("中控配置必须是一个 JSON 对象")

    host = str(raw_config.get("ip") or "").strip()
    if not host:
        raise ConfigError("中控配置缺少 ip")
    try:
        port = int(raw_config["port"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError("中控配置中的 port 必须是 1-65535 的整数") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("中控配置中的 port 必须是 1-65535 的整数")

    try:
        interval = int(raw_config.get("interval", 600))
        thread = int(raw_config.get("thread", 3))
    except (TypeError, ValueError) as exc:
        raise ConfigError("中控配置中的 interval 和 thread 必须是正整数") from exc
    if interval <= 0 or thread <= 0:
        raise ConfigError("中控配置中的 interval 和 thread 必须是正整数")

    if host.startswith(("http://", "https://")):
        base_url = host.rstrip("/")
        host_part = base_url.rsplit("/", 1)[-1]
        if ":" not in host_part:
            base_url = f"{base_url}:{port}"
    else:
        base_url = f"http://{host}:{port}"
    return ServerConfig(base_url=base_url, interval=interval, thread=thread)


def _error_message(data: Any) -> str:
    if not isinstance(data, Mapping):
        return ""
    return " ".join(
        str(data.get(field) or "").strip()
        for field in ("error_msg", "errorMsg", "message", "msg")
        if data.get(field)
    )


def _is_expired_response(data: Any) -> bool:
    message = _error_message(data)
    return "会话已过期" in message or "登录已过期" in message


def get_pdd_shop_info(
    cookies: Mapping[str, str],
    cookie_text: str,
    *,
    request_session: Any = requests,
) -> dict[str, str]:
    """从拼多多接口取得保存 Cookie 所需的店铺资料。"""
    response = request_session.post(
        PDD_MERCHANT_INFO_URL,
        headers=PDD_MERCHANT_INFO_HEADERS,
        cookies=dict(cookies),
        json={},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if _is_expired_response(data):
        raise CookieExpiredError("拼多多返回：会话已过期")

    result = data.get("result") if isinstance(data, Mapping) else None
    if not isinstance(result, Mapping):
        message = _error_message(data) or "响应中没有 result"
        raise ValueError(f"获取拼多多店铺信息失败：{message}")

    shop_id = str(result.get("mallId") or result.get("mall_id") or "").strip()
    shop_name = str(result.get("mallName") or result.get("mall_name") or "").strip()
    if not shop_id or not shop_name:
        raise ValueError("拼多多店铺信息缺少 mallId 或 mallName")
    main_category = str(
        result.get("mallCategoryStr") or result.get("mall_category_str") or "notfind"
    ).strip() or "notfind"
    return {
        "platform": "pdd",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "main_category": main_category,
        "cookie": cookie_text,
    }


def upsert_cookie(
    base_url: str,
    shop_info: Mapping[str, str],
    *,
    request_session: Any = requests,
) -> Mapping[str, Any]:
    response = request_session.post(
        f"{base_url.rstrip('/')}/api/v1/cookies/upsert/",
        json=dict(shop_info),
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping) or not data.get("ok", False):
        message = data.get("message") if isinstance(data, Mapping) else "中控响应不是 JSON 对象"
        raise ValueError(message or "中控拒绝保存 Cookie")
    return data


def create_pending_task(
    base_url: str,
    shop_id: str,
    *,
    handling_item: str,
    time_type: str = "normal",
    request_session: Any = requests,
) -> Mapping[str, Any]:
    response = request_session.post(
        f"{base_url.rstrip('/')}/api/v1/pending-tasks/create/",
        json={
            "shop_id": str(shop_id),
            "platform": "pdd",
            "time_type": time_type,
            "handling_item": handling_item,
        },
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping) or not data.get("ok", False):
        message = data.get("message") if isinstance(data, Mapping) else "中控响应不是 JSON 对象"
        raise ValueError(message or "中控拒绝创建待处理事务")
    return data


def find_shop_record(
    path: str | Path, group_name: str, port: int
) -> dict[str, Any] | None:
    """从浏览器启动程序保存的记录中查找一个端口对应的店铺。"""
    try:
        with Path(path).open("r", encoding="utf-8-sig") as file:
            data = json.load(file)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    group_items = data.get(group_name, []) if isinstance(data, dict) else []
    if not isinstance(group_items, list):
        return None
    for item in group_items:
        if isinstance(item, dict) and str(item.get("port")) == str(port):
            return item
    return None


def report_auto_login_failure(
    base_url: str,
    port: int,
    group_name: str,
    *,
    login_info_file: str | Path,
) -> bool:
    """为 Cookie 无效且无法自动登录的店铺创建普通待处理事务。"""
    shop_record = find_shop_record(login_info_file, group_name, port)
    shop_id = str((shop_record or {}).get("shop_id") or "").strip()
    if not shop_id:
        print(f"端口 {port} 未返回 Cookie，且未找到对应 shop_id，无法创建待处理事务。")
        return False
    try:
        create_pending_task(
            base_url,
            shop_id,
            handling_item="自动登录失败",
            time_type="normal",
        )
    except (requests.RequestException, ValueError) as exc:
        print(f"端口 {port}：创建自动登录失败待处理事务失败：{exc}")
        return False
    print(f"端口 {port}：已为店铺 {shop_id} 创建普通待处理事务：自动登录失败。")
    return True
