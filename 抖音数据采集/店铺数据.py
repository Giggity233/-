"""采集指定客户的抖音店铺数据，并上传到联樽中控平台。

配置：
    1. 同级目录的“客户.json”仅列出需要采集的客户；
    2. 可用环境变量 LZ_BASE_URL 覆盖中控地址。
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, time as datetime_time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests


BASE_DIR = Path(__file__).resolve().parent
BASE_URL = os.getenv("LZ_BASE_URL", "http://117.72.204.36:8000").rstrip("/")
CUSTOMERS_FILE = BASE_DIR / "客户.json"
LOG_FILE = BASE_DIR / "店铺数据.log"
DOUYIN_PLATFORM = "douyin"
TIMEOUT = 20
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    encoding="utf-8",
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

COOKIE_EXPIRED_MARKERS = ("cookie", "登录", "登陆", "失效", "未登录", "会话", "session", "login")


def metric_error_reason(interface_name: str, message: str) -> str:
    """将登录失效保留为可操作状态，其他接口错误保留具体原因。"""
    if any(marker in message.lower() for marker in COOKIE_EXPIRED_MARKERS):
        return "Cookie过期"
    return f"{interface_name}：{message}"


def get_today_context() -> dict[str, Any]:
    """返回报表日期、小时、当天时间戳和抖音接口使用的日期字符串。"""
    now = datetime.now(SHANGHAI_TZ)
    day_start = datetime.combine(now.date(), datetime_time.min, tzinfo=SHANGHAI_TZ)
    day_end = datetime.combine(now.date(), datetime_time.max, tzinfo=SHANGHAI_TZ)
    yesterday = now.date() - timedelta(days=1)
    return {
        "report_date": now.strftime("%Y-%m-%d"),
        "time": now.hour,
        "date_compact": now.strftime("%Y%m%d"),
        "yesterday_compact": yesterday.strftime("%Y%m%d"),
        "start_timestamp": int(day_start.timestamp()),
        "end_timestamp": int(day_end.timestamp()),
    }


def load_customer_names() -> list[str]:
    """兼容客户.json 的常见结构，并去除重复、空白客户名。"""
    if not CUSTOMERS_FILE.exists():
        raise FileNotFoundError(f"未找到客户列表文件：{CUSTOMERS_FILE}")

    with CUSTOMERS_FILE.open("r", encoding="utf-8-sig") as file:
        content = json.load(file)

    if isinstance(content, list):
        customers = content
    elif isinstance(content, dict):
        customers = content.get("客户列表", content.get("customers", content.get("客户", [])))
    else:
        raise ValueError("客户.json 必须是客户列表，或包含“客户列表”的对象")

    if not isinstance(customers, list):
        raise ValueError("客户.json 中的客户列表必须是数组")

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
        raise ValueError("客户.json 中的客户列表为空，已停止采集")
    return names


def cookie_string_to_dict(cookie_value: str | dict[str, str]) -> dict[str, str]:
    """将中控返回的完整 Cookie 字符串转换为 requests 可用的字典。"""
    if isinstance(cookie_value, dict):
        return {str(key): str(value) for key, value in cookie_value.items()}
    if not isinstance(cookie_value, str) or not cookie_value.strip():
        raise ValueError("店铺没有可用 Cookie")

    parsed = SimpleCookie()
    parsed.load(cookie_value)
    cookies = {name: morsel.value for name, morsel in parsed.items()}
    if cookies:
        return cookies

    pairs = (part.strip().split("=", 1) for part in cookie_value.split(";"))
    cookies = {key.strip(): value.strip() for key, value in pairs if key.strip() and value.strip()}
    if not cookies:
        raise ValueError("Cookie 格式无法解析")
    return cookies


def douyin_headers(referer: str, cookies: dict[str, str], *, content_type: bool = False) -> dict[str, str]:
    """构造抖店和抖音客服后台通用请求头。"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "referer": referer,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    referer_parts = urlsplit(referer)
    if referer_parts.scheme and referer_parts.netloc:
        headers["origin"] = f"{referer_parts.scheme}://{referer_parts.netloc}"
    csrf_token = cookies.get("csrf_session_id")
    if csrf_token:
        headers["x-secsdk-csrf-token"] = csrf_token
    if content_type:
        headers["content-type"] = "application/json"
    return headers


