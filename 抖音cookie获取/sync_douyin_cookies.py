"""常驻验证并上传抖音店铺 Cookie。

启动后立即执行一次，默认每 15 分钟执行一次。单个店铺失败不会中断其他
店铺；Cookie 失效或上传失败时，会尝试创建一个非紧急待处理事项。

示例：
    python sync_douyin_cookies.py
    python sync_douyin_cookies.py --shop-id 29411390
    python sync_douyin_cookies.py --once --shop-id 29411390
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from requests.cookies import RequestsCookieJar

import get_doudian_cookies as cookie_reader


DEFAULT_BASE_URL = "http://117.72.204.36:8000"
SHOP_INFO_URL = "https://fxg.jinritemai.com/center/qualification/shop/info"
FXG_HOST = cookie_reader.FXG_HOST


@dataclass
class ShopCookie:
    shop_id: str
    partition: str
    source_dir: Path
    cookie_header: str
    cookie_jar: RequestsCookieJar


def build_cookie_bundle(
    app_dir: Path,
    master_keys: list[bytes],
    cookie_db: Path,
    shop_id: str,
) -> ShopCookie | None:
    """Decode one store's cookies from one Chromium cookie database."""
    try:
        rows = cookie_reader.snapshot_rows(cookie_db)
    except Exception as exc:
        print(f"[{cookie_db}] 读取失败：{exc}", file=sys.stderr)
        return None

    decoded: list[tuple[str, str, str, str]] = []
    for host, name, path, encrypted, plain, _expires, _secure, _httponly in rows:
        if not cookie_reader.is_cookie_for(host, FXG_HOST):
            continue
        try:
            value = cookie_reader.decrypt_cookie_with_master_keys(
                encrypted or b"",
                plain or "",
                host,
                master_keys,
            )
        except Exception as exc:
            print(f"[{cookie_db}] {host} / {name} 解密失败：{exc}", file=sys.stderr)
            continue
        decoded.append((host, name, path, value))

    store_ids = {
        str(value).strip()
        for _host, name, _path, value in decoded
        if name in {"SHOP_ID", "ecom_gray_shop_id"}
        and cookie_reader.is_plausible_shop_id(value)
    }
    if str(shop_id).strip() not in store_ids:
        return None

    jar = RequestsCookieJar()
    for host, name, path, value in decoded:
        jar.set(name, value, domain=host, path=path or "/")

    cookie_header = "; ".join(f"{name}={value}" for _host, name, _path, value in decoded)
    partition = cookie_reader.cookie_db_partition(cookie_db, app_dir)
    source_dir = cookie_reader.cookie_db_data_dir(cookie_db, app_dir)
    return ShopCookie(shop_id, partition, source_dir, cookie_header, jar)


def collect_shop_cookies(
    app_dir: Path,
    master_keys: list[bytes],
    shop_id: str,
) -> list[ShopCookie]:
    """Return all local cookie DBs containing the requested shop ID."""
    bundles: list[ShopCookie] = []
    for cookie_db in cookie_reader.discover_cookie_dbs(app_dir):
        bundle = build_cookie_bundle(app_dir, master_keys, cookie_db, shop_id)
        if bundle:
            bundles.append(bundle)
    return bundles


