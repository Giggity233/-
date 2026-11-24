"""导出抖音（抖店）近 30 天销量大于指定阈值的商品。

右键直接运行即可。阈值改下面 MIN_SALES 变量。
店铺 Cookie 从中控平台接口 /api/v1/cookies/?platform=douyin 获取。
"""

import json
import math
import sys
from pathlib import Path

import requests


BASE_URL = "http://117.72.204.36:8000"
GOODS_LIST_URL = "https://fxg.jinritemai.com/product/tproduct/list"
OUTPUT_FILE = Path(__file__).with_name("douyin_30day_sales_over_threshold.json")
CUSTOMERS_FILE = Path(__file__).with_name("kehu.json")
MIN_SALES = 30          # 销量阈值，严格大于
TIMEOUT = 20
PAGE_SIZE = 100
MAX_PAGES = 200


def build_headers():
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i",
        "referer": (
            "https://fxg.jinritemai.com/ffa/g/list"
            "?btm_ppre=a0.b0.c0.d0&btm_pre=a2427.b76571.c902327.d871297"
        ),
        "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
        ),
        "x-tt-from-appid": "ffa-goods",
        "x-tt-from-end": "PC",
        "x-tt-from-page": "https://fxg.jinritemai.com/ffa/g/list",
        "x-tt-from-version": "1.0.1.8920",
    }


def cookie_string_to_dict(cookie):
    result = {}
    for item in cookie.split(";"):
        key, sep, value = item.strip().partition("=")
        if sep and key:
            result[key] = value
    return result


def load_selected_customers(path=CUSTOMERS_FILE):
    """读取 kehu.json；返回 None 代表全部客户。"""
    config = json.loads(path.read_text(encoding="utf-8"))
    customers = config.get("data") if isinstance(config, dict) else None
    if not isinstance(customers, list):
        raise ValueError("kehu.json 的 data 必须是客户名称字符串列表")
    selected = {c.strip() for c in customers if isinstance(c, str) and c.strip()}
    if "all" in {c.casefold() for c in selected}:
        return None
    return selected


def get_douyin_shops(base_url=BASE_URL, timeout=TIMEOUT):
    selected = load_selected_customers()
    resp = requests.get(
        f"{base_url.rstrip('/')}/api/v1/cookies/",
        params={"platform": "douyin"},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("ok") is False:
        raise RuntimeError(payload.get("message", "中控服务未返回店铺 Cookie"))
    shops = payload.get("data")
    if not isinstance(shops, list):
        raise ValueError("中控服务响应中缺少 data 店铺列表")

    valid = [
        s for s in shops
        if s.get("cookie") and s.get("cookie_status", "valid") == "valid"
    ]
    if selected is None:
        return valid
    return [
        s for s in valid
        if isinstance(s.get("customer"), str) and s["customer"].strip() in selected
    ]


def goods_request_params(page, page_size=PAGE_SIZE):
    return {
        "page": str(page),
        "pageSize": str(page_size),
        "sort": "desc",
        "order_field": "sell_num",
        "draft_status": "0",
        "comment_percent": "",
        "group_id": "",
        "sku_type": "",
        "tab": "onSale",
        "business_type": "4",
        "is_online": "1",
        "not_for_sale_search_type": "1",
        "from_mng": "1",
        "check_status": "3",
        "status": "0",
        "supply_status": "",
        "need_auto_rectify_info": "true",
        "need_pay_no_stock_skus": "true",
        "appid": "1",
    }


def _extract_sales(goods):
    """优先 sell_num_30d，回退 sell_num。"""
    for key in ("sell_num_30d", "sell_num"):
        value = goods.get(key)
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def get_qualifying_goods(cookie, min_sales, timeout=TIMEOUT, page_size=PAGE_SIZE):
    session = requests.Session()
    session.cookies.update(cookie_string_to_dict(cookie))

    qualifying = []
    top_goods = []
    page = 0
    total_pages = None

    while (total_pages is None or page < total_pages) and page < MAX_PAGES:
        resp = session.get(
            GOODS_LIST_URL,
            headers=build_headers(),
            params=goods_request_params(page, page_size),
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("st") != 0 or payload.get("code") != 0:
            raise RuntimeError(payload.get("msg") or "抖音商品接口请求失败")

        goods_list = payload.get("data") or []
        if not isinstance(goods_list, list):
            raise ValueError("抖音商品接口响应中缺少 data 列表")

        if total_pages is None:
            total = int(payload.get("total") or 0)
            actual_size = len(goods_list) or int(payload.get("size") or page_size) or page_size
            total_pages = math.ceil(total / actual_size) if total else 0

        for goods in goods_list:
            product_id = goods.get("product_id")
            if product_id is None:
                continue
            sales = _extract_sales(goods)
            if sales is None:
                continue
            item = {
                "goods_id": str(product_id),
                "sold_quantity_for_thirty_days": sales,
            }
            if sales > min_sales:
                qualifying.append(item)
            top_goods.append(item)
            top_goods.sort(key=lambda x: int(x["sold_quantity_for_thirty_days"]), reverse=True)
            del top_goods[2:]

        if not goods_list:
            break
        page += 1

    return qualifying or top_goods


def main():
    shops = get_douyin_shops()
    results = []
    errors = []

    print(f"共获取到 {len(shops)} 个抖音店铺，开始拉取商品……")
    for shop in shops:
        shop_name = str(shop.get("shop_name") or shop.get("shop_id") or "未命名店铺")
        print(f"[处理] {shop_name}")
        try:
            goods = get_qualifying_goods(str(shop["cookie"]), MIN_SALES)
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            errors.append(f"{shop_name}: {exc}")
            print(f"  [跳过] {exc}")
            continue
        print(f"  [完成] 命中商品 {len(goods)} 件")
        if goods:
            results.append({"shop_name": shop_name, "goods": goods})

    OUTPUT_FILE.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n已导出 {len(results)} 个店铺到：{OUTPUT_FILE.resolve()}")
    for err in errors:
        print(f"跳过店铺：{err}", file=sys.stderr)


if __name__ == "__main__":
    main()