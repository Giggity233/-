"""将 ``pdd_30day_sales_over_100.json`` 中的拼多多商品按需采集并入库。

流程：读取销售 JSON → 从中控读取店铺 Cookie → 逐商品查库 → 对缺失或缺主图
的商品调用拼多多商品详情接口 → 按 ``sec.py`` 的 ``zl`` 格式上传到商品库。

注：本脚本只读取 ``pdd_30day_sales_over_100.json``，不会修改该文件。
最小销量门槛由顶部 ``DEFAULT_MIN_SOLD`` 控制（也可用 ``--min-sold`` 覆盖）。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import execjs
import requests


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
DEFAULT_SOURCE = Path("pdd_30day_sales_over_100.json")

# === 只需修改这一个值，即可控制最小销量（近 30 天）===
# 低于该值的商品不会被采集/入库；设为 0 表示不按销量过滤。
DEFAULT_MIN_SOLD = 20
# =====================================================

COOKIES_URL = "/api/v1/cookies/"
PRODUCTS_URL = "/api/v1/ai/products/"
PRODUCT_UPSERT_URL = "/api/v1/ai/products/upsert/"
PDD_GOODS_DETAIL_URL = "https://mms.pinduoduo.com/glide/v2/mms/query/commit/on_shop/detail"
PDD_GOODS_PROPERTY_URL = "https://mms.pinduoduo.com/draco-ms/mms/query-goods-property"
PDD_REFERER = "https://mms.pinduoduo.com/goods/goods_list?msfrom=mms_sidenav"

_ANTI_CONTEXT: Any | None = None


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
class PddShop:
    shop_id: str
    shop_name: str
    cookie: str


def _anti_content() -> str:
    """使用与 ltlapi 相同的 anti.js + 当前秒级时间戳生成 anti-content。"""
    global _ANTI_CONTEXT
    if _ANTI_CONTEXT is None:
        anti_path = Path(__file__).with_name("anti.js")
        if not anti_path.is_file():
            raise FileNotFoundError(f"未找到 anti.js：{anti_path}")
        print(f"[准备] 加载 anti-content 脚本：{anti_path}")
        _ANTI_CONTEXT = execjs.compile(anti_path.read_text(encoding="utf-8"))
    return str(_ANTI_CONTEXT.call("get_anti", int(time.time())))


def _pdd_headers() -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": _anti_content(),
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "referer": PDD_REFERER,
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/154.0.0.0 Safari/537.36"
        ),
    }


def _cookie_dict(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for fragment in cookie.split(";"):
        key, separator, value = fragment.strip().partition("=")
        if key and separator:
            result[key] = value
    return result


def _as_int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def load_sales_goods(source: Path, min_sold: int = DEFAULT_MIN_SOLD) -> list[SalesGoods]:
    """读取销售 JSON，保留店铺名、商品 ID、近 30 天销量。

    - 只读 ``source``，不会改写该 JSON 文件。
    - ``min_sold > 0`` 时，30 天销量缺失或低于该值的商品会被过滤掉。
    """
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
    skipped_by_sold = 0
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

            sold = _as_int_or_none(goods_data.get("sold_quantity_for_thirty_days"))
            if min_sold > 0 and (sold is None or sold < min_sold):
                skipped_by_sold += 1
                continue

            result.append(
                SalesGoods(
                    shop_name=shop_name,
                    goods_id=goods_id,
                    sold_quantity_for_thirty_days=sold,
                )
            )

    if min_sold > 0 and skipped_by_sold:
        print(f"[过滤] 近 30 天销量 < {min_sold}（或缺失）的商品已跳过：{skipped_by_sold} 个")
    return result


def get_pdd_shops(base_url: str, timeout: int) -> dict[str, PddShop]:
    """按接口文档从中控读取有效拼多多店铺 Cookie，并以店铺名建立映射。"""
    response = requests.get(
        f"{base_url.rstrip('/')}{COOKIES_URL}",
        params={"platform": "pdd"},
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

    matches: dict[str, list[PddShop]] = defaultdict(list)
    for raw_shop in raw_shops:
        if not isinstance(raw_shop, Mapping):
            continue
        if raw_shop.get("cookie_status", "valid") != "valid":
            continue
        if not raw_shop.get("shop_name") or not raw_shop.get("shop_id") or not raw_shop.get("cookie"):
            continue
        shop = PddShop(
            shop_id=str(raw_shop["shop_id"]),
            shop_name=str(raw_shop["shop_name"]),
            cookie=str(raw_shop["cookie"]),
        )
        matches[shop.shop_name].append(shop)

    shops: dict[str, PddShop] = {}
    for name, same_name_shops in matches.items():
        if len(same_name_shops) == 1:
            shops[name] = same_name_shops[0]
        else:
            print(f"[跳过] 中控存在 {len(same_name_shops)} 个同名有效店铺：{name}")
    return shops


def product_has_main_images(
    session: requests.Session, base_url: str, shop_id: str, goods_id: str, timeout: int
) -> bool:
    """商品已入库且已保存至少一张主图时返回 True。"""
    response = session.get(
        f"{base_url.rstrip('/')}{PRODUCTS_URL}",
        params={"platform": "pdd", "shopid": shop_id, "goods_id": goods_id},
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


def fetch_goods_detail(
    session: requests.Session, goods_id: str, timeout: int
) -> dict[str, Any]:
    """调用商品详情接口，取得与 ``sec.py`` 相同的图片、SKU 等数据源。"""
    response = session.post(
        PDD_GOODS_DETAIL_URL,
        headers=_pdd_headers(),
        json={"goods_id": goods_id},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    result = payload.get("result") if isinstance(payload, Mapping) else None
    if not isinstance(result, Mapping):
        message = payload.get("errorMsg") if isinstance(payload, Mapping) else None
        raise ImportError(f"商品详情采集失败：{message or goods_id}")
    return dict(result)


def fetch_goods_properties(
    session: requests.Session, goods_id: str, timeout: int, max_attempts: int = 2
) -> list[Mapping[str, Any]]:
    """获取商品属性；与 ``sec.py`` 一样最多重试两次。"""
    for _ in range(max_attempts):
        response = session.post(
            PDD_GOODS_PROPERTY_URL,
            headers=_pdd_headers(),
            json={"goods_id": goods_id},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
        result = payload.get("result") if isinstance(payload, Mapping) else None
        properties = result.get("goods_properties") if isinstance(result, Mapping) else None
        if isinstance(properties, list):
            return [item for item in properties if isinstance(item, Mapping)]
    return []


def _image_urls(gallery: Any) -> list[str]:
    """提取详情接口画廊中的有效图片链接。"""
    if not isinstance(gallery, list):
        return []
    return [
        image["url"]
        for image in gallery
        if isinstance(image, Mapping)
        and isinstance(image.get("url"), str)
        and image["url"].startswith(("http://", "https://"))
    ]


def build_zl(
    shop: PddShop,
    goods: SalesGoods,
    detail: Mapping[str, Any],
    properties: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """按 ``sec.py`` 的字段及价格/SKU 规则组装商品入库数据。"""
    zl: dict[str, Any] = {
        "shopSN": shop.shop_id,
        "goods_id": goods.goods_id,
        "goods_name": detail.get("goods_name", ""),
        "min_group_price": detail.get("min_group_price"),
        "max_group_price": detail.get("max_group_price"),
        "sold_quantity": goods.sold_quantity_for_thirty_days,
        "created_at": detail.get("created_at"),
        "mainimgurls": _image_urls(detail.get("carousel_gallery")),
        "detailimgurls": _image_urls(detail.get("detail_gallery")),
    }

    styles: list[str] = []
    models: list[str] = []
    skudetails: list[dict[str, Any]] = []
    carnival_prices: list[int] = []
    skus = detail.get("skus")
    if isinstance(skus, list):
        for sku in skus:
            if not isinstance(sku, Mapping):
                continue
            specs = sku.get("spec")
            if not isinstance(specs, list) or len(specs) < 2:
                continue
            first_spec, second_spec = specs[0], specs[1]
            if not isinstance(first_spec, Mapping) or not isinstance(second_spec, Mapping):
                continue
            style = first_spec.get("spec_name")
            model = second_spec.get("spec_name")
            if not isinstance(style, str) or not isinstance(model, str):
                continue
            if style not in styles:
                styles.append(style)
            if model not in models:
                models.append(model)
            skudetails.append(
                {
                    "skuname": f"{style}%{model}",
                    "sku_id": sku.get("sku_id"),
                    "price": sku.get("multi_price"),
                    "quantity": sku.get("quantity"),
                }
            )
            carnival_price = _as_int_or_none(sku.get("carnival_price"))
            if carnival_price is not None:
                carnival_prices.append(carnival_price)

    if carnival_prices:
        lowest_carnival_price = min(carnival_prices)
        if lowest_carnival_price != 0:
            zl["min_group_price"] = lowest_carnival_price
        zl["max_group_price"] = max(carnival_prices)
    zl["skudetails"] = skudetails
    zl["skutypes"] = [
        {"skutypename": "款式", "values": styles},
        {"skutypename": "型号", "values": models},
    ]
    zl["values"] = [
        {"AttributeName": item["name"], "AttributeValue": item["values"][0]["value"]}
        for item in properties
        if isinstance(item.get("name"), str)
        and isinstance(item.get("values"), list)
        and item["values"]
        and isinstance(item["values"][0], Mapping)
        and item["values"][0].get("value") is not None
    ]
    return zl


def upsert_product(
    session: requests.Session,
    base_url: str,
    shop: PddShop,
    goods: SalesGoods,
    zl: Mapping[str, Any],
    timeout: int,
) -> None:
    """将按 ``sec.py`` 格式组装的商品数据上传至中控商品库。"""
    response = session.post(
        f"{base_url.rstrip('/')}{PRODUCT_UPSERT_URL}",
        json={
            "platform": "pdd",
            "shopSN": shop.shop_id,
            "goods_id": goods.goods_id,
            "zl": zl,
        },
        timeout=timeout,
    )
    print(dict(zl))
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is not True:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise ImportError(f"商品入库失败：{message or goods.goods_id}")


def run(source: Path, base_url: str, timeout: int, min_sold: int) -> dict[str, int]:
    """执行商品查重、采集、入库，返回处理统计。"""
    goods_rows = load_sales_goods(source, min_sold)
    print(
        f"[开始] 从 {source.resolve()} 读取到 {len(goods_rows)} 个去重商品"
        f"（最小销量门槛：{min_sold if min_sold > 0 else '不过滤'}）。"
    )
    shops_by_name = get_pdd_shops(base_url, timeout)
    print(f"[Cookie] 已读取 {len(shops_by_name)} 个可唯一匹配的有效拼多多店铺。")

    central_session = requests.Session()
    missing_by_shop: dict[str, list[SalesGoods]] = defaultdict(list)
    unmatched_shops = 0
    existing_count = 0
    check_failures = 0

    for index, goods in enumerate(goods_rows, start=1):
        shop = shops_by_name.get(goods.shop_name)
        if shop is None:
            unmatched_shops += 1
            print(f"[商品 {index}/{len(goods_rows)}] 店铺未匹配 Cookie，跳过：{goods.shop_name} / {goods.goods_id}")
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
    pdd_collect_failed = 0
    upload_failures = 0
    for shop_name, missing_goods in missing_by_shop.items():
        shop = shops_by_name[shop_name]
        print(f"[店铺] {shop_name} 有 {len(missing_goods)} 个待补全商品，开始采集详情。")
        pdd_session = requests.Session()
        pdd_session.cookies.update(_cookie_dict(shop.cookie))

        for goods in missing_goods:
            try:
                detail = fetch_goods_detail(pdd_session, goods.goods_id, timeout)
                properties = fetch_goods_properties(pdd_session, goods.goods_id, timeout)
                zl = build_zl(shop, goods, detail, properties)
            except (requests.RequestException, ValueError, ImportError) as error:
                pdd_collect_failed += 1
                print(f"[采集] 商品详情失败，未入库：{goods.goods_id}；{error}")
                continue
            try:
                upsert_product(central_session, base_url, shop, goods, zl, timeout)
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
        "pdd_collect_failed": pdd_collect_failed,
        "upload_failed": upload_failures,
    }
    print(f"[完成] {summary}")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="拼多多销售商品按需采集并入库")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="销售商品 JSON 路径")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="中控服务地址")
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时秒数")
    parser.add_argument(
        "--min-sold",
        type=int,
        default=DEFAULT_MIN_SOLD,
        help=f"近 30 天最小销量门槛，默认 {DEFAULT_MIN_SOLD}；设为 0 表示不过滤",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.timeout <= 0:
        print("--timeout 必须大于 0", file=sys.stderr)
        return 2
    if args.min_sold < 0:
        print("--min-sold 不能为负数", file=sys.stderr)
        return 2
    try:
        summary = run(args.source, args.base_url, args.timeout, args.min_sold)
    except (OSError, ValueError, ImportError, requests.RequestException) as error:
        print(f"[失败] {error}", file=sys.stderr)
        return 1
    return 1 if any(summary[key] for key in ("unmatched_shop", "check_failed", "upload_failed")) else 0


if __name__ == "__main__":
    raise SystemExit(main())