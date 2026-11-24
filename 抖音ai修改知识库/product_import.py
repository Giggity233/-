"""将 douyin_30day_sales_over_threshold.json 中的抖音商品按需采集并入库。

流程：读取销售 JSON → 从中控读取抖音店铺 Cookie → 逐商品查库 → 对缺失或缺主图
的商品调用抖音商品列表接口（按 id_name_code 精确查询）+ previewOnline 详情接口
→ 按抖音入库脚本的 zl 格式上传到商品库。

依赖本地 dy_jl_ab.js 生成 a_bogus。
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import execjs
import requests


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
DEFAULT_SOURCE = Path("douyin_30day_sales_over_threshold.json")
COOKIES_URL = "/api/v1/cookies/"
PRODUCTS_URL = "/api/v1/ai/products/"
PRODUCT_UPSERT_URL = "/api/v1/ai/products/upsert/"
DY_GOODS_LIST_URL = "https://fxg.jinritemai.com/product/tproduct/list"
DY_GOODS_PREVIEW_URL = "https://fxg.jinritemai.com/product/tproduct/previewOnline"
DY_REFERER = "https://fxg.jinritemai.com/ffa/g/list"

_JS_CONTEXT: Any | None = None


try:
    # 防止商品标题含 Emoji 时，GBK 控制台因打印日志而中断脚本。
    sys.stdout.reconfigure(errors="backslashreplace")
except (AttributeError, OSError):
    pass


class ImportError(RuntimeError):
    """采集或入库流程中的可读错误。"""


@dataclass(frozen=True)
class SalesGoods:
    shop_name: str
    goods_id: str
    sold_quantity_for_thirty_days: int | None


@dataclass(frozen=True)
class DouyinShop:
    shop_id: str
    shop_name: str
    cookie: str


# ========================= a_bogus 签名 =========================

def _load_js() -> Any:
    """加载并缓存 dy_jl_ab.js 的 JS 上下文。"""
    global _JS_CONTEXT
    if _JS_CONTEXT is not None:
        return _JS_CONTEXT

    candidates = [
        Path(__file__).with_name("dy_jl_ab.js"),
        Path(__file__).parent / "js" / "dy_jl_ab.js",
        Path(__file__).parent.parent / "抖音机器人回复" / "js" / "dy_jl_ab.js",
    ]
    for path in candidates:
        if path.is_file():
            print(f"[准备] 加载 JS：{path}")
            _JS_CONTEXT = execjs.compile(path.read_text(encoding="utf-8"))
            return _JS_CONTEXT

    raise FileNotFoundError(
        "未找到 dy_jl_ab.js，请放到脚本同目录，或修改 _load_js 里的搜索路径"
    )


def _gen_a_bogus(params: Mapping[str, Any], user_agent: str) -> str:
    """根据当前 GET 参数生成 a_bogus。"""
    ctx = _load_js()
    pa = urllib.parse.urlencode(params)
    da = json.dumps({}, separators=(",", ":")).replace(" ", "")
    return str(ctx.call("enc", pa, da, user_agent))


def _dy_headers() -> dict[str, str]:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i",
        "referer": DY_REFERER,
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/142.0.0.0 Safari/537.36"
        ),
        "x-tt-from-appid": "ffa-goods",
        "x-tt-from-end": "PC",
        "x-tt-from-page": DY_REFERER,
        "x-tt-from-version": "1.0.1.520",
    }


# ========================= 工具函数 =========================

def _cookie_dict(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for fragment in cookie.split(";"):
        key, separator, value = fragment.strip().partition("=")
        if key and separator:
            if value.lower() == "null":
                value = ""
            result[key] = value
    return result


def _as_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def time_str_to_timestamp(time_str: Any, fmt: str = "%Y-%m-%d %H:%M:%S") -> int:
    """把 '2026-03-04 10:55:01' 转成秒级时间戳；失败返回 0。"""
    if isinstance(time_str, (int, float)):
        return int(time_str)
    if not isinstance(time_str, str) or not time_str.strip():
        return 0
    try:
        return int(datetime.strptime(time_str, fmt).timestamp())
    except ValueError:
        return 0


def convert_to_attr_list(raw_dict: Any) -> list[dict[str, str]]:
    """把 product_format(dict) 转成 [{AttributeName, AttributeValue}]。"""
    if not isinstance(raw_dict, Mapping):
        return []
    attr_list: list[dict[str, str]] = []
    for key, value in raw_dict.items():
        if value is None or value == "":
            continue
        attr_list.append(
            {
                "AttributeName": key,
                "AttributeValue": (value if isinstance(value, str) else str(value))[:20],
            }
        )
    return attr_list


# ========================= 销售 JSON / 店铺 Cookie =========================

def load_sales_goods(source: Path) -> list[SalesGoods]:
    """读取销售 JSON，保留店铺名、商品 ID、近 30 天销量。"""
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"未找到销售 JSON：{source.resolve()}") from None
    except json.JSONDecodeError as error:
        raise ImportError(f"销售 JSON 格式错误：{error}") from error

    if not isinstance(raw, list):
        raise ImportError("销售 JSON 顶层必须是店铺列表")

    result: list[SalesGoods] = []
    seen: set[tuple[str, str]] = set()
    for shop_data in raw:
        if not isinstance(shop_data, Mapping):
            continue
        shop_name = str(shop_data.get("shop_name") or "").strip()
        goods_list = shop_data.get("goods")
        if not shop_name or not isinstance(goods_list, list):
            print("[跳过] 销售 JSON 中存在缺少店铺名或 goods 列表的记录。")
            continue

        for goods_data in goods_list:
            if not isinstance(goods_data, Mapping) or goods_data.get("goods_id") is None:
                print(f"[跳过] 店铺 {shop_name} 有缺少 goods_id 的记录。")
                continue
            goods_id = str(goods_data["goods_id"]).strip()
            key = (shop_name, goods_id)
            if not goods_id or key in seen:
                continue
            seen.add(key)
            result.append(
                SalesGoods(
                    shop_name=shop_name,
                    goods_id=goods_id,
                    sold_quantity_for_thirty_days=_as_int_or_none(
                        goods_data.get("sold_quantity_for_thirty_days")
                    ),
                )
            )
    return result


def get_douyin_shops(base_url: str, timeout: int) -> dict[str, DouyinShop]:
    """按接口文档从中控读取有效抖音店铺 Cookie，并以店铺名建立映射。"""
    response = requests.get(
        f"{base_url.rstrip('/')}{COOKIES_URL}",
        params={"platform": "douyin"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is False:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise ImportError(f"读取中控 Cookie 失败：{message or '响应格式错误'}")

    raw_shops = payload.get("data")
    if not isinstance(raw_shops, list):
        raise ImportError("中控 Cookie 接口缺少 data 店铺列表")

    matches: dict[str, list[DouyinShop]] = defaultdict(list)
    for raw_shop in raw_shops:
        if not isinstance(raw_shop, Mapping):
            continue
        if raw_shop.get("cookie_status", "valid") != "valid":
            continue
        if not raw_shop.get("shop_name") or not raw_shop.get("shop_id") or not raw_shop.get("cookie"):
            continue
        shop = DouyinShop(
            shop_id=str(raw_shop["shop_id"]),
            shop_name=str(raw_shop["shop_name"]),
            cookie=str(raw_shop["cookie"]),
        )
        matches[shop.shop_name].append(shop)

    shops: dict[str, DouyinShop] = {}
    for name, same_name_shops in matches.items():
        if len(same_name_shops) == 1:
            shops[name] = same_name_shops[0]
        else:
            print(f"[跳过] 中控存在 {len(same_name_shops)} 个同名有效店铺：{name}")
    return shops


# ========================= 查库 / 采集 / 入库 =========================

def product_has_main_images(
    session: requests.Session, base_url: str, shop_id: str, goods_id: str, timeout: int
) -> bool:
    """商品已入库且已保存至少一张主图时返回 True。"""
    response = session.get(
        f"{base_url.rstrip('/')}{PRODUCTS_URL}",
        params={"platform": "douyin", "shopid": shop_id, "goods_id": goods_id},
        timeout=timeout,
    )
    if response.status_code == 404:
        return False
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        raise ImportError(f"商品查库响应异常：goods_id={goods_id}")
    product = payload.get("data")
    if not isinstance(product, Mapping):
        return False
    main_images = product.get("mainimgurls")
    return isinstance(main_images, list) and any(
        isinstance(url, str) and url.startswith(("http://", "https://"))
        for url in main_images
    )


def fetch_goods_from_list(
    session: requests.Session, goods_id: str, timeout: int
) -> dict[str, Any]:
    """用列表接口按 id_name_code 精确查一个商品，返回 data 中的一条。"""
    headers = _dy_headers()
    params = {
        "page": "0",
        "pageSize": "20",
        "id_name_code": str(goods_id),
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
        "order_field": "audit_time",
        "sort": "desc",
        "appid": "1",
        "_bid": "ffa_goods",
        "_lid": "468012705947",
    }
    params["a_bogus"] = _gen_a_bogus(params, headers["user-agent"])

    response = session.get(
        DY_GOODS_LIST_URL, headers=headers, params=params, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("st") != 0 or payload.get("code") != 0:
        raise ImportError(payload.get("msg") or f"抖音商品列表失败：{goods_id}")

    goods_list = payload.get("data")
    if not isinstance(goods_list, list) or not goods_list:
        raise ImportError(f"抖音商品列表未返回数据：{goods_id}")

    for item in goods_list:
        if isinstance(item, Mapping) and str(item.get("product_id")) == str(goods_id):
            return dict(item)
    return dict(goods_list[0])


def fetch_goods_preview(
    session: requests.Session, goods_id: str, timeout: int
) -> dict[str, Any]:
    """调用 previewOnline，返回 data（含 spec_detail / spec_prices / product_format）。"""
    headers = _dy_headers()
    params = {
        "product_id": str(goods_id),
        "need_live_status": "true",
        "appid": "1",
    }
    params["a_bogus"] = _gen_a_bogus(params, headers["user-agent"])

    response = session.get(
        DY_GOODS_PREVIEW_URL, headers=headers, params=params, timeout=timeout
    )
    response.raise_for_status()
    payload = response.json()
    print(payload)
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping):
        raise ImportError(f"抖音商品详情未返回 data：{goods_id}")
    return dict(data)


def _extract_skus(
    preview_data: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """从 previewOnline 返回中提取 skutypes / skudetails。"""
    skutypes: list[dict[str, Any]] = []
    spec_detail = preview_data.get("spec_detail")
    if isinstance(spec_detail, Mapping):
        specs = spec_detail.get("specs")
        if isinstance(specs, list):
            for spec in specs:
                if not isinstance(spec, Mapping):
                    continue
                values_raw = spec.get("values")
                values: list[str] = []
                if isinstance(values_raw, list):
                    values = [
                        v["name"]
                        for v in values_raw
                        if isinstance(v, Mapping) and isinstance(v.get("name"), str)
                    ]
                skutypes.append(
                    {"skutypename": spec.get("name", ""), "values": values}
                )

    skudetails: list[dict[str, Any]] = []
    spec_prices = preview_data.get("spec_prices")
    if isinstance(spec_prices, list):
        for sp in spec_prices:
            if not isinstance(sp, Mapping):
                continue
            name = ""
            sell_props = sp.get("sell_properties")
            if isinstance(sell_props, list):
                for prop in sell_props:
                    if isinstance(prop, Mapping) and isinstance(prop.get("value_name"), str):
                        name += prop["value_name"]
            skudetails.append(
                {
                    "skuname": name,
                    "sku_id": sp.get("id"),
                    "price": sp.get("price"),
                    "quantity": sp.get("stock_num"),
                }
            )
    return skutypes, skudetails


def build_zl(
    shop: DouyinShop,
    goods: SalesGoods,
    list_data: Mapping[str, Any],
    preview_data: Mapping[str, Any],
) -> dict[str, Any]:
    """按抖音入库脚本的 zl 字段组装。"""
    zl: dict[str, Any] = {
        "platform": "douyin",
        "PT": "2",
        "username": "",
        "shopSN": shop.shop_id,
        "goods_id": goods.goods_id,
        "goods_name": list_data.get("name", ""),
        "mainimgurls": list_data.get("pics") or [],
        "detailimgurls": list_data.get("pics") or [],
        "created_at": time_str_to_timestamp(list_data.get("create_time")),
        "min_group_price": list_data.get("price_lower"),
        "max_group_price": list_data.get("price_higher"),
        "sold_quantity": (
            goods.sold_quantity_for_thirty_days
            if goods.sold_quantity_for_thirty_days is not None
            else _as_int_or_none(list_data.get("sell_num"))
        ),
    }

    try:
        skutypes, skudetails = _extract_skus(preview_data)
        if not skudetails:
            raise ValueError("preview 未返回 skudetails")
        zl["skutypes"] = skutypes
        zl["skudetails"] = skudetails
    except Exception as error:  # noqa: BLE001
        print(f"[警告] 获取规格详情失败，使用兜底：{goods.goods_id}；{error}")
        zl["skutypes"] = [{"skutypename": "权限缺失", "values": ["权限缺失"]}]
        zl["skudetails"] = [
            {"skuname": "权限缺失", "sku_id": 111000, "price": 0, "quantity": 0}
        ]

    preview_format = preview_data.get("product_format")
    if isinstance(preview_format, Mapping) and preview_format:
        zl["values"] = convert_to_attr_list(preview_format)
    else:
        zl["values"] = convert_to_attr_list(list_data.get("product_format_new") or {})

    return zl


def upsert_product(
    session: requests.Session,
    base_url: str,
    zl: Mapping[str, Any],
    timeout: int,
) -> None:
    """按抖音入库脚本的格式上传：{'platform': 'douyin', 'zl': zl}。"""
    response = session.post(
        f"{base_url.rstrip('/')}{PRODUCT_UPSERT_URL}",
        json={"platform": "douyin", "zl": dict(zl)},
        timeout=timeout,
    )
    print(dict(zl))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise ImportError(f"商品入库失败：{message}")


# ========================= 主流程 =========================

def run(source: Path, base_url: str, timeout: int) -> dict[str, int]:
    goods_rows = load_sales_goods(source)
    print(f"[开始] 从 {source.resolve()} 读取到 {len(goods_rows)} 个去重商品。")
    shops_by_name = get_douyin_shops(base_url, timeout)
    print(f"[Cookie] 已读取 {len(shops_by_name)} 个可唯一匹配的有效抖音店铺。")

    central_session = requests.Session()
    missing_by_shop: dict[str, list[SalesGoods]] = defaultdict(list)
    unmatched_shops = 0
    existing_count = 0
    check_failures = 0

    for index, goods in enumerate(goods_rows, start=1):
        shop = shops_by_name.get(goods.shop_name)
        if shop is None:
            unmatched_shops += 1
            print(
                f"[商品 {index}/{len(goods_rows)}] 店铺未匹配 Cookie，"
                f"跳过：{goods.shop_name} / {goods.goods_id}"
            )
            continue
        try:
            if product_has_main_images(
                central_session, base_url, shop.shop_id, goods.goods_id, timeout
            ):
                existing_count += 1
                print(f"[商品 {index}/{len(goods_rows)}] 已入库且有主图，跳过：{goods.goods_id}")
            else:
                missing_by_shop[goods.shop_name].append(goods)
                print(
                    f"[商品 {index}/{len(goods_rows)}] 未入库或缺主图，"
                    f"等待详情采集：{goods.goods_id}"
                )
        except (requests.RequestException, ValueError, ImportError) as error:
            check_failures += 1
            print(f"[商品 {index}/{len(goods_rows)}] 查库失败，跳过：{goods.goods_id}；{error}")

    uploaded_count = 0
    dy_collect_failed = 0
    upload_failures = 0
    for shop_name, missing_goods in missing_by_shop.items():
        shop = shops_by_name[shop_name]
        print(f"[店铺] {shop_name} 有 {len(missing_goods)} 个待补全商品，开始采集详情。")
        dy_session = requests.Session()
        dy_session.cookies.update(_cookie_dict(shop.cookie))

        for goods in missing_goods:
            try:
                list_data = fetch_goods_from_list(dy_session, goods.goods_id, timeout)
                preview_data = fetch_goods_preview(dy_session, goods.goods_id, timeout)
                zl = build_zl(shop, goods, list_data, preview_data)
            except (requests.RequestException, ValueError, ImportError) as error:
                dy_collect_failed += 1
                print(f"[采集] 商品详情失败，未入库：{goods.goods_id}；{error}")
                continue
            try:
                upsert_product(central_session, base_url, zl, timeout)
                uploaded_count += 1
                print(f"[入库] 成功：{shop_name} / {goods.goods_id}")
            except (requests.RequestException, ValueError, ImportError) as error:
                upload_failures += 1
                print(f"[入库] 失败：{shop_name} / {goods.goods_id}；{error}")

    summary = {
        "total": len(goods_rows),
        "existing": existing_count,
        "uploaded": uploaded_count,
        "unmatched_shop": unmatched_shops,
        "check_failed": check_failures,
        "dy_collect_failed": dy_collect_failed,
        "upload_failed": upload_failures,
    }
    print(f"[完成] {summary}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抖音销售商品按需采集并入库")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="销售商品 JSON 路径")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="中控服务地址")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时秒数")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("--timeout 必须大于 0", file=sys.stderr)
        return 2
    try:
        summary = run(args.source, args.base_url, args.timeout)
    except (OSError, ValueError, ImportError, requests.RequestException) as error:
        print(f"[失败] {error}", file=sys.stderr)
        return 1
    return 1 if any(
        summary[key]
        for key in ("unmatched_shop", "check_failed", "upload_failed")
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())