def collect_all_shop_cookies(
    app_dir: Path,
    master_keys: list[bytes],
) -> dict[str, list[ShopCookie]]:
    """Decode every local Cookie DB once and group bundles by shop ID."""
    grouped: dict[str, list[ShopCookie]] = {}
    for cookie_db in cookie_reader.discover_cookie_dbs(app_dir):
        try:
            rows = cookie_reader.snapshot_rows(cookie_db)
        except Exception as exc:
            print(f"[{cookie_db}] 读取失败：{exc}", file=sys.stderr)
            continue

        decoded: list[tuple[str, str, str, str]] = []
        for host, name, path, encrypted, plain, _expires, _secure, _httponly in rows:
            if not cookie_reader.is_cookie_for(host, FXG_HOST):
                continue
            try:
                value = cookie_reader.decrypt_cookie_with_master_keys(
                    encrypted or b"",
                    plain or "",
                    host,
                    master_keys,
                )
            except Exception as exc:
                print(
                    f"[{cookie_db}] {host} / {name} 解密失败：{exc}",
                    file=sys.stderr,
                )
                continue
            decoded.append((host, name, path, value))

        shop_ids = {
            str(value).strip()
            for _host, name, _path, value in decoded
            if name in {"SHOP_ID", "ecom_gray_shop_id"}
            and cookie_reader.is_plausible_shop_id(value)
        }
        if not shop_ids:
            continue

        jar = RequestsCookieJar()
        for host, name, path, value in decoded:
            jar.set(name, value, domain=host, path=path or "/")

        cookie_header = "; ".join(
            f"{name}={value}" for _host, name, _path, value in decoded
        )
        partition = cookie_reader.cookie_db_partition(cookie_db, app_dir)
        source_dir = cookie_reader.cookie_db_data_dir(cookie_db, app_dir)
        for shop_id in shop_ids:
            grouped.setdefault(shop_id, []).append(
                ShopCookie(shop_id, partition, source_dir, cookie_header, jar)
            )

    return grouped


def discover_local_shop_ids(
    app_dir: Path,
    master_keys: list[bytes],
) -> set[str]:
    """Read shop IDs from local Cookie DBs before using saved metadata."""
    return set(collect_all_shop_cookies(app_dir, master_keys))


def choose_bundle(
    bundles: list[ShopCookie],
    shop_info: dict[str, dict[str, str]],
    shop_id: str,
    preferred_source_dir: Path | None = None,
) -> ShopCookie | None:
    """Prefer the account's persist partition over the default root session."""
    if not bundles:
        return None

    candidates = bundles
    if preferred_source_dir is not None:
        preferred_key = str(preferred_source_dir.resolve()).lower()
        same_dir = [
            bundle
            for bundle in bundles
            if str(bundle.source_dir.resolve()).lower() == preferred_key
        ]
        if same_dir:
            candidates = same_dir

    expected_account = shop_info.get(shop_id, {}).get("account_id", "")
    expected_partition = f"Partitions\\{expected_account}" if expected_account else ""
    for bundle in candidates:
        if bundle.partition.replace("/", "\\") == expected_partition:
            return bundle

    return candidates[0]


def validate_shop(bundle: ShopCookie, timeout: float) -> tuple[bool, dict[str, Any], str]:
    """Ask Douyin for shop information and determine whether the Cookie works."""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "referer": "https://fxg.jinritemai.com/ffa/grs-new/qualification/personal-info",
        "sec-ch-ua": '"Google Chrome";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
    }
    params = {"version": "0", "appid": "1", "_bid": "fxg_admin"}

    try:
        response = requests.get(
            SHOP_INFO_URL,
            headers=headers,
            cookies=bundle.cookie_jar,
            params=params,
            timeout=timeout,
        )
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return False, {}, f"店铺信息请求失败：{exc}"

    message = str(body.get("msg") or body.get("message") or "")
    data = body.get("data")

    if response.status_code >= 400:
        return (
            False,
            {},
            f"店铺信息 HTTP {response.status_code}：{message or response.text[:200]}",
        )

    if "失效" in message or "重新登录" in message:
        return False, {}, message

    if not isinstance(data, dict) or not data.get("shop_name"):
        return False, {}, message or "店铺信息接口未返回有效店铺数据"

    return True, data, ""


def upload_cookie(
    base_url: str,
    shop_id: str,
    shop_name: str,
    cookie_header: str,
    main_category: str,
    cookie_status: str,
    timeout: float,
) -> tuple[bool, str]:
    payload = {
        "platform": "douyin",
        "shop_id": shop_id,
        "shop_name": shop_name,
        "cookie": cookie_header,
        "main_category": main_category or "notfind",
        "cookie_status": cookie_status,
    }
    url = f"{base_url.rstrip('/')}/api/v1/cookies/upsert/"

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return False, f"上传请求失败：{exc}"

    if response.status_code >= 400 or body.get("ok") is False:
        return False, f"上传失败 HTTP {response.status_code}：{body}"
    return True, str(body)