def douyin_request(
    *,
    interface_name: str,
    method: str,
    url: str,
    cookies: dict[str, str],
    referer: str,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """调用抖音接口；失败时返回能直接上传到中控的文字状态。"""
    try:
        response = requests.request(
            method,
            url,
            headers=douyin_headers(referer, cookies, content_type=method != "GET"),
            cookies=cookies,
            params=params,
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        response_data = response.json()
    except (requests.RequestException, ValueError) as error:
        message = f"请求失败：{error}"
        logger.error("%s %s", interface_name, message, exc_info=True)
        return None, metric_error_reason(interface_name, message)

    if not isinstance(response_data, dict):
        message = "返回格式错误：不是 JSON 对象"
        logger.error("%s %s", interface_name, message)
        return None, metric_error_reason(interface_name, message)

    # 抖音不同接口的成功码有 0、200 和字符串 "0"；缺少 code 的旧接口也允许继续解析。
    code = response_data.get("code")
    if code not in (None, 0, "0", 200, "200"):
        detail = response_data.get("msg") or response_data.get("message") or response_data.get("detail") or code
        message = f"接口返回失败：{detail}"
        logger.error("%s %s", interface_name, message)
        return None, metric_error_reason(interface_name, message)
    if response_data.get("success") is False:
        detail = response_data.get("msg") or response_data.get("message") or "接口返回失败"
        message = f"接口返回失败：{detail}"
        logger.error("%s %s", interface_name, message)
        return None, metric_error_reason(interface_name, message)
    return response_data, None


def result_value(result: dict[str, Any], key: str) -> Any:
    """字段缺失也作为独立状态上传，避免一个字段阻断整店采集。"""
    if key not in result:
        message = f"抖音接口返回缺少字段：{key}"
        logger.error(message)
        return message
    return result[key]


def get_home_page_overview(cookies: dict[str, str]) -> tuple[dict[str, Any] | None, str | None]:
    data, error = douyin_request(
        interface_name="homepage",
        method="GET",
        url="https://fxg.jinritemai.com/pc/api/home/homepage",
        cookies=cookies,
        referer="https://fxg.jinritemai.com/ffa/mshop/homepage/index",
        params={
            "layout_ids": "1420",
            "homepage_version": "202606240",
            "refresh_card": '{"business_data_type":"Real"}',
        },
    )
    if error:
        return None, error

    result = {"pay_cnt": None, "income_amt": None, "ad_costed_amt": None}
    layouts = data.get("data", {}).get("lay_out_data", [])
    if not isinstance(layouts, list):
        return result, "homepage：返回字段 lay_out_data 格式错误"
    for layout in layouts:
        for card in layout.get("cards", []):
            if card.get("card_name") != "operating_data_card_v4":
                continue
            compass_list = card.get("data", {}).get("operating_data_card_v4_data", {}).get("compass_list", [])
            for item in compass_list if isinstance(compass_list, list) else []:
                key = item.get("key")
                if key in result:
                    result[key] = item.get("val")
            return result, None
    return result, "homepage：未找到经营数据卡片"


def get_experience_score(cookies: dict[str, str]) -> tuple[Any, str | None]:
    data, error = douyin_request(
        interface_name="getTrendByVersion",
        method="GET",
        url="https://fxg.jinritemai.com/governance/shop/experiencescore/getTrendByVersion",
        cookies=cookies,
        referer="https://fxg.jinritemai.com/ffa/eco/experience-score",
        params={"trend_type": "1", "time": "30", "exp_version": "v10"},
    )
    if error:
        return None, error
    return result_value(data.get("data", {}), "recent_7_avg_score"), None


def get_after_sales_count(cookies: dict[str, str], context: dict[str, Any]) -> tuple[Any, str | None]:
    data, error = douyin_request(
        interface_name="after_sale/list",
        method="POST",
        url="https://fxg.jinritemai.com/after_sale/pc/list",
        cookies=cookies,
        referer="https://fxg.jinritemai.com/ffa/merchant-aftersale-workbench/aftersale/list",
        params={"appid": "1", "_bid": "ffa_aftersale", "aid": "4272", "aftersale_platform_source": "fxg"},
        payload={
            "pageSize": 10,
            "page": 1,
            "order_by": ["status_deadline asc"],
            "conf_version": "v13",
            "search_receiver": "",
            "after_sale_status": "",
            "after_sale_type": "",
            "reason": "",
            "negotiate_status": "",
            "order_flag": [],
            "order_logistics_state": [],
            "apply_time_start": context["start_timestamp"],
            "apply_time_end": context["end_timestamp"],
        },
    )
    if error:
        return None, error
    return result_value(data, "total"), None


def get_pending_ticket_count(cookies: dict[str, str], context: dict[str, Any]) -> tuple[Any, str | None]:
    data, error = douyin_request(
        interface_name="task_order/list",
        method="POST",
        url="https://pigeon.jinritemai.com/backstage/task_order/list",
        cookies=cookies,
        referer="https://im.jinritemai.com/",
        params={"PIGEON_BIZ_TYPE": "2", "REAL_PIGEON_BIZ_TYPE": "2", "request_source": "doudian"},
        payload={
            "createTimeStart": context["start_timestamp"],
            "createTimeEnd": context["end_timestamp"],
            "businessType": 0,
            "pageSize": 10,
            "queryForMixTaskOrder": True,
            "page": 1,
        },
    )
    if error:
        return None, error
    return result_value(data.get("data", {}), "total"), None


def get_staff_data(
    cookies: dict[str, str],
    report_day: str,
    account_id: str | None,
) -> tuple[dict[str, Any] | None, str | None]:
    data, error = douyin_request(
        interface_name="queryStaffData",
        method="GET",
        url="https://pigeon.jinritemai.com/backstage/queryStaffData",
        cookies=cookies,
        referer="https://im.jinritemai.com/",
        params={
            "_pms": "1",
            "queryType": "1",
            "startTime": report_day,
            "endTime": report_day,
            "page": "1",
            "size": "100",
        },
    )
    if error:
        return None, error

    staff_rows = data.get("data", {}).get("staffDataModel", [])
    if not isinstance(staff_rows, list):
        return None, "queryStaffData：返回字段 staffDataModel 格式错误"
    if not account_id:
        return None, "queryStaffData：Cookie 或中控店铺未提供专员账号 ID"
    for row in staff_rows:
        staff_id = row.get("staffUserInfo", {}).get("staffId")
        if str(staff_id) == str(account_id):
            return row, None
    return None, f"queryStaffData：未找到专员账号 {account_id}"


def get_staff_account_id(shop: dict[str, Any], cookies: dict[str, str]) -> str | None:
    """优先使用当前 Cookie 的 PIGEON_CID，缺失时使用中控保存的首个专员账号。"""
    account_id = cookies.get("PIGEON_CID") or cookies.get("pigeon_cid")
    if account_id:
        return str(account_id)
    human_accounts = shop.get("human_accounts", [])
    if isinstance(human_accounts, list):
        for account in human_accounts:
            if not isinstance(account, dict):
                continue
            account_id = str(account.get("account_id") or "").strip()
            if account_id and account_id != "该id没抓":
                return account_id
    return None


def value_or_reason(value: Any, reason: str | None) -> Any:
    return reason if reason else value


def decimal_number_or_reason(value: Any, reason: str | None) -> Any:
    """将抖音返回的金额文本（如 ¥1,234.56）转成中控可接受的数字。"""
    if reason:
        return reason
    if isinstance(value, (int, float, Decimal)):
        return value
    text = str(value).replace(",", "").strip()
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return value
    try:
        return float(Decimal(match.group()))
    except InvalidOperation:
        return value


def integer_or_reason(value: Any, reason: str | None) -> Any:
    if reason:
        return reason
    try:
        return int(Decimal(str(value).replace(",", "").strip()))
    except (InvalidOperation, ValueError, TypeError):
        return value


def percentage_or_reason(value: Any, reason: str | None) -> Any:
    """将 “50.00%” 等抖音回复率统一为 0~100 的数字。"""
    if reason:
        return reason
    text = str(value).strip()
    is_percent_text = text.endswith("%")
    if is_percent_text:
        text = text[:-1].strip()
    try:
        rate = Decimal(text)
    except (InvalidOperation, ValueError, TypeError):
        return value
    if not is_percent_text and Decimal("0") <= rate <= Decimal("1"):
        rate *= 100
    return float(rate)


def duration_seconds_or_reason(value: Any, reason: str | None) -> Any:
    """把 “3分0秒” 等平均响应时长转换为秒，无法转换时保留原值。"""
    if reason:
        return reason
    if isinstance(value, (int, float, Decimal)):
        return value
    text = str(value).strip()
    numeric = re.fullmatch(r"\d+(?:\.\d+)?", text)
    if numeric:
        return float(Decimal(text))
    match = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)\s*分)?\s*(?:(\d+(?:\.\d+)?)\s*(?:秒|s))?\s*", text, re.IGNORECASE)
    if not match or (match.group(1) is None and match.group(2) is None):
        return value
    minutes = Decimal(match.group(1) or "0")
    seconds = Decimal(match.group(2) or "0")
    return float(minutes * 60 + seconds)


