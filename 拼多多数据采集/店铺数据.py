"""采集指定客户的拼多多店铺数据，并上传到联樽中控平台。

配置：
    1. 同级目录的“客户.json”仅列出需要采集的客户；
    2. 可用环境变量 LZ_BASE_URL 覆盖中控地址（默认 http://117.72.204.36:8000）。
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, time as datetime_time
from decimal import Decimal, InvalidOperation
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import execjs
import requests


BASE_DIR = Path.cwd()
BASE_URL = os.getenv("LZ_BASE_URL", "http://117.72.204.36:8000").rstrip("/")
CUSTOMERS_FILE = BASE_DIR / "客户.json"
LOG_FILE = BASE_DIR / "店铺数据.log"
PDD_PLATFORM = "pdd"
TIMEOUT = 20
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

COOKIE_EXPIRED_MARKERS = ("cookie", "登录", "登陆", "未登录", "会话", "session", "login")

with (BASE_DIR / "anti.js").open("r", encoding="utf-8") as file:
    ANTI_CODE = file.read()


def metric_error_reason(interface_name: str, message: str) -> str:
    """店铺分接口异常不展示技术报错；仅保留 Cookie 过期这个可操作状态。"""
    if interface_name != "getMallServeScoreV2":
        return message
    if any(marker in message.lower() for marker in COOKIE_EXPIRED_MARKERS):
        return "Cookie过期"
    return "无权限"


def get_today_context() -> dict[str, Any]:
    """返回接口文档要求的当天日期、当前小时和当天起止 Unix 时间戳。"""
    now = datetime.now(SHANGHAI_TZ)
    day_start = datetime.combine(now.date(), datetime_time.min, tzinfo=SHANGHAI_TZ)
    day_end = datetime.combine(now.date(), datetime_time.max, tzinfo=SHANGHAI_TZ)
    return {
        "report_date": now.strftime("%Y-%m-%d"),
        "time": now.hour,
        "start_timestamp": int(day_start.timestamp()),
        "end_timestamp": int(day_end.timestamp()),
    }


def load_customer_names() -> list[str]:
    """兼容客户.json中的常见结构，提取客户名称。"""
    if not CUSTOMERS_FILE.exists():
        raise FileNotFoundError(f"未找到客户列表文件：{CUSTOMERS_FILE}")

    with CUSTOMERS_FILE.open("r", encoding="utf-8-sig") as file:
        content = json.load(file)

    if isinstance(content, list):
        customers = content
    elif isinstance(content, dict):
        customers = content.get("客户列表", content.get("customers", content.get("客户", [])))
    else:
        raise ValueError("客户.json必须是客户列表，或包含“客户列表”的对象")

    if not isinstance(customers, list):
        raise ValueError("客户.json中的客户列表必须是数组")

    names: list[str] = []
    for customer in customers:
        if isinstance(customer, str):
            name = customer.strip()
        elif isinstance(customer, dict):
            name = str(customer.get("name", customer.get("客户名称", customer.get("客户", "")))).strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)

    if not names:
        raise ValueError("客户.json中的客户列表为空，已停止采集")
    return names


def cookie_string_to_dict(cookie_value: str | dict[str, str]) -> dict[str, str]:
    """将中控接口返回的完整 Cookie 字符串转换为 requests 可用的字典。"""
    if isinstance(cookie_value, dict):
        return {str(key): str(value) for key, value in cookie_value.items()}
    if not isinstance(cookie_value, str) or not cookie_value.strip():
        raise ValueError("店铺没有可用Cookie")

    parsed = SimpleCookie()
    parsed.load(cookie_value)
    cookies = {name: morsel.value for name, morsel in parsed.items()}
    if cookies:
        return cookies

    # 个别 Cookie 不符合 SimpleCookie 的格式时，保留原始键值对。
    pairs = (part.strip().split("=", 1) for part in cookie_value.split(";"))
    cookies = {key.strip(): value.strip() for key, value in pairs if key.strip() and value.strip()}
    if not cookies:
        raise ValueError("Cookie格式无法解析")
    return cookies


def pdd_headers(referer: str, *, content_type: bool = True) -> dict[str, str]:
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": execjs.compile(ANTI_CODE).call("get_anti", int(time.time())),
        "origin": "https://mms.pinduoduo.com",
        "referer": referer,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
        ),
    }
    if content_type:
        headers["content-type"] = "application/json"
    return headers


def pdd_request(
    *,
    interface_name: str,
    method: str,
    url: str,
    cookies: dict[str, str],
    referer: str,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """调用拼多多接口；接口或网络失败时返回可直接上传的具体原因。"""
    try:
        response = requests.request(
            method,
            url,
            headers=pdd_headers(referer, content_type=method != "GET"),
            cookies=cookies,
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
    except (requests.RequestException, ValueError, execjs.RuntimeError) as error:
        message = f"{interface_name}请求失败：{error}"
        logger.error(message, exc_info=True)
        return None, metric_error_reason(interface_name, message)

    if not isinstance(response_data, dict):
        message = f"{interface_name}返回格式错误：不是JSON对象"
        logger.error(message)
        return None, metric_error_reason(interface_name, message)

    error_message = response_data.get("errorMsg")
    if error_message is not None:
        message = f"{interface_name}：{error_message or '拼多多接口返回失败'}"
        logger.error(message)
        return None, metric_error_reason(interface_name, message)
    if response_data.get("success") is False:
        message = f"{interface_name}：拼多多接口返回失败"
        logger.error(message)
        return None, metric_error_reason(interface_name, message)
    return response_data, None


def result_value(result: dict[str, Any], key: str) -> Any:
    """字段缺失也作为可上传的明确状态，避免整店采集失败。"""
    if key not in result:
        message = f"拼多多接口返回缺少字段：{key}"
        logger.error(message)
        return message
    return result[key]


def get_home_page_overview(cookies: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    data, error = pdd_request(
        interface_name="homePageOverView",
        method="POST",
        url="https://mms.pinduoduo.com/sydney/api/mallCoreData/homePageOverView",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/home",
        payload={},
    )
    if error:
        return None, error
    return data.get("result", {}).get("rtDataOverView", {}), None


def get_mall_service_score(cookies: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    data, error = pdd_request(
        interface_name="getMallServeScoreV2",
        method="POST",
        url="https://mms.pinduoduo.com/sydney/api/mallService/getMallServeScoreV2",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/sycm/goods_quality/help",
        payload={},
    )
    if error:
        return None, error
    return data.get("result", {}), None


def get_after_sales_count(cookies: dict[str, str], context: dict[str, Any]) -> tuple[Any, str | None]:
    data, error = pdd_request(
        interface_name="afterSales/queryList",
        method="POST",
        url="https://mms.pinduoduo.com/mercury/mms/afterSales/queryList",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/aftersales/aftersale_list",
        payload={
            "pageSize": 10,
            "pageNumber": 1,
            "orderByCreatedAtDesc": True,
            "startCreatedTime": context["start_timestamp"],
            "endCreatedTime": context["end_timestamp"],
        },
    )
    if error:
        return None, error
    return result_value(data.get("result", {}), "total"), None


def get_pending_ticket_count(cookies: dict[str, str], context: dict[str, Any]) -> tuple[Any, str | None]:
    data, error = pdd_request(
        interface_name="todoList",
        method="POST",
        url="https://mms.pinduoduo.com/strickland/sop/mms/todoList",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/aftersales/work_order/list?msfrom=mms_sidenav",
        payload={
            "serviceStatus": [None],
            "problemType": [None],
            "createStartTime": context["start_timestamp"],
            "createEndTime": context["end_timestamp"],
            "pageNum": 1,
            "pageSize": 10,
        },
    )
    if error:
        return None, error
    return result_value(data.get("result", {}), "total"), None


def get_realtime_reply_data(cookies: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    data, error = pdd_request(
        interface_name="getCsRealTimeReplyData",
        method="GET",
        url="https://mms.pinduoduo.com/chats/getCsRealTimeReplyData",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/chat-merchant/",
    )
    if error:
        return None, error
    return data.get("result", {}), None


def get_yesterday_average_response(cookies: dict[str, str]) -> tuple[Any, str | None]:
    data, error = pdd_request(
        interface_name="csInquiryGroupData",
        method="GET",
        url="https://mms.pinduoduo.com/chats/latest/csInquiryGroupData",
        cookies=cookies,
        referer="https://mms.pinduoduo.com/chat-merchant/",
    )
    if error:
        return None, error
    return result_value(data.get("result", {}), "artificial_response_time"), None


def yuan_or_reason(value: Any, reason: str | None) -> Any:
    """金额由分转元；拼多多接口失败时上传失败原因。"""
    if reason:
        return reason
    if isinstance(value, (int, float)):
        return round(value / 100, 2)
    return value


def value_or_reason(value: Any, reason: str | None) -> Any:
    return reason if reason else value


def percentage_or_reason(value: Any, reason: str | None) -> Any:
    """拼多多 reply_rate 是 0~1 小数，中控展示需要 0~100 百分比。"""
    if reason:
        return reason
    try:
        return float(Decimal(str(value)) * 100)
    except (ValueError, TypeError, InvalidOperation):
        return value


def collect_store_metrics(cookies: dict[str, str], context: dict[str, Any]) -> dict[str, Any]:
    """按照接口文档的 store-metrics 字段名整理拼多多采集结果。"""
    overview, overview_error = get_home_page_overview(cookies)
    score, score_error = get_mall_service_score(cookies)
    after_sales, after_sales_error = get_after_sales_count(cookies, context)
    pending_tickets, pending_tickets_error = get_pending_ticket_count(cookies, context)
    realtime_reply, realtime_reply_error = get_realtime_reply_data(cookies)
    yesterday_response, yesterday_response_error = get_yesterday_average_response(cookies)

    overview = overview or {}
    score = score or {}
    realtime_reply = realtime_reply or {}
    return {
        # 以下字段均为接口文档 /api/v1/store-metrics/upsert/ 支持的字段。
        "today_order_count": value_or_reason(result_value(overview, "curPayOrdrCnt"), overview_error),
        "today_turnover": yuan_or_reason(result_value(overview, "curPayOrdrAmt"), overview_error),
        "today_ad_spend": yuan_or_reason(result_value(overview, "promotionSpend"), overview_error),
        "store_experience_score": value_or_reason(result_value(score, "cstmrServScore"), score_error),
        "service_experience_score": value_or_reason(result_value(score, "jcfwLmScore"), score_error),
        "pending_after_sales": value_or_reason(after_sales, after_sales_error),
        "pending_tickets": value_or_reason(pending_tickets, pending_tickets_error),
        "specialist_reply_count": value_or_reason(
            result_value(realtime_reply, "recv_user"), realtime_reply_error
        ),
        "specialist_three_minute_reply_rate": percentage_or_reason(
            result_value(realtime_reply, "reply_rate"), realtime_reply_error
        ),
        "specialist_yesterday_average_response_seconds": value_or_reason(
            yesterday_response, yesterday_response_error
        ),
    }


def get_customer_shops(customer_name: str | None) -> list[dict[str, Any]]:
    """获取指定客户的店铺；customer_name 为 None 时获取该平台全部店铺。"""
    params = {"platform": PDD_PLATFORM}
    if customer_name is not None:
        params["customer"] = customer_name
    response = requests.get(
        f"{BASE_URL}/api/v1/cookies/",
        params=params,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response_data = response.json()
    if not response_data.get("ok", False):
        raise RuntimeError(response_data.get("message", "中控接口未返回成功状态"))
    shops = response_data.get("data", [])
    if not isinstance(shops, list):
        raise RuntimeError("中控接口返回的店铺列表格式不正确")
    return shops


def upload_store_metrics(shop: dict[str, Any], metrics: dict[str, Any], context: dict[str, Any]) -> None:
    shop_id = shop.get("shop_id")
    if not shop_id:
        raise ValueError("中控返回的店铺缺少shop_id")

    payload = {
        "shop_id": shop_id,
        "platform": PDD_PLATFORM,
        "time": context["time"],
        "report_date": context["report_date"],
        **metrics,
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/store-metrics/upsert/",
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response_data = response.json()
    if not response_data.get("ok", False):
        raise RuntimeError(response_data.get("message", "店铺数据上传失败"))


def process_shop(customer_name: str, shop: dict[str, Any], context: dict[str, Any]) -> None:
    shop_name = shop.get("shop_name", "未命名店铺")
    shop_id = shop.get("shop_id", "未知shop_id")
    try:
        cookies = cookie_string_to_dict(shop.get("cookie", ""))
        metrics = collect_store_metrics(cookies, context)
        print(metrics)
        upload_store_metrics(shop, metrics, context)
        logger.info("上传成功 customer=%s shop=%s(%s)", customer_name, shop_name, shop_id)
        print(f"上传成功：{customer_name} / {shop_name} ({shop_id})")
    except Exception as error:  # 单店失败不可影响其余客户和店铺。
        logger.exception("处理失败 customer=%s shop=%s(%s)：%s", customer_name, shop_name, shop_id, error)
        print(f"处理失败：{customer_name} / {shop_name} ({shop_id})，原因：{error}")


def main() -> None:
    context = get_today_context()
    try:
        customers = load_customer_names()
    except (OSError, json.JSONDecodeError, ValueError) as error:
        logger.error("无法读取客户列表：%s", error)
        raise SystemExit(f"无法读取客户列表：{error}") from error

    collect_all = any(customer.strip().casefold() == "all" for customer in customers)
    customer_batches: list[str | None] = [None] if collect_all else customers
    collection_scope = "全部客户" if collect_all else f"客户数：{len(customers)}"
    print(f"采集日期：{context['report_date']}，小时：{context['time']}，{collection_scope}")
    for customer_name in customer_batches:
        customer_label = "all" if customer_name is None else customer_name
        try:
            shops = get_customer_shops(customer_name)
            logger.info("客户=%s，待采集店铺数=%s", customer_label, len(shops))
        except Exception as error:
            logger.exception("获取客户店铺失败 customer=%s：%s", customer_label, error)
            print(f"获取店铺失败：{customer_label}，原因：{error}")
            continue

        for shop in shops:
            process_shop(customer_label, shop, context)
