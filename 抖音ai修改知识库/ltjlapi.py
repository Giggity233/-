"""按销售商品清单批量抓取抖音聊天问答。

流程：
1. 从销售 JSON 读取 (店铺名, 商品ID)，按店铺分组；
2. 每个店铺只调用一次 fuzzySearchConversation，翻页拉取时间范围内全部会话；
3. 对每个商品，从已拉取的会话里筛出属于该商品的消息，整理成问答对；
4. 用 intent_level / is_refund / 订单信息 判定会话是售前、售后还是中性；
5. 输出时保证售前问答占比至少 MIN_PRESALE_RATIO（默认 60%）。

输出格式：纯问答数组 [{"问题": "...", "回答": "..."}]，
可直接作为清洗插件输入（原始插件取第一个 [ 到最后一个 ] 即能解析）。

抓取天数由 DAYS 控制，售前占比由 MIN_PRESALE_RATIO 控制，右键运行生效。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Mapping
from zoneinfo import ZoneInfo

import requests


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
DEFAULT_SOURCE = Path("douyin_30day_sales_over_threshold.json")
DEFAULT_OUTPUT_DIR = Path("ltjlapi_json")
CONVERSATION_URL = "https://pigeon.jinritemai.com/backstage/fuzzySearchConversation"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
PAGE_SIZE = 100
DAYS = 2                    # 抓取最近多少天
MIN_PRESALE_RATIO = 0.6       # 输出中售前问答最低占比
TIMEOUT = 20

# 强售后关键词：命中即判定为售后
AFTERSALE_KEYWORDS = (
    "退款", "退货", "换货", "投诉", "纠纷", "破损", "少件", "漏发", "错发",
    "质量问题", "假货", "售后", "维权", "赔付", "补偿", "返现", "差价",
    "取消订单", "修改地址", "改地址", "修改收货", "修改订单", "修改电话",
)

# 强售前关键词：命中即判定为售前
PRESALE_KEYWORDS = (
    "咨询价格", "咨询商品", "咨询活动", "价格问题", "商品咨询", "活动咨询",
    "库存", "优惠", "规格", "尺码", "颜色", "材质", "发货时间", "指定快递",
    "快递选择", "什么时候发货", "包邮", "运费", "正品", "保质期", "成分",
    "适合", "推荐", "区别", "怎么用", "如何使用",
)

try:
    sys.stdout.reconfigure(errors="backslashreplace")
except (AttributeError, OSError):
    pass


class DouyinApiError(RuntimeError):
    """抖音或中控接口返回异常时抛出。"""


# ========================= HTTP / 工具 =========================

def _headers() -> dict[str, str]:
    return {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://im.jinritemai.com",
        "priority": "u=1, i",
        "referer": "https://im.jinritemai.com/",
        "sec-ch-ua": '"Not:A-Brand";v="8", "Chromium";v="156", "Google Chrome";v="156"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/156.0.0.0 Safari/537.36"
        ),
        "x-secsdk-csrf-token": "DOWNGRADE",
    }


def _cookie_dict(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for fragment in cookie.split(";"):
        key, separator, value = fragment.strip().partition("=")
        if key and separator:
            result[key] = value
    return result


def _time_range(days: int) -> tuple[datetime, datetime, int, int]:
    if days <= 0:
        raise ValueError("days 必须大于 0")
    today_midnight = datetime.now(BEIJING_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start_midnight = today_midnight - timedelta(days=days)
    return (
        start_midnight,
        today_midnight,
        int(start_midnight.timestamp()),
        int(today_midnight.timestamp()),
    )


def _atomic_save(output_path: Path, payload: Any) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temp_name = temporary.name
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
        Path(temp_name).replace(output_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


# ========================= 消息解析 =========================

def _chat_product_id(chat: Mapping[str, Any]) -> str | None:
    ext = chat.get("ext") or {}
    point_info = ext.get("point_info")
    if isinstance(point_info, str):
        try:
            point_info = json.loads(point_info)
        except (TypeError, ValueError):
            point_info = None
    if isinstance(point_info, Mapping):
        product_id = point_info.get("product_id")
        if product_id and str(product_id) != "0":
            return str(product_id)
    for key in ("goods_id", "shark_product_id"):
        value = ext.get(key)
        if value and str(value) != "0":
            return str(value)
    return None


def _chat_sender(chat: Mapping[str, Any]) -> str:
    ext = chat.get("ext") or {}
    if ext.get("type") != "text":
        return "system"
    biz_role = ext.get("s:sender_biz_role")
    sender_role = ext.get("sender_role")
    if biz_role == "Buyer" or sender_role == "1":
        return "buyer"
    if biz_role == "CurrentServer" or sender_role == "2":
        return "seller"
    return "system"


def _chat_text(chat: Mapping[str, Any]) -> str | None:
    ext = chat.get("ext") or {}
    if ext.get("type") != "text":
        return None
    content = chat.get("content")
    if not isinstance(content, str):
        return None
    content = content.strip()
    return content or None


def _chat_timestamp(chat: Mapping[str, Any], fallback: int) -> int:
    try:
        return int(chat.get("create_time"))
    except (TypeError, ValueError):
        return fallback


def _conversation_product_messages(
    conversation: Mapping[str, Any], target_goods_id: str
) -> list[Mapping[str, Any]]:
    chats = conversation.get("chats")
    if not isinstance(chats, list):
        return []
    conversation_products: list[str] = []
    raw_products = conversation.get("product_id_list")
    if isinstance(raw_products, list):
        conversation_products = [str(item) for item in raw_products if item]
    current_product_id: str | None = None
    if conversation_products == [target_goods_id]:
        current_product_id = target_goods_id

    selected: list[Mapping[str, Any]] = []
    for chat in chats:
        if not isinstance(chat, Mapping):
            continue
        product_id = _chat_product_id(chat)
        if product_id:
            current_product_id = product_id
        if current_product_id == target_goods_id:
            selected.append(chat)
    return selected


def _iter_qa_pairs(messages: list[Mapping[str, Any]]) -> Iterator[dict[str, str]]:
    ordered = sorted(
        enumerate(messages),
        key=lambda item: (_chat_timestamp(item[1], item[0]), item[0]),
    )
    question_parts: list[str] = []
    answer_parts: list[str] = []

    def build_pair() -> dict[str, str] | None:
        if not question_parts or not answer_parts:
            return None
        return {"问题": "\n".join(question_parts), "回答": "\n".join(answer_parts)}

    for _, message in ordered:
        text = _chat_text(message)
        if text is None:
            continue
        sender = _chat_sender(message)
        if sender == "buyer":
            pair = build_pair()
            if pair is not None:
                yield pair
                question_parts = []
                answer_parts = []
            question_parts.append(text)
        elif sender == "seller":
            if question_parts:
                answer_parts.append(text)

    pair = build_pair()
    if pair is not None:
        yield pair


# ========================= 会话分类 / 订单提取 =========================

def _intent_text(conversation: Mapping[str, Any]) -> str:
    parts: list[str] = []
    for key in ("intent_level1", "intent_level2", "intent_level3", "intent_level4"):
        value = conversation.get(key)
        if value:
            parts.append(str(value))
    return " > ".join(parts)


def _extract_order_ids(conversation: Mapping[str, Any]) -> list[str]:
    order_ids: list[str] = []

    def add(value: Any) -> None:
        if value is None:
            return
        text = str(value)
        if text in ("", "0"):
            return
        if text not in order_ids:
            order_ids.append(text)

    raw = conversation.get("order_id_list")
    if isinstance(raw, list):
        for item in raw:
            add(item)
    raw = conversation.get("inquiryOrderList")
    if isinstance(raw, list):
        for item in raw:
            add(item)

    chats = conversation.get("chats")
    if isinstance(chats, list):
        for chat in chats:
            if not isinstance(chat, Mapping):
                continue
            ext = chat.get("ext") or {}
            add(ext.get("order_id"))
            point_info = ext.get("point_info")
            if isinstance(point_info, str):
                try:
                    point_info = json.loads(point_info)
                except (TypeError, ValueError):
                    point_info = None
            if isinstance(point_info, Mapping):
                add(point_info.get("shop_order_id"))
    return order_ids


def _classify_conversation(conversation: Mapping[str, Any]) -> str:
    """返回 presale / aftersale / neutral。"""
    intent_text = _intent_text(conversation)

    # 1. 强售后信号
    if any(kw in intent_text for kw in AFTERSALE_KEYWORDS):
        return "aftersale"
    if conversation.get("is_refund") is True or conversation.get("is_refund_v2") == 1:
        return "aftersale"
    if conversation.get("service_problem_labels"):
        return "aftersale"
    if conversation.get("intent_level1") == "订单操作":
        return "aftersale"

    # 2. 强售前信号
    if conversation.get("intent_level1") in ("店铺/活动咨询",):
        return "presale"
    if conversation.get("intent_level2") in ("价格问题", "商品咨询", "活动咨询"):
        return "presale"
    if any(kw in intent_text for kw in PRESALE_KEYWORDS):
        return "presale"

    # 3. 物流履约 / 订单交易 归为售前（售中）
    if conversation.get("intent_level1") in ("物流履约", "订单交易"):
        return "presale"

    # 4. 其他 / 无意图 → 中性
    return "neutral"


def _conversation_user_key(conversation: Mapping[str, Any]) -> str:
    user_name = str(conversation.get("userName") or "未知买家")
    uid = str(
        conversation.get("security_userId")
        or conversation.get("conversationId")
        or ""
    )
    return f"{user_name}（security_user_id={uid}）" if uid else user_name


# ========================= 销售清单 / 店铺 Cookie =========================

def load_sales_products(source: Path) -> list[tuple[str, str]]:
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise FileNotFoundError(f"未找到销售 JSON：{source.resolve()}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"销售 JSON 格式错误：{error}") from error

    if not isinstance(payload, list):
        raise ValueError("销售 JSON 顶层必须是店铺列表")
    products: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for shop_data in payload:
        if not isinstance(shop_data, Mapping):
            continue
        shop_name = str(shop_data.get("shop_name") or "").strip()
        goods_list = shop_data.get("goods")
        if not shop_name or not isinstance(goods_list, list):
            print("[跳过] 销售 JSON 中存在缺少店铺名或 goods 列表的记录。")
            continue
        for goods_data in goods_list:
            if not isinstance(goods_data, Mapping) or goods_data.get("goods_id") is None:
                continue
            item = (shop_name, str(goods_data["goods_id"]).strip())
            if not item[1] or item in seen:
                continue
            seen.add(item)
            products.append(item)
    return products


def get_douyin_shops(base_url: str, timeout: int) -> dict[str, dict[str, str]]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v1/cookies/",
        params={"platform": "douyin"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is False:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise DouyinApiError(f"读取中控 Cookie 失败：{message or '响应格式错误'}")
    raw_shops = payload.get("data")
    if not isinstance(raw_shops, list):
        raise DouyinApiError("中控 Cookie 接口缺少 data 店铺列表")

    same_name_shops: dict[str, list[dict[str, str]]] = defaultdict(list)
    for shop in raw_shops:
        if not isinstance(shop, Mapping) or shop.get("cookie_status", "valid") != "valid":
            continue
        if not shop.get("shop_name") or not shop.get("shop_id") or not shop.get("cookie"):
            continue
        same_name_shops[str(shop["shop_name"])].append(
            {"shopid": str(shop["shop_id"]), "cookie": str(shop["cookie"])}
        )

    result: dict[str, dict[str, str]] = {}
    for shop_name, candidates in same_name_shops.items():
        if len(candidates) == 1:
            result[shop_name] = candidates[0]
        else:
            print(f"[跳过] 中控有 {len(candidates)} 个同名有效店铺，无法自动匹配：{shop_name}")
    return result


# ========================= 会话抓取 =========================

def fetch_all_conversations(
    session: requests.Session,
    start_ms: int,
    end_ms: int,
    timeout: int,
) -> list[Mapping[str, Any]]:
    all_conversations: list[Mapping[str, Any]] = []
    page = 1
    while True:
        body = {
            "commentType": [-1, 0, 2],
            "sessionTypeList": [],
            "conversation_server_type": [3, 1, 2, 0],
            "page": page,
            "size": PAGE_SIZE,
            "evaluationLabelList": [],
            "workTimeType": 0,
            "isFirstResolutionConversation": False,
            "inquiryOrderTypes": [],
            "isInquiryOrders": [-1, 0, 1],
            "turn2_labor_type_agg": [],
            "robot_evaluation_type": [],
            "humanEvaluationType": [],
            "conv_source": [],
            "dispatch_group_id": [],
            "startTime": start_ms,
            "endTime": end_ms,
            "startSceneTypeList": [1, 2, 3, 4, 5, 8, 0],
            "endSceneTypeList": [1, 2, 6, 7, 8, 9, 10, 11],
            "staffQuery": "",
            "userQuery": "",
            "conversationId": "",
            "content": "",
        }
        response = session.post(
            CONVERSATION_URL,
            headers=_headers(),
            params={"PIGEON_BIZ_TYPE": "2", "_pms": "1"},
            json=body,
            timeout=timeout,
        )
        print(f"[会话] 第 {page} 页 HTTP {response.status_code}")
        response.raise_for_status()
        try:
            payload = response.json()
        except ValueError as error:
            raise DouyinApiError("抖音会话接口未返回 JSON") from error
        if payload.get("st") != 0 or payload.get("code") != 0:
            raise DouyinApiError(payload.get("msg") or "抖音会话接口失败")

        data = payload.get("data") or []
        if not isinstance(data, list):
            raise DouyinApiError("会话接口 data 不是列表")
        all_conversations.extend(item for item in data if isinstance(item, Mapping))

        total = int(payload.get("total") or 0)
        print(f"[会话] 本页 {len(data)} 条，累计 {len(all_conversations)}/{total}")
        if not data or len(all_conversations) >= total:
            break
        page += 1
    return all_conversations


# ========================= 商品匹配 + 售前/售后分类 =========================

def match_product_from_conversations(
    conversations: list[Mapping[str, Any]],
    shopid: str,
    goodsid: str,
    days: int,
    min_presale_ratio: float = MIN_PRESALE_RATIO,
    presale_only: bool = False,
    include_neutral: bool = False,
) -> tuple[list[dict[str, str]], int, int, dict[str, Any]]:
    """从已拉取全量会话里筛出目标商品 QA，并保证售前占比 >= min_presale_ratio。

    返回 (qas, 命中会话数, 输出问答数, stats)。
    qas 是纯数组 [{"问题": ..., "回答": ...}]，与示例 JSON 单条问答格式一致，
    原始清洗插件取第一个 [ 到最后一个 ] 即可解析。
    """
    start_datetime, end_datetime, start_time, end_time = _time_range(days)

    user_pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    hit_conversations = 0

    for conversation in conversations:
        messages = _conversation_product_messages(conversation, str(goodsid))
        if not messages:
            continue
        pairs = list(_iter_qa_pairs(messages))
        if not pairs:
            continue

        hit_conversations += 1
        category = _classify_conversation(conversation)
        order_ids = _extract_order_ids(conversation)
        intent = _intent_text(conversation)
        user_key = _conversation_user_key(conversation)

        for pair in pairs:
            user_pairs[user_key].append(
                {
                    "问题": pair["问题"],
                    "回答": pair["回答"],
                    "分类": category,
                    "订单ID": order_ids,
                    "意图": intent,
                }
            )

    all_items: list[tuple[str, dict[str, Any]]] = [
        (user_key, pair) for user_key, pairs in user_pairs.items() for pair in pairs
    ]
    presale_items = [item for item in all_items if item[1]["分类"] == "presale"]
    aftersale_items = [item for item in all_items if item[1]["分类"] == "aftersale"]
    neutral_items = [item for item in all_items if item[1]["分类"] == "neutral"]

    # 候选集合
    if presale_only:
        candidates = presale_items
    elif include_neutral:
        candidates = all_items
    else:
        candidates = presale_items + aftersale_items

    # 控制售前占比
    if not candidates:
        final_items: list[tuple[str, dict[str, Any]]] = []
    else:
        cand_presale = [item for item in candidates if item[1]["分类"] == "presale"]
        cand_others = [item for item in candidates if item[1]["分类"] != "presale"]
        if not cand_presale:
            final_items = candidates
        elif len(cand_presale) / len(candidates) >= min_presale_ratio:
            final_items = candidates
        else:
            max_others = int(
                len(cand_presale) * (1 - min_presale_ratio) / min_presale_ratio
            )
            final_items = cand_presale + cand_others[:max_others]

    final_users: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for user_key, pair in final_items:
        final_users[user_key].append(pair)

    # 扁平化为纯问答数组，字段名与示例 JSON 中的问答项一致
    qas: list[dict[str, str]] = [
        {"问题": pair["问题"], "回答": pair["回答"]}
        for pairs in final_users.values()
        for pair in pairs
    ]

    stats = {
        "total_pairs": len(all_items),
        "presale_pairs": len(presale_items),
        "aftersale_pairs": len(aftersale_items),
        "neutral_pairs": len(neutral_items),
        "output_pairs": len(final_items),
        "presale_ratio_all": round(len(presale_items) / len(all_items), 4) if all_items else 0,
        "presale_ratio_output": round(
            sum(1 for item in final_items if item[1]["分类"] == "presale") / len(final_items), 4
        ) if final_items else 0,
    }

    return qas, hit_conversations, len(qas), stats


# ========================= 主流程 =========================

def main(
    source: Path = DEFAULT_SOURCE,
    base_url: str = DEFAULT_BASE_URL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    timeout: int = TIMEOUT,
    days: int = DAYS,
    min_presale_ratio: float = MIN_PRESALE_RATIO,
    presale_only: bool = False,
    include_neutral: bool = False,
) -> list[Path]:
    if timeout <= 0:
        raise ValueError("timeout 必须大于 0")
    if days <= 0:
        raise ValueError("days 必须大于 0")
    if not 0 < min_presale_ratio <= 1:
        raise ValueError("min_presale_ratio 必须在 (0, 1] 之间")

    output_dir.mkdir(parents=True, exist_ok=True)
    products = load_sales_products(source)
    print(
        f"[开始] 从 {source.resolve()} 读取到 {len(products)} 个去重商品，"
        f"抓取最近 {days} 天，售前占比要求 ≥ {min_presale_ratio:.0%}"
    )

    products_by_shop: dict[str, list[str]] = defaultdict(list)
    for shop_name, goodsid in products:
        products_by_shop[shop_name].append(goodsid)

    shops = get_douyin_shops(base_url, timeout)
    print(f"[Cookie] 自动读取到 {len(shops)} 个可唯一匹配的有效抖音店铺。")

    start_datetime, end_datetime, start_time, end_time = _time_range(days)
    start_ms = start_time * 1000
    end_ms = end_time * 1000 - 1
    print(
        "[时间] "
        f"{start_datetime:%Y-%m-%d %H:%M:%S %Z} 至 "
        f"{end_datetime:%Y-%m-%d %H:%M:%S %Z}"
    )

    completed: list[Path] = []
    failures = 0
    total_output_pairs = 0

    for shop_index, (shop_name, goodsids) in enumerate(products_by_shop.items(), start=1):
        shop = shops.get(shop_name)
        if shop is None:
            failures += len(goodsids)
            print(
                f"[店铺 {shop_index}/{len(products_by_shop)}] 找不到店铺 Cookie，"
                f"跳过 {len(goodsids)} 个商品：{shop_name}"
            )
            continue

        shopid = shop["shopid"]
        print(
            f"[店铺 {shop_index}/{len(products_by_shop)}] 店铺={shop_name}，"
            f"商品数={len(goodsids)}，先拉全量会话……"
        )
        session = requests.Session()
        session.cookies.update(_cookie_dict(shop["cookie"]))

        try:
            conversations = fetch_all_conversations(
                session, start_ms=start_ms, end_ms=end_ms, timeout=timeout,
            )
        except (requests.RequestException, DouyinApiError, ValueError) as error:
            failures += len(goodsids)
            print(f"[店铺 {shop_index}/{len(products_by_shop)}] 拉取会话失败，跳过该店铺：{error}")
            continue

        print(
            f"[店铺 {shop_index}/{len(products_by_shop)}] 全量会话 {len(conversations)} 个，"
            f"开始按 {len(goodsids)} 个商品匹配。"
        )

        for goods_index, goodsid in enumerate(goodsids, start=1):
            output_path = output_dir / f"douyin_{shopid}_{goodsid}_qa.json"
            try:
                qas, hit, out_count, stats = match_product_from_conversations(
                    conversations=conversations,
                    shopid=shopid,
                    goodsid=goodsid,
                    days=days,
                    min_presale_ratio=min_presale_ratio,
                    presale_only=presale_only,
                    include_neutral=include_neutral,
                )
                _atomic_save(output_path, qas)
                completed.append(output_path)
                total_output_pairs += out_count
                print(
                    f"[商品 {goods_index}/{len(goodsids)}] goodsid={goodsid}，"
                    f"命中 {hit} 个会话，输出 {out_count} 组问答，"
                    f"售前占比 原始={stats['presale_ratio_all']:.0%} / "
                    f"输出={stats['presale_ratio_output']:.0%}，"
                    f"写入：{output_path.name}"
                )
            except (OSError, ValueError) as error:
                failures += 1
                print(
                    f"[商品 {goods_index}/{len(goodsids)}] goodsid={goodsid} 处理失败：{error}"
                )

    print(
        f"[完成] 已生成 {len(completed)} 个商品 JSON，共 {total_output_pairs} 组问答，"
        f"失败/跳过 {failures} 个商品。"
    )
    return completed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按抖音销售商品清单批量抓取聊天问答")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="销售商品 JSON 路径")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="中控服务地址")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="问答 JSON 输出目录（默认：ltjlapi_json）",
    )
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help="单次请求超时秒数")
    parser.add_argument("--days", type=int, default=DAYS, help=f"抓取最近多少天（默认 {DAYS}）")
    parser.add_argument(
        "--min-presale-ratio",
        type=float,
        default=MIN_PRESALE_RATIO,
        help=f"输出中售前问答最低占比（默认 {MIN_PRESALE_RATIO}）",
    )
    parser.add_argument(
        "--presale-only",
        action="store_true",
        help="只输出售前问答（100% 售前）",
    )
    parser.add_argument(
        "--include-neutral",
        action="store_true",
        help="是否把中性对话也纳入候选（默认不纳入）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        main(
            args.source,
            args.base_url,
            args.output_dir,
            args.timeout,
            args.days,
            args.min_presale_ratio,
            args.presale_only,
            args.include_neutral,
        )
    except (OSError, ValueError, DouyinApiError, requests.RequestException) as error:
        print(f"[失败] {error}", file=sys.stderr)
        raise SystemExit(1)