def calculate_timeout_count(reply_total: Any, three_minute_reply_rate: Any, reason: str | None) -> Any:
    """超时数量 = 专员回复总数 × (1 - 三分钟回复率)，按四舍五入取整。"""
    if reason:
        return reason
    try:
        total = Decimal(str(reply_total))
        rate_text = str(three_minute_reply_rate).strip().removesuffix("%").strip()
        rate = Decimal(rate_text)
        if Decimal("0") <= rate <= Decimal("1") and not str(three_minute_reply_rate).strip().endswith("%"):
            rate *= 100
        if total < 0 or not Decimal("0") <= rate <= Decimal("100"):
            raise ValueError("总数或回复率不在有效范围")
        return int((total * (Decimal("100") - rate) / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError, TypeError):
        return "无法根据专员回复总数和3分钟回复率计算超时数量"


def collect_store_metrics(shop: dict[str, Any], cookies: dict[str, str], context: dict[str, Any]) -> dict[str, Any]:
    """按 /api/v1/store-metrics/upsert/ 的字段名整理抖音采集结果。"""
    overview, overview_error = get_home_page_overview(cookies)
    score, score_error = get_experience_score(cookies)
    after_sales, after_sales_error = get_after_sales_count(cookies, context)
    pending_tickets, pending_tickets_error = get_pending_ticket_count(cookies, context)
    account_id = get_staff_account_id(shop, cookies)
    staff_today, staff_today_error = get_staff_data(cookies, context["date_compact"], account_id)
    staff_yesterday, staff_yesterday_error = get_staff_data(cookies, context["yesterday_compact"], account_id)

    overview = overview or {}
    staff_today = staff_today or {}
    staff_yesterday = staff_yesterday or {}
    reply_total = value_or_reason(result_value(staff_today, "servConvCnt"), staff_today_error)
    reply_rate = percentage_or_reason(
        result_value(staff_today.get("workTimeThreeMinRespRate", {}), "fieldValue"),
        staff_today_error,
    )
    return {
        "today_order_count": integer_or_reason(result_value(overview, "pay_cnt"), overview_error),
        "today_turnover": decimal_number_or_reason(result_value(overview, "income_amt"), overview_error),
        "today_ad_spend": decimal_number_or_reason(result_value(overview, "ad_costed_amt"), overview_error),
        "store_experience_score": decimal_number_or_reason(score, score_error),
        # 抖店现有接口只提供店铺体验分，服务体验分同步使用这个采集值。
        "service_experience_score": decimal_number_or_reason(score, score_error),
        "pending_after_sales": integer_or_reason(after_sales, after_sales_error),
        "pending_tickets": integer_or_reason(pending_tickets, pending_tickets_error),
        "specialist_reply_count": integer_or_reason(reply_total, staff_today_error),
        "specialist_three_minute_reply_rate": reply_rate,
        "specialist_timeout_count": calculate_timeout_count(reply_total, reply_rate, staff_today_error),
        "specialist_yesterday_average_response_seconds": duration_seconds_or_reason(
            result_value(staff_yesterday, "avgRespDuration"), staff_yesterday_error
        ),
    }


def get_customer_shops(customer_name: str | None) -> list[dict[str, Any]]:
    """获取指定客户的店铺；customer_name 为 None 时获取该平台全部店铺。"""
    params = {"platform": DOUYIN_PLATFORM}
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
        raise ValueError("中控返回的店铺缺少 shop_id")
    payload = {
        "shop_id": shop_id,
        "platform": DOUYIN_PLATFORM,
        "time": context["time"],
        "report_date": context["report_date"],
        **metrics,
    }
    response = requests.post(f"{BASE_URL}/api/v1/store-metrics/upsert/", json=payload, timeout=TIMEOUT)
    response.raise_for_status()
    response_data = response.json()
    if not response_data.get("ok", False):
        raise RuntimeError(response_data.get("message", "店铺数据上传失败"))


def process_shop(customer_name: str, shop: dict[str, Any], context: dict[str, Any]) -> None:
    shop_name = shop.get("shop_name", "未命名店铺")
    shop_id = shop.get("shop_id", "未知 shop_id")
    try:
        cookies = cookie_string_to_dict(shop.get("cookie", ""))
        metrics = collect_store_metrics(shop, cookies, context)
        print(metrics)
        upload_store_metrics(shop, metrics, context)
        logger.info("上传成功 customer=%s shop=%s(%s)", customer_name, shop_name, shop_id)
        print(f"上传成功：{customer_name} / {shop_name} ({shop_id})")
    except Exception as error:
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


if __name__ == "__main__":
    main()