def create_pending_task(
    base_url: str,
    shop_id: str,
    shop_name: str,
    reason: str,
    timeout: float,
) -> tuple[bool, str]:
    """Create a normal-priority pending task for a failed shop update."""
    payload = {
        "shop_id": shop_id,
        "platform": "douyin",
        "time_type": "normal",
        "handling_item": f"店铺 {shop_name} Cookie 自动更新失败：{reason}",
    }
    url = f"{base_url.rstrip('/')}/api/v1/pending-tasks/create/"

    try:
        response = requests.post(url, json=payload, timeout=timeout)
        body = response.json()
    except (requests.RequestException, ValueError) as exc:
        return False, f"待处理事项创建失败：{exc}"

    if response.status_code >= 400 or body.get("ok") is False:
        return False, f"待处理事项创建失败 HTTP {response.status_code}：{body}"
    return True, str(body)


def resolve_shop_ids(
    args: argparse.Namespace,
    shop_info: dict[str, dict[str, str]],
    local_shop_ids: set[str] | None = None,
) -> list[str]:
    """Select shop IDs, matching 1.1.9's shop-level sync behavior."""
    if args.all and (args.shop_id or args.shop_name):
        raise ValueError("--all 不能和 --shop-id/--shop-name 同时使用")

    selected = [
        str(value).strip()
        for value in (args.shop_id or [])
        if cookie_reader.is_plausible_shop_id(value)
    ]

    for name in args.shop_name or []:
        matched = [
            shop_id
            for shop_id, info in shop_info.items()
            if info.get("name") == name
        ]
        if not matched:
            raise ValueError(f"未在 config.json 中找到店铺名称：{name}")
        selected.extend(matched)

    if args.all or not selected:
        # The Cookie DB is authoritative for automatic/all mode.  Metadata
        # is only a fallback for installations where the DB is not readable.
        selected = sorted(local_shop_ids or set())
        if not selected:
            selected = [
                shop_id
                for shop_id in shop_info
                if cookie_reader.is_plausible_shop_id(shop_id)
            ]
        if not selected:
            raise ValueError("未找到可用的店铺 Cookie 或店铺列表")

    return list(dict.fromkeys(selected))


def process_shop(
    app_dir: Path,
    master_keys: list[bytes],
    shop_id: str,
    shop_info: dict[str, dict[str, str]],
    base_url: str,
    timeout: float,
    bundles_by_shop: dict[str, list[ShopCookie]] | None = None,
    preferred_source_dir: Path | None = None,
) -> tuple[bool, str]:
    """Process one shop; exceptions are converted to a skip-able failure."""
    configured_name = shop_info.get(shop_id, {}).get("name", "")

    try:
        if bundles_by_shop is None:
            bundles = collect_shop_cookies(app_dir, master_keys, shop_id)
        else:
            bundles = bundles_by_shop.get(shop_id, [])
        bundle = choose_bundle(
            bundles,
            shop_info,
            shop_id,
            preferred_source_dir,
        )
    except Exception as exc:
        return False, f"Cookie 读取失败：{exc}"

    if not bundle:
        return False, "没有找到本地 Cookie"

    valid, data, validation_error = validate_shop(bundle, timeout)
    shop_name = str(data.get("shop_name") or configured_name or f"店铺 {shop_id}")
    main_category = str(data.get("main_category") or "notfind")
    status = "valid" if valid else "invalid"

    print(f"[{shop_id}] 分区={bundle.partition} 店铺={shop_name} Cookie状态={status}")
    if validation_error:
        print(f"[{shop_id}] {validation_error}", file=sys.stderr)

    if not valid:
        print(f"[{shop_id}] 店铺状态无效，跳过 Cookie 上传", file=sys.stderr)
        return False, validation_error or "店铺状态无效"

    uploaded, message = upload_cookie(
        base_url,
        shop_id,
        shop_name,
        bundle.cookie_header,
        main_category,
        status,
        timeout,
    )
    if not uploaded:
        return False, message

    print(f"[{shop_id}] Cookie 状态上传成功：{message}")
    if not valid:
        return False, validation_error or "Cookie 已失效，请重新登录后更新"

    return True, ""


