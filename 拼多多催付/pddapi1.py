"""拼多多待支付订单自动催付。

运行前，在同级 ``shop.json`` 中填写一个或多个店铺名，例如：

    {"shops": ["蘑菇头旗舰店", "示例店铺"]}

脚本启动时和每完成 12 轮后，都会从中控平台读取该店铺的机器人
Cookie。每轮只读取待支付订单的第一页，并且只会对 ``sum == 1``、
有待支付话术、且未在本地 SQLite 中记录过的订单发送一次文字消息。

默认常驻运行；用 ``python pddapi1.py --once`` 可只执行一轮，便于验证
配置而不进入五分钟循环。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sqlite3
import string
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import execjs
import requests


# onefile EXE 会在临时目录解包 Python 文件；配置、anti 和 SQLite 必须始终
# 从 EXE 所在目录读取，而不是临时解包目录读取。
if getattr(sys, "frozen", False):
    ROOT = Path(sys.executable).resolve().parent
    bundle_dir = Path(getattr(sys, "_MEIPASS", ROOT))
    # 打包时会把 node.exe 放在解包根目录，让 execjs 能找到内置 JS 运行时。
    os.environ["PATH"] = str(bundle_dir) + os.pathsep + os.environ.get("PATH", "")
else:
    ROOT = Path(__file__).resolve().parent

SHOP_FILE = ROOT / "shop.json"
ANTI_FILE = ROOT / "anti.js"
DB_FILE = ROOT / "urge_sent.sqlite3"

PLATFORM_URL = "http://117.72.204.36:8000"
PDD_URL = "https://mms.pinduoduo.com"
PLATFORM_NAME = "pdd"
PAGE_SIZE = 10                 # 严格与 ces2 一致：只取第一页的 10 条，不翻页。
INTERVAL_SECONDS = 5 * 60
COOKIE_REFRESH_EVERY = 12      # 第 13 轮开始前刷新 Cookie。
RECORD_RETENTION_SECONDS = 7 * 24 * 60 * 60
REQUEST_TIMEOUT = 15

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/157.0.0.0 Safari/537.36"
)


class ConfigurationError(RuntimeError):
    """本地配置或中控平台返回的数据无法使用。"""


class PlatformApiError(RuntimeError):
    """中控平台接口调用失败。"""


class PddApiError(RuntimeError):
    """拼多多接口调用失败。``auth_failed`` 表示应刷新 Cookie 后重试。"""

    def __init__(self, message: str, *, auth_failed: bool = False) -> None:
        super().__init__(message)
        self.auth_failed = auth_failed


@dataclass(frozen=True)
class ShopCookie:
    name: str
    shop_id: str
    cookie: str


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_shop_names() -> list[str]:
    """读取一个或多个店铺名，兼容旧的单店配置。"""
    try:
        raw = json.loads(SHOP_FILE.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"缺少店铺配置文件：{SHOP_FILE}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"{SHOP_FILE.name} 不是有效 JSON，请填写 {{\"shop_name\": \"店铺名\"}}"
        ) from exc

    if isinstance(raw, str):
        values: Any = [raw]
    elif isinstance(raw, list):
        values = raw
    elif isinstance(raw, dict):
        # 推荐 {"shops": ["店铺 A", "店铺 B"]}，也兼容旧的单店格式。
        values = (
            raw.get("shops")
            or raw.get("shop_names")
            or raw.get("店铺列表")
            or raw.get("shop_name")
            or raw.get("shop")
            or raw.get("店铺名")
        )
        if isinstance(values, str):
            values = [values]
    else:
        values = None

    if not isinstance(values, list):
        raise ConfigurationError(
            f"{SHOP_FILE.name} 必须包含店铺名，例如 {{\"shops\": [\"店铺 A\", \"店铺 B\"]}}"
        )

    names: list[str] = []
    for item in values:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(
                item.get("shop_name") or item.get("shop") or item.get("店铺名") or ""
            ).strip()
        else:
            name = ""
        if name and name not in names:
            names.append(name)
    if not names:
        raise ConfigurationError(f"{SHOP_FILE.name} 中没有有效店铺名")
    return names


class PlatformClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()

    def get_robot_cookies(self, shop_names: list[str]) -> dict[str, ShopCookie]:
        """一次读取机器人 Cookie 列表，并按店铺名精确匹配全部配置店铺。"""
        url = f"{self.base_url}/api/v1/robot-cookies/"
        try:
            response = self.session.get(
                url, params={"platform": PLATFORM_NAME}, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PlatformApiError(f"读取机器人 Cookie 失败：{exc}") from exc

        if isinstance(payload, dict) and payload.get("ok") is False:
            raise PlatformApiError(payload.get("message") or "机器人 Cookie 接口返回失败")

        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise PlatformApiError("机器人 Cookie 接口未返回 data 列表")

        result: dict[str, ShopCookie] = {}
        for shop_name in shop_names:
            matches = [
                item for item in data
                if isinstance(item, dict) and str(item.get("shop_name", "")).strip() == shop_name
            ]
            if not matches:
                raise ConfigurationError(f"机器人 Cookie 中未找到店铺名：{shop_name}")
            if len(matches) > 1:
                raise ConfigurationError(
                    f"机器人 Cookie 中存在多个同名店铺“{shop_name}”，无法唯一选择"
                )

            item = matches[0]
            shop_id = str(item.get("shop_id") or "").strip()
            cookie = str(item.get("cookie") or "").strip()
            if not shop_id or not cookie:
                raise PlatformApiError(f"店铺“{shop_name}”缺少 shop_id 或机器人 Cookie")
            result[shop_name] = ShopCookie(name=shop_name, shop_id=shop_id, cookie=cookie)
        return result

    def get_store_pending_payment_script(self, shop_id: str) -> str | None:
        """读取店铺层面最终生效的待支付话术（含客户继承的话术）。"""
        url = f"{self.base_url}/api/v1/ai/order-urging-scripts/store/"
        try:
            response = self.session.get(
                url,
                params={"store_id": shop_id, "platform": PLATFORM_NAME},
                timeout=REQUEST_TIMEOUT,
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise PlatformApiError(f"读取店铺待支付话术失败：{exc}") from exc

        if isinstance(payload, dict) and payload.get("ok") is False:
            raise PlatformApiError(payload.get("message") or "店铺待支付话术接口返回失败")
        data = payload.get("data") if isinstance(payload, dict) else None
        text = data.get("pending_payment") if isinstance(data, dict) else None
        if text is None:
            return None
        text = str(text).strip()
        return text if text and text != "无" else None


class AntiGenerator:
    """复用 pddapi1 原本的 anti.js，所有拼多多请求均由这里生成 anti。"""

    def __init__(self, js_file: Path) -> None:
        try:
            source = js_file.read_text(encoding="utf-8")
            self.context = execjs.compile(source)
        except Exception as exc:  # execjs 的异常类型随 JS 运行时实现变化。
            raise ConfigurationError(f"加载 anti.js 失败：{exc}") from exc

    def new(self) -> str:
        try:
            # 严格与 ces2 一致：不向 get_anti 传入参数。
            anti = str(self.context.call("get_anti"))
        except Exception as exc:
            raise PddApiError(f"生成 anti-content 失败：{exc}") from exc
        if not anti or anti == "None":
            raise PddApiError("生成的 anti-content 为空")
        return anti


def md5_custom(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def make_random(mall_uid: Any, buyer_uid: Any, text: str) -> str:
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(random.choices(chars, k=16))
    base = "@".join([str(mall_uid), str(buyer_uid), str(text), "rpZigw#&iy$!KQD8"])
    return md5_custom(base)[:16] + md5_custom(random_part)[:16]


def make_hash(buyer_uid: Any, request_id: int) -> str:
    text = f"uid={buyer_uid}&mall_id=undefined&request_id={request_id}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pdd_headers(anti: str) -> dict[str, str]:
    """严格复用 ces2 的请求头；Cookie 由 requests 的 cookies 参数传递。"""
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,
        "content-type": "application/json",
        "priority": "u=1, i",
        "referer": f"{PDD_URL}/chat-merchant/",
        "sec-ch-ua": "\"Not-A.Brand\";v=\"99\", \"Google Chrome\";v=\"157\", \"Chromium\";v=\"157\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA,
    }


def pdd_cookies(cookie_text: str) -> dict[str, str]:
    """把中控保存的完整 Cookie 字符串转换为 ces2 使用的 cookies 字典。"""
    result: dict[str, str] = {}
    for part in cookie_text.split(";"):
        if "=" not in part:
            continue
        key, value = part.strip().split("=", 1)
        if key:
            result[key] = value
    if not result:
        raise PddApiError("机器人 Cookie 格式为空或无法解析")
    return result


def is_auth_failure(response: requests.Response, payload: Any | None = None) -> bool:
    if response.status_code in (401, 403):
        return True
    if payload is None:
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
    if isinstance(payload, dict):
        message = " ".join(
            str(payload.get(key) or "") for key in ("errorMsg", "message", "msg")
        )
    else:
        message = str(payload)
    message = message.lower()
    return any(word in message for word in ("cookie", "session", "登录", "登陆", "login", "未登录"))


class RobotCookieProvider:
    """多个店铺共享一次机器人 Cookie 列表请求。"""

    def __init__(self, platform: PlatformClient, shop_names: list[str]) -> None:
        self.platform = platform
        self.shop_names = shop_names
        self.shops: dict[str, ShopCookie] = {}

    def refresh_all(self, reason: str) -> None:
        self.shops = self.platform.get_robot_cookies(self.shop_names)
        logging.info("已刷新 %d 个店铺的机器人 Cookie（%s）", len(self.shops), reason)

    def get(self, shop_name: str) -> ShopCookie:
        try:
            return self.shops[shop_name]
        except KeyError as exc:
            raise ConfigurationError(f"店铺“{shop_name}”尚未读取到机器人 Cookie") from exc


class PddClient:
    def __init__(
        self, anti_generator: AntiGenerator, cookie_provider: RobotCookieProvider, shop_name: str
    ) -> None:
        self.anti_generator = anti_generator
        self.cookie_provider = cookie_provider
        self.shop_name = shop_name
        self._anti: str | None = None
        self._anti_cookie: str | None = None

    def refresh_cookie(self, reason: str) -> ShopCookie:
        self.cookie_provider.refresh_all(reason)
        return self.cookie_provider.get(self.shop_name)

    def _require_shop(self) -> ShopCookie:
        if not self.cookie_provider.shops:
            return self.refresh_cookie("启动")
        return self.cookie_provider.get(self.shop_name)

    def current_shop(self) -> ShopCookie:
        return self._require_shop()

    def _anti_for(self, shop: ShopCookie) -> str:
        # ces2 在同一 Cookie 会话内只生成一次 anti；Cookie 被刷新后才重新生成。
        if self._anti is None or self._anti_cookie != shop.cookie:
            self._anti = self.anti_generator.new()
            self._anti_cookie = shop.cookie
        return self._anti

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        shop = self._require_shop()
        anti = self._anti_for(shop)
        try:
            response = requests.request(
                method,
                f"{PDD_URL}{path}",
                headers=pdd_headers(anti),
                cookies=pdd_cookies(shop.cookie),
                params=params,
                json=body,
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise PddApiError(f"拼多多请求异常：{exc}") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not response.ok:
            detail = "HTTP " + str(response.status_code)
            if isinstance(payload, dict):
                detail += f" {payload.get('errorMsg') or payload.get('message') or ''}".rstrip()
            raise PddApiError(detail, auth_failed=is_auth_failure(response, payload))
        if not isinstance(payload, dict):
            raise PddApiError("拼多多接口未返回 JSON 对象", auth_failed=is_auth_failure(response, payload))
        if payload.get("success") is False:
            detail_parts = [
                str(payload.get("errorMsg") or payload.get("message") or "接口返回 success=false")
            ]
            if payload.get("errorCode") not in (None, ""):
                detail_parts.append(f"errorCode={payload['errorCode']}")
            # 只输出服务端错误结果，不记录 Cookie、请求头或待发送内容。
            if payload.get("result") not in (None, ""):
                detail_parts.append(f"result={payload['result']!r}")
            detail = "；".join(detail_parts)
            raise PddApiError(detail, auth_failed=is_auth_failure(response, payload))
        return payload

    def _with_cookie_retry(self, action: Callable[[], Any]) -> Any:
        try:
            return action()
        except PddApiError as exc:
            if not exc.auth_failed:
                raise
            logging.warning("检测到 Cookie 可能失效，立即刷新并重试一次：%s", exc)
            self.refresh_cookie("Cookie 失效")
            return action()

    def unpaid_orders(self) -> list[dict[str, Any]]:
        def action() -> list[dict[str, Any]]:
            payload = self._request_json(
                "GET", "/chats/unpaidOrders", params={"pageNo": "1", "pageSize": str(PAGE_SIZE)}
            )
            orders = payload.get("orders", [])
            if not isinstance(orders, list):
                raise PddApiError("待支付订单接口的 orders 字段不是列表")
            return [item for item in orders if isinstance(item, dict)]

        return self._with_cookie_retry(action)

    def order_sum_is_one(self, buyer_uid: Any) -> bool:
        def action() -> bool:
            payload = self._request_json(
                "POST", "/latitude/order/userOrderQuantity", body={"uid": str(buyer_uid)}
            )
            result = payload.get("result")
            if not isinstance(result, dict):
                raise PddApiError("订单数量接口未返回 result")
            try:
                return int(result.get("sum")) == 1
            except (TypeError, ValueError):
                raise PddApiError(f"订单数量接口的 sum 非法：{result.get('sum')!r}") from None

        return bool(self._with_cookie_retry(action))

    def send_text(self, mall_uid: Any, buyer_uid: Any, content: str) -> None:
        def action() -> None:
            shop = self._require_shop()
            anti = self._anti_for(shop)
            request_id = int(time.time() * 1000)
            data = {
                "data": {
                    "cmd": "send_message",
                    "request_id": request_id,
                    "message": {
                        "to": {"role": "user", "uid": str(buyer_uid)},
                        "from": {"role": "mall_cs"},
                        "ts": int(time.time()),
                        "content": content,
                        "msg_id": None,
                        "type": 0,
                        "is_aut": 0,
                        "manual_reply": 1,
                        "status": "read",
                        "is_read": 1,
                        "hash": make_hash(buyer_uid, request_id),
                    },
                    "random": make_random(mall_uid, buyer_uid, content),
                },
                "client": "WEB",
                "anti_content": anti,
            }
            try:
                response = requests.post(
                    f"{PDD_URL}/plateau/chat/send_message",
                    headers=pdd_headers(anti),
                    cookies=pdd_cookies(shop.cookie),
                    json=data,
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as exc:
                raise PddApiError(f"发送消息请求异常：{exc}") from exc
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if not response.ok:
                raise PddApiError(
                    f"发送消息失败：HTTP {response.status_code}",
                    auth_failed=is_auth_failure(response, payload),
                )
            if not isinstance(payload, dict):
                raise PddApiError("发送消息接口未返回 JSON", auth_failed=is_auth_failure(response, payload))
            if payload.get("success") is not True:
                raise PddApiError(
                    f"发送消息失败：{payload.get('errorMsg') or payload.get('message') or payload}",
                    auth_failed=is_auth_failure(response, payload),
                )
            result = payload.get("result")
            if isinstance(result, dict) and result.get("result") not in (None, "ok"):
                raise PddApiError(f"发送消息失败：{result}")

        self._with_cookie_retry(action)


class SentOrderStore:
    def __init__(self, path: Path) -> None:
        self.connection = sqlite3.connect(path)
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sent_orders (
                shop_id TEXT NOT NULL,
                order_sn TEXT NOT NULL,
                buyer_uid TEXT NOT NULL,
                goods_id TEXT,
                script TEXT NOT NULL,
                sent_at INTEGER NOT NULL,
                PRIMARY KEY (shop_id, order_sn)
            )
            """
        )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sent_orders_sent_at ON sent_orders(sent_at)"
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def cleanup_old_records(self) -> int:
        cutoff = int(time.time()) - RECORD_RETENTION_SECONDS
        cursor = self.connection.execute("DELETE FROM sent_orders WHERE sent_at < ?", (cutoff,))
        self.connection.commit()
        return cursor.rowcount

    def contains(self, shop_id: str, order_sn: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sent_orders WHERE shop_id = ? AND order_sn = ?", (shop_id, order_sn)
        ).fetchone()
        return row is not None

    def add(
        self, shop_id: str, order_sn: str, buyer_uid: Any, goods_id: Any, script: str
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO sent_orders (shop_id, order_sn, buyer_uid, goods_id, script, sent_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (shop_id, order_sn, str(buyer_uid), str(goods_id or ""), script, int(time.time())),
        )
        self.connection.commit()


class UrgeRunner:
    def __init__(self, platform: PlatformClient, pdd: PddClient, store: SentOrderStore) -> None:
        self.platform = platform
        self.pdd = pdd
        self.store = store

    def run_cycle(self) -> None:
        removed = self.store.cleanup_old_records()
        if removed:
            logging.info("已清理 %d 条超过 7 天的发送记录", removed)

        try:
            orders = self.pdd.unpaid_orders()
        except (PddApiError, PlatformApiError, ConfigurationError) as exc:
            logging.error("读取待支付订单失败：%s", exc)
            return

        logging.info("本轮读取到 %d 个待支付订单（仅第一页）", len(orders))
        sent = skipped = 0
        # 店铺话术对本轮所有订单相同；首次需要时只读一次中控接口。
        store_script_checked = False
        store_script: str | None = None
        for order in orders:
            shop = self.pdd.current_shop()
            order_sn = str(order.get("orderSn") or "").strip()
            buyer_uid = order.get("uid")
            goods = order.get("orderGoodsList")
            goods_id = goods.get("goodsId") if isinstance(goods, dict) else None
            mall_uid = order.get("mallId")

            if not order_sn or buyer_uid in (None, "") or not mall_uid:
                logging.warning("订单缺少 orderSn、uid 或 mallId，跳过：%s", order_sn or "未知订单")
                skipped += 1
                continue
            if self.store.contains(shop.shop_id, order_sn):
                logging.info("订单 %s 已发送过，跳过", order_sn)
                skipped += 1
                continue

            try:
                if not self.pdd.order_sum_is_one(buyer_uid):
                    logging.info("订单 %s 的买家总订单数不等于 1，跳过", order_sn)
                    skipped += 1
                    continue

                if not store_script_checked:
                    store_script_checked = True
                    try:
                        store_script = self.platform.get_store_pending_payment_script(shop.shop_id)
                    except PlatformApiError as exc:
                        logging.error("店铺 %s 读取待支付话术失败：%s", shop.name, exc)

                if not store_script:
                    logging.info("店铺 %s 未配置待支付话术或读取失败，订单 %s 跳过", shop.name, order_sn)
                    skipped += 1
                    continue

                self.pdd.send_text(mall_uid, buyer_uid, store_script)
                self.store.add(shop.shop_id, order_sn, buyer_uid, goods_id, store_script)
                logging.info("订单 %s 已成功发送待支付话术", order_sn)
                sent += 1
            except (PddApiError, PlatformApiError, sqlite3.Error) as exc:
                # 没有写入 SQLite，后续轮次仍会尝试该订单。
                logging.error("处理订单 %s 失败：%s", order_sn, exc)

        logging.info("本轮结束：成功发送 %d，跳过 %d", sent, skipped)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="拼多多待支付订单自动催付")
    parser.add_argument("--once", action="store_true", help="只执行一轮，不进入五分钟循环")
    parser.add_argument(
        "--interval",
        type=int,
        default=INTERVAL_SECONDS,
        help="轮询间隔秒数（默认 300）",
    )
    parser.add_argument(
        "--platform-url",
        default=PLATFORM_URL,
        help=f"中控平台地址（默认 {PLATFORM_URL}）",
    )
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error("--interval 必须大于 0")
    return args


