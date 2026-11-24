"""导出拼多多近 30 天销量大于指定阈值的商品。

店铺 Cookie 从中控平台接口 ``/api/v1/cookies/?platform=pdd`` 获取，
不会写入本脚本或导出的 JSON 文件。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

import execjs
import requests


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
PDD_GOODS_LIST_URL = "https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList"
DEFAULT_OUTPUT = Path("pdd_30day_sales_over_100.json")
CUSTOMERS_FILE = Path(__file__).with_name("kehu.json")

_ANTI_CONTEXT: Any | None = None


def _anti_content() -> str:
    """使用与 ltjlapi 相同的 anti.js 和当前时间生成 anti-content。"""
    global _ANTI_CONTEXT
    if _ANTI_CONTEXT is None:
        anti_path = Path(__file__).with_name("anti.js")
        if not anti_path.is_file():
            raise FileNotFoundError(f"未找到 anti.js：{anti_path}")
        print(f"[准备] 加载 anti-content 脚本：{anti_path}")
        _ANTI_CONTEXT = execjs.compile(anti_path.read_text(encoding="utf-8"))
    return str(_ANTI_CONTEXT.call("get_anti", int(time.time())))


def build_headers() -> dict[str, str]:
    """返回拼多多商品接口所需的、含实时 anti-content 的请求头。"""
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": _anti_content(),
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "referer": "https://mms.pinduoduo.com/goods/goods_list?msfrom=mms_sidenav",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
        ),
    }


def cookie_string_to_dict(cookie: str) -> dict[str, str]:
    """将中控接口返回的标准 Cookie 字符串转为 requests 可用的字典。"""
    result: dict[str, str] = {}
    for item in cookie.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key:
            result[key] = value
    return result


def load_selected_customers(path: Path = CUSTOMERS_FILE) -> set[str] | None:
    """读取 kehu.json；返回 None 代表选择全部客户。"""
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"未找到客户配置文件：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"客户配置文件不是有效 JSON：{path}") from exc

    customers = config.get("data") if isinstance(config, dict) else None
    if not isinstance(customers, list) or not all(
        isinstance(customer, str) for customer in customers
    ):
        raise ValueError("kehu.json 的 data 必须是客户名称字符串列表")

    selected_customers = {customer.strip() for customer in customers if customer.strip()}
    if "all" in {customer.casefold() for customer in selected_customers}:
        return None
    return selected_customers


def get_pdd_shops(
    base_url: str, timeout: int, customers_file: Path = CUSTOMERS_FILE
) -> list[dict[str, Any]]:
    """读取有效拼多多店铺，并按 kehu.json 的客户列表筛选。"""
    selected_customers = load_selected_customers(customers_file)
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v1/cookies/",
        params={"platform": "pdd"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("ok") is False:
        raise RuntimeError(payload.get("message", "中控服务未返回店铺 Cookie"))

    shops = payload.get("data")
    if not isinstance(shops, list):
        raise ValueError("中控服务响应中缺少 data 店铺列表")

    valid_shops = [
        shop
        for shop in shops
        if shop.get("cookie") and shop.get("cookie_status", "valid") == "valid"
    ]
    if selected_customers is None:
        return valid_shops

    return [
        shop
        for shop in valid_shops
        if isinstance(shop.get("customer"), str)
        and shop["customer"].strip() in selected_customers
    ]


def goods_request_body(page: int, page_size: int) -> dict[str, Any]:
    return {
        "pre_sale_type": 4,
        "page": page,
        "order_by": "sold_quantity_30d:desc,id:desc",
        "out_goods_sn_gray_flag": True,
        "shipment_time_type": 3,
        "is_onsale": 1,
        "sold_out": 0,
        "size": page_size,
    }


def get_qualifying_goods(
    cookie: str, min_sales: int, timeout: int, page_size: int = 100
) -> list[dict[str, int | str]]:
    """读取一个店铺的商品，返回近 30 天销量严格大于 min_sales 的商品。"""
    session = requests.Session()
    session.cookies.update(cookie_string_to_dict(cookie))

    qualifying_goods: list[dict[str, int | str]] = []
    top_goods: list[dict[str, int | str]] = []
    page = 1
    total_pages: int | None = None

    while total_pages is None or page <= total_pages:
        response = session.post(
            PDD_GOODS_LIST_URL,
            headers=build_headers(),
            json=goods_request_body(page, page_size),
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        print(payload)
        if not payload.get("success"):
            raise RuntimeError(payload.get("errorMsg") or "拼多多商品接口请求失败")

        result = payload.get("result") or {}
        goods_list = result.get("goods_list") or []
        if not isinstance(goods_list, list):
            raise ValueError("拼多多商品接口响应中缺少 result.goods_list")

        if total_pages is None:
            total = int(result.get("total") or 0)
            # 部分账号会被接口限制每页返回数量；以实际返回条数计算页数，
            # 避免请求 size=100 却只返回 10 条时漏掉后续商品。
            actual_page_size = len(goods_list) or page_size
            total_pages = math.ceil(total / actual_page_size)

        page_sales: list[int] = []
        for goods in goods_list:
            sales = goods.get("sold_quantity_for_thirty_days", 0)
            try:
                sales = int(sales)
            except (TypeError, ValueError):
                continue
            page_sales.append(sales)
            if goods.get("id") is None:
                continue

            goods_summary = {
                "goods_id": str(goods["id"]),
                "sold_quantity_for_thirty_days": sales,
            }
            if sales > min_sales:
                qualifying_goods.append(goods_summary)

            # 作为没有达标商品时的回退结果，始终保留销量最高的两件商品。
            top_goods.append(goods_summary)
            top_goods.sort(
                key=lambda item: int(item["sold_quantity_for_thirty_days"]),
                reverse=True,
            )
            del top_goods[2:]

        # 接口已按 30 天销量倒序排列，后续页不会再出现符合条件的商品。
        # 若尚未收集到两件回退商品，则继续翻页以补足该店铺的最高两件。
        if not goods_list or (
            page_sales
            and max(page_sales) <= min_sales
            and (qualifying_goods or len(top_goods) >= 2)
        ):
            break
        page += 1

    return qualifying_goods or top_goods


def export_sales_over_threshold(
    base_url: str, min_sales: int, output: Path, timeout: int
) -> tuple[int, list[str]]:
    shops = get_pdd_shops(base_url, timeout)
    shop_results: list[dict[str, Any]] = []
    errors: list[str] = []

    for shop in shops:
        shop_name = str(shop.get("shop_name") or shop.get("shop_id") or "未命名店铺")
        try:
            goods = get_qualifying_goods(str(shop["cookie"]), min_sales, timeout)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors.append(f"{shop_name}: {exc}")
            continue

        if goods:
            shop_results.append({"shop_name": shop_name, "goods": goods})

    # 输出只保留用户所需的店铺名、商品 ID 和近 30 天销量，不包含 Cookie。
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(shop_results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return len(shop_results), errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="导出拼多多近 30 天销量达标商品")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="中控服务地址")
    parser.add_argument("--min-sales", type=int, default=30, help="销量阈值（严格大于）")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="导出 JSON 路径")
    parser.add_argument("--timeout", type=int, default=20, help="单次 HTTP 请求超时秒数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.min_sales < 0:
        print("--min-sales 不能小于 0", file=sys.stderr)
        return 2

    try:
        shop_count, errors = export_sales_over_threshold(
            args.base_url, args.min_sales, args.output, args.timeout
        )
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        print(f"导出失败：{exc}", file=sys.stderr)
        return 1

    print(f"已导出 {shop_count} 个店铺到：{args.output.resolve()}")
    for error in errors:
        print(f"跳过店铺：{error}", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