def run_once(
    app_dir: Path,
    master_keys: list[bytes],
    shop_ids: list[str],
    shop_info: dict[str, dict[str, str]],
    base_url: str,
    timeout: float,
    pending_created: set[str],
    bundles_by_shop: dict[str, list[ShopCookie]] | None = None,
) -> tuple[int, int]:
    succeeded = 0
    failed = 0
    preferred_source_dir: Path | None = None

    for shop_id in shop_ids:
        if bundles_by_shop is not None and preferred_source_dir is None:
            first_bundle = choose_bundle(
                bundles_by_shop.get(shop_id, []),
                shop_info,
                shop_id,
            )
            if first_bundle is not None:
                preferred_source_dir = first_bundle.source_dir
        try:
            success, reason = process_shop(
                app_dir,
                master_keys,
                shop_id,
                shop_info,
                base_url,
                timeout,
                bundles_by_shop,
                preferred_source_dir,
            )
        except Exception as exc:
            success, reason = False, f"处理异常：{exc}"

        if success:
            succeeded += 1
            pending_created.discard(shop_id)
            continue

        failed += 1
        print(f"[{shop_id}] 跳过本轮：{reason}", file=sys.stderr)
        if reason == "没有找到本地 Cookie":
            # A missing local Cookie is a local-data mismatch, not a server
            # task.  Do not send a stale/random shop ID to that endpoint.
            continue
        if shop_id in pending_created:
            continue

        shop_name = shop_info.get(shop_id, {}).get("name", f"店铺 {shop_id}")
        task_ok, task_message = create_pending_task(
            base_url,
            shop_id,
            shop_name,
            reason,
            timeout,
        )
        if task_ok:
            pending_created.add(shop_id)
            print(f"[{shop_id}] 已创建非紧急待处理事项：{task_message}")
            continue

        print(f"[{shop_id}] {task_message}", file=sys.stderr)

    print(f"本轮完成：成功 {succeeded}，跳过/失败 {failed}")
    return succeeded, failed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="常驻验证并上传抖音店铺 Cookie")
    parser.add_argument("--shop-id", action="append", help="店铺 ID，可重复指定")
    parser.add_argument("--shop-name", action="append", help="店铺名称，可重复指定")
    parser.add_argument("--all", action="store_true", help="上传全部已保存店铺（默认行为）")
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"中控平台地址（默认 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=None,
        help="抖店工作台数据目录；不指定时自动探测（1.1.11 便携版一般在安装盘根目录，如 D:\\抖店）",
    )
    parser.add_argument("--timeout", type=float, default=20.0, help="单次请求超时时间（秒）")
    parser.add_argument("--interval", type=float, default=900.0, help="执行间隔，默认 900 秒")
    parser.add_argument("--once", action="store_true", help="只执行一轮后退出，便于测试")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_dir = cookie_reader.resolve_app_dir(args.app_dir)
    if not app_dir.is_dir():
        print(f"未找到抖店工作台数据目录：{app_dir}", file=sys.stderr)
        return 1

    print(f"使用数据目录：{app_dir}")
    if args.interval <= 0:
        print("--interval 必须大于 0", file=sys.stderr)
        return 2

    try:
        master_keys = cookie_reader.load_master_keys(app_dir)
    except Exception as exc:
        print(f"读取 Windows 解密密钥失败：{exc}", file=sys.stderr)
        return 1

    pending_created: set[str] = set()
    try:
        while True:
            shop_info = cookie_reader.load_shop_info(app_dir)
            bundles_by_shop = collect_all_shop_cookies(app_dir, master_keys)
            local_shop_ids = set(bundles_by_shop)
            shop_ids = resolve_shop_ids(args, shop_info, local_shop_ids)
            run_once(
                app_dir,
                master_keys,
                shop_ids,
                shop_info,
                args.base_url,
                args.timeout,
                pending_created,
                bundles_by_shop,
            )
            if args.once:
                return 0

            print(f"下一轮将在 {args.interval:g} 秒后开始；按 Ctrl+C 停止。")
            time.sleep(args.interval)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("已停止。")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
