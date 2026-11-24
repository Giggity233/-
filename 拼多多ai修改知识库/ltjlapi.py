"""按销售商品清单批量抓取拼多多聊天问答。

脚本从 ``pdd_30day_sales_over_100.json`` 读取店铺和商品 ID，再按接口文档从
中控获取对应店铺的 Cookie。每个商品单独输出为
``ltjlapi_json/pdd_<shopid>_<goodsid>_qa.json``，不需要在脚本中填写 Cookie。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterator, Mapping
from zoneinfo import ZoneInfo

import execjs
import requests


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
DEFAULT_SOURCE = Path("pdd_30day_sales_over_100.json")
DEFAULT_OUTPUT_DIR = Path("ltjlapi_json")
GOODS_USERS_URL = (
    "https://mms.pinduoduo.com/latitude/search/message/getMessagesUsersByGoodsId"
)
MESSAGES_URL = "https://mms.pinduoduo.com/latitude/search/message/getMessages"
BEIJING_TZ = ZoneInfo("Asia/Shanghai")
MAX_USERS = 150
MESSAGE_PAGE_SIZE = 100

_ANTI_CONTEXT: Any | None = None


try:
    # 避免 Windows GBK 控制台打印 Emoji 或特殊昵称时中断任务。
    sys.stdout.reconfigure(errors="backslashreplace")
except (AttributeError, OSError):
    pass


class PddApiError(RuntimeError):
    """拼多多或中控接口返回异常时抛出。"""


def _anti_content() -> str:
    """使用与原 ltlapi 相同的 anti.js 和当前时间生成 anti-content。"""
    global _ANTI_CONTEXT
    if _ANTI_CONTEXT is None:
        anti_path = Path(__file__).with_name("anti.js")
        if not anti_path.is_file():
            raise FileNotFoundError(f"未找到 anti.js：{anti_path}")
        print(f"[准备] 加载 anti-content 脚本：{anti_path}")
        _ANTI_CONTEXT = execjs.compile(anti_path.read_text(encoding="utf-8"))
    return str(_ANTI_CONTEXT.call("get_anti", int(time.time())))


def _headers(referer: str) -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": _anti_content(),
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "referer": referer,
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


def _time_range() -> tuple[datetime, datetime, int, int]:
    """返回中国时区“五天前零点至今天零点”的时间范围。"""
    today_midnight = datetime.now(BEIJING_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    five_days_ago_midnight = today_midnight - timedelta(days=5)
    return (
        five_days_ago_midnight,
        today_midnight,
        int(five_days_ago_midnight.timestamp()),
        int(today_midnight.timestamp()),
    )


def _post_pdd_json(
    session: requests.Session,
    url: str,
    body: dict[str, Any],
    referer: str,
    timeout: int,
) -> dict[str, Any]:
    response = session.post(
        url,
        headers=_headers(referer),
        json=body,
        timeout=timeout,
    )
    print(f"[请求] HTTP {response.status_code}")
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError as error:
        raise PddApiError("拼多多接口未返回 JSON") from error
    if not isinstance(payload, dict) or payload.get("success") is not True:
        error_code = payload.get("errorCode") if isinstance(payload, Mapping) else None
        error_msg = payload.get("errorMsg") if isinstance(payload, Mapping) else None
        raise PddApiError(f"拼多多接口失败：errorCode={error_code}，errorMsg={error_msg}")
    return payload


def _atomic_save(output_path: Path, payload: Mapping[str, Any]) -> None:
    """只在单个商品整理完成后写一次，并避免留下半个 JSON 文件。"""
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


def _message_text(message: Mapping[str, Any]) -> str | None:
    """仅保留普通文本；图片、商品卡片、系统消息等不参与问答。"""
    if message.get("type") not in (None, 0, "0"):
        return None
    content = message.get("content")
    if not isinstance(content, str):
        return None
    content = content.strip()
    return content or None


def _timestamp(message: Mapping[str, Any], fallback: int) -> int:
    try:
        return int(message.get("ts"))
    except (TypeError, ValueError):
        return fallback


def iter_qa_pairs(
    messages: list[Mapping[str, Any]],
    uid: int | str,
) -> Iterator[dict[str, str]]:
    """按时间整理文字聊天为多个独立的 ``问题/回答`` 对。"""
    ordered_messages = sorted(
        enumerate(messages),
        key=lambda item: (_timestamp(item[1], item[0]), item[0]),
    )
    question_parts: list[str] = []
    answer_parts: list[str] = []

    def build_pair() -> dict[str, str] | None:
        if not question_parts or not answer_parts:
            return None
        return {"问题": "\n".join(question_parts), "回答": "\n".join(answer_parts)}

    for _, message in ordered_messages:
        text = _message_text(message)
        if text is None:
            print(
                "[清洗] 跳过非文本/空消息："
                f"uid={uid}，msgId={message.get('msgId')}，type={message.get('type')}"
            )
            continue

        # getMessages 中 direction=False 为买家，direction=True 为商家。
        direction = message.get("direction")
        if direction is False:
            pair = build_pair()
            if pair is not None:
                yield pair
                question_parts = []
                answer_parts = []
            question_parts.append(text)
        elif direction is True:
            if question_parts:
                answer_parts.append(text)
            else:
                print(f"[清洗] 跳过无买家问题的商家消息：uid={uid}，msgId={message.get('msgId')}")
        else:
            print(
                "[清洗] 跳过无法识别发言方的消息："
                f"uid={uid}，msgId={message.get('msgId')}，direction={direction!r}"
            )

    pair = build_pair()
    if pair is not None:
        yield pair
    elif question_parts:
        print(f"[清洗] uid={uid} 的最后一个问题没有商家回答，未写入。")


def load_sales_products(source: Path) -> list[tuple[str, str]]:
    """读取销售 JSON，返回去重后的 ``(店铺名, 商品ID)``。"""
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


def get_pdd_shops(base_url: str, timeout: int) -> dict[str, dict[str, str]]:
    """按接口文档获取有效 Cookie，返回以店铺名为键的唯一店铺映射。"""
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v1/cookies/",
        params={"platform": "pdd"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("ok") is False:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise PddApiError(f"读取中控 Cookie 失败：{message or '响应格式错误'}")
    raw_shops = payload.get("data")
    if not isinstance(raw_shops, list):
        raise PddApiError("中控 Cookie 接口缺少 data 店铺列表")

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


def scrape_product(
    cookie: Mapping[str, Any],
    shopid: str,
    goodsid: str,
    output_path: Path,
    timeout: int,
) -> Path:
    """抓取单个商品聊天，整理完成后一次性写出一个 JSON 文件。"""
    if not cookie:
        raise ValueError("Cookie 不能为空")
    if timeout <= 0:
        raise ValueError("timeout 必须大于 0")

    start_datetime, end_datetime, start_time, end_time = _time_range()
    output: dict[str, Any] = {
        "shopid": str(shopid),
        "goodsid": str(goodsid),
        "time_range": {
            "start_time": start_time,
            "end_time": end_time,
            "start_time_text": start_datetime.isoformat(),
            "end_time_text": end_datetime.isoformat(),
        },
        "users": {},
    }

    print(f"[商品] 开始抓取：shopid={shopid}，goodsid={goodsid}")
    print(
        "[时间] "
        f"{start_datetime:%Y-%m-%d %H:%M:%S %Z} 至 "
        f"{end_datetime:%Y-%m-%d %H:%M:%S %Z}"
    )
    session = requests.Session()
    session.cookies.update({str(key): str(value) for key, value in cookie.items()})

    print("[用户列表] 请求商品聊天用户列表……")
    users_payload = _post_pdd_json(
        session=session,
        url=GOODS_USERS_URL,
        body={"startTime": start_time, "endTime": end_time, "goodsId": int(goodsid)},
        referer="https://mms.pinduoduo.com/mms-chat/search?msfrom=mms_ai_search_function",
        timeout=timeout,
    )
    result = users_payload.get("result")
    if not isinstance(result, Mapping) or not isinstance(result.get("convUsers"), list):
        raise PddApiError("商品聊天用户接口缺少 convUsers 列表")
    users = result["convUsers"]
    selected_users = users[-MAX_USERS:]
    print(
        f"[用户列表] 返回 {len(users)} 位用户（total={result.get('total')}），"
        f"按原顺序取最后 {len(selected_users)} 位。"
    )

    pair_count = 0
    failed_users = 0
    for index, user in enumerate(selected_users, start=1):
        if not isinstance(user, Mapping) or user.get("uid") is None:
            failed_users += 1
            print(f"[用户 {index}/{len(selected_users)}] 缺少 uid，跳过。")
            continue
        uid = user["uid"]
        nickname = str(user.get("nickname") or "未知买家")
        print(f"[用户 {index}/{len(selected_users)}] 获取 uid={uid}，昵称={nickname} 的聊天……")
        try:
            messages_payload = _post_pdd_json(
                session=session,
                url=MESSAGES_URL,
                body={
                    "uid": uid,
                    "pageSize": MESSAGE_PAGE_SIZE,
                    "startTime": start_time,
                    "endTime": end_time,
                    "msgId": None,
                    "keywords": "",
                },
                referer="https://mms.pinduoduo.com/mms-chat/search?msfrom=mms_globalsearch",
                timeout=timeout,
            )
            message_result = messages_payload.get("result")
            messages = message_result.get("contentList") if isinstance(message_result, Mapping) else None
            if not isinstance(messages, list):
                raise PddApiError("聊天明细接口缺少 contentList 列表")

            print(f"[用户 {index}/{len(selected_users)}] 收到 {len(messages)} 条消息，开始整理。")
            user_pairs = list(iter_qa_pairs(messages, uid))
            if user_pairs:
                user_key = f"{nickname}（uid={uid}）"
                output["users"][user_key] = user_pairs
                pair_count += len(user_pairs)
                print(f"[用户 {index}/{len(selected_users)}] 整理出 {len(user_pairs)} 组问答。")
            else:
                print(f"[用户 {index}/{len(selected_users)}] 没有完整问答。")
        except (requests.RequestException, PddApiError, ValueError) as error:
            failed_users += 1
            print(f"[用户 {index}/{len(selected_users)}] 获取失败，继续下一位：{error}")

    print(f"[保存] 商品整理完成，共 {pair_count} 组问答，写入：{output_path.resolve()}")
    _atomic_save(output_path, output)
    print(f"[商品] 完成：goodsid={goodsid}，失败/跳过用户 {failed_users} 位。")
    return output_path


def main(
    source: Path = DEFAULT_SOURCE,
    base_url: str = DEFAULT_BASE_URL,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    timeout: int = 20,
) -> list[Path]:
    """按销售 JSON 自动获取 Cookie，并批量抓取所有商品聊天问答。"""
    if timeout <= 0:
        raise ValueError("timeout 必须大于 0")
    output_dir.mkdir(parents=True, exist_ok=True)
    products = load_sales_products(source)
    print(f"[开始] 从 {source.resolve()} 读取到 {len(products)} 个去重商品。")
    shops = get_pdd_shops(base_url, timeout)
    print(f"[Cookie] 自动读取到 {len(shops)} 个可唯一匹配的有效拼多多店铺。")

    completed: list[Path] = []
    failures = 0
    for index, (shop_name, goodsid) in enumerate(products, start=1):
        shop = shops.get(shop_name)
        if shop is None:
            failures += 1
            print(f"[商品 {index}/{len(products)}] 找不到店铺 Cookie，跳过：{shop_name} / {goodsid}")
            continue
        shopid = shop["shopid"]
        output_path = output_dir / f"pdd_{shopid}_{goodsid}_qa.json"
        print(f"[商品 {index}/{len(products)}] 店铺={shop_name}，商品={goodsid}")
        try:
            completed.append(
                scrape_product(
                    cookie=_cookie_dict(shop["cookie"]),
                    shopid=shopid,
                    goodsid=goodsid,
                    output_path=output_path,
                    timeout=timeout,
                )
            )
        except (OSError, ValueError, PddApiError, requests.RequestException) as error:
            failures += 1
            print(f"[商品 {index}/{len(products)}] 抓取失败，继续下一商品：{error}")

    print(f"[完成] 已生成 {len(completed)} 个商品 JSON，失败/跳过 {failures} 个商品。")
    return completed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="按拼多多销售商品清单批量抓取聊天问答")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="销售商品 JSON 路径")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="中控服务地址")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="问答 JSON 输出目录（默认：ltjlapi_json）",
    )
    parser.add_argument("--timeout", type=int, default=20, help="单次请求超时秒数")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        main(args.source, args.base_url, args.output_dir, args.timeout)
    except (OSError, ValueError, PddApiError, requests.RequestException) as error:
        print(f"[失败] {error}", file=sys.stderr)
        raise SystemExit(1)