def main() -> None:
    args = parse_args()
    setup_logging()
    shop_names = load_shop_names()
    platform = PlatformClient(args.platform_url)
    anti_generator = AntiGenerator(ANTI_FILE)
    cookie_provider = RobotCookieProvider(platform, shop_names)
    pdd_clients = [
        PddClient(anti_generator, cookie_provider, shop_name) for shop_name in shop_names
    ]
    store = SentOrderStore(DB_FILE)
    runners = [UrgeRunner(platform, pdd, store) for pdd in pdd_clients]

    completed_cycles = 0
    try:
        cookie_provider.refresh_all("启动")
        while True:
            if completed_cycles and completed_cycles % COOKIE_REFRESH_EVERY == 0:
                # 第 13、25…轮开始前读取一次，满足“运行 12 次后更换”。
                try:
                    cookie_provider.refresh_all("已完成 12 轮")
                except (ConfigurationError, PlatformApiError) as exc:
                    # 保留当前 Cookie，不用每轮都访问中控；下一轮会再次尝试刷新。
                    logging.error("定期刷新机器人 Cookie 失败：%s", exc)
                    if args.once:
                        break
                    logging.info("等待 %d 秒后重试刷新 Cookie", args.interval)
                    time.sleep(args.interval)
                    continue
            for runner in runners:
                runner.run_cycle()
            completed_cycles += 1
            if args.once:
                break
            logging.info("等待 %d 秒后执行下一轮", args.interval)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        logging.info("已停止")
    except (ConfigurationError, PlatformApiError) as exc:
        logging.error("启动失败：%s", exc)
    finally:
        store.close()


if __name__ == "__main__":
    main()
