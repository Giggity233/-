"""读取中控平台保存的京东机器人 Cookie。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

import requests


DEFAULT_API_BASE_URL = "http://117.72.204.36:8000/api/v1"
DEFAULT_PLATFORM = "jingdong"


class RobotCookieApiError(RuntimeError):
    """中控平台 Cookie 接口不可用或返回格式异常。"""


@dataclass(frozen=True)
class Customer:
    id: str
    name: str


@dataclass(frozen=True)
class RobotCookieShop:
    key: str
    shop_id: str
    shop_name: str
    customer_name: str
    cookie: str
    cookie_status: str
    human_account_id: str = ""
    human_account_name: str = ""

    @property
    def can_start(self) -> bool:
        return bool(self.cookie) and self.cookie_status in {"", "valid"}


class RobotCookieApi:
    def __init__(
        self,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        session: Optional[requests.Session] = None,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self._customers_cache: list[Customer] | None = None
        self._shops_cache: dict[tuple[str, str], list[RobotCookieShop]] = {}

    def list_customers(self) -> list[Customer]:
        if self._customers_cache is not None:
            return list(self._customers_cache)
        payload = self._get_json("{}/customers/".format(self.base_url))
        rows = self._response_rows(payload, "客户")
        customers: list[Customer] = []
        for row in rows:
            customer_id = str(row.get("id") or "").strip()
            customer_name = str(row.get("name") or "").strip()
            if customer_id and customer_name:
                customers.append(Customer(id=customer_id, name=customer_name))
        self._customers_cache = customers
        return list(customers)

    def list_customers_with_robot_shops(
        self,
        *,
        platform: str = DEFAULT_PLATFORM,
    ) -> list[Customer]:
        """仅返回至少拥有一间当前平台机器人店铺的启用客户。"""
        customers = self.list_customers()
        shops = self.list_shops(platform=platform)
        customer_names = {shop.customer_name for shop in shops if shop.customer_name}
        return [customer for customer in customers if customer.name in customer_names]

    def list_shops(
        self,
        *,
        platform: str = DEFAULT_PLATFORM,
        customer_id: str | int | None = None,
    ) -> list[RobotCookieShop]:
        normalized_platform = str(platform).strip()
        normalized_customer_id = "" if customer_id is None else str(customer_id).strip()
        cache_key = (normalized_platform, normalized_customer_id)
        cached = self._shops_cache.get(cache_key)
        if cached is not None:
            return list(cached)

        # 首次已读取全量店铺时，按客户从内存筛选，避免再请求中控接口。
        all_shops = self._shops_cache.get((normalized_platform, ""))
        if normalized_customer_id and all_shops is not None:
            customer_name = self._customer_name(normalized_customer_id)
            if customer_name:
                shops = [shop for shop in all_shops if shop.customer_name == customer_name]
                self._shops_cache[cache_key] = shops
                return list(shops)

        params: dict[str, str | int] = {"platform": platform}
        if customer_id is not None:
            params["customer_id"] = customer_id
        payload = self._get_json(
            "{}/robot-cookies/".format(self.base_url),
            params=params,
        )
        rows = self._response_rows(payload, "机器人 Cookie")
        human_accounts_by_shop = self._human_accounts_by_shop(
            platform=platform,
            customer_id=customer_id,
        )

        shops: list[RobotCookieShop] = []
        for index, row in enumerate(rows):
            shop_id = str(row.get("shop_id") or "").strip()
            source_id = str(row.get("id") or shop_id or index).strip()
            if not source_id:
                continue
            human_account_id, human_account_name = human_accounts_by_shop.get(shop_id, ("", ""))
            shops.append(
                RobotCookieShop(
                    key=source_id,
                    shop_id=shop_id or source_id,
                    shop_name=str(row.get("shop_name") or shop_id or source_id).strip(),
                    customer_name=str(
                        row.get("customer_name") or row.get("customer") or ""
                    ).strip(),
                    cookie=str(row.get("cookie") or "").strip(),
                    cookie_status=str(row.get("cookie_status") or "valid").strip().lower(),
                    human_account_id=human_account_id,
                    human_account_name=human_account_name,
                )
            )
        self._shops_cache[cache_key] = shops
        return list(shops)

    def clear_cache(self) -> None:
        """用户主动重新读取时，清理本次程序运行的店铺账号缓存。"""
        self._customers_cache = None
        self._shops_cache.clear()

    def _customer_name(self, customer_id: str) -> str:
        for customer in self._customers_cache or []:
            if customer.id == customer_id:
                return customer.name
        return ""

    def _human_accounts_by_shop(
        self,
        *,
        platform: str,
        customer_id: str | int | None,
    ) -> dict[str, tuple[str, str]]:
        params: dict[str, str | int] = {"platform": platform}
        if customer_id is not None:
            params["customer_id"] = customer_id
        payload = self._get_json("{}/cookies/".format(self.base_url), params=params)
        rows = self._response_rows(payload, "店铺账号")
        result: dict[str, tuple[str, str]] = {}
        for row in rows:
            shop_id = str(row.get("shop_id") or "").strip()
            accounts = row.get("human_accounts")
            if not shop_id or not isinstance(accounts, list) or not accounts:
                continue
            first_account = accounts[0]
            if not isinstance(first_account, Mapping):
                continue
            account_id = str(first_account.get("account_id") or "").strip()
            account_name = str(first_account.get("account_name") or "").strip()
            result[shop_id] = (account_id, account_name)
        return result

    def _get_json(self, url: str, **kwargs: Any) -> Mapping[str, Any]:
        try:
            response = self.session.get(
                url,
                timeout=self.timeout_seconds,
                **kwargs,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise RobotCookieApiError("读取机器人 Cookie 接口失败") from error
        except ValueError as error:
            raise RobotCookieApiError("中控接口返回的不是 JSON") from error
        if not isinstance(payload, Mapping):
            raise RobotCookieApiError("中控接口返回格式错误")
        return payload

    @staticmethod
    def _response_rows(payload: Mapping[str, Any], resource_name: str) -> list[Mapping[str, Any]]:
        if payload.get("ok") is not True:
            message = payload.get("message")
            raise RobotCookieApiError(str(message or "{}接口返回失败".format(resource_name)))
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise RobotCookieApiError("{}接口 data 不是列表".format(resource_name))
        return [row for row in rows if isinstance(row, Mapping)]


def parse_cookie_string(cookie: str) -> dict[str, str]:
    """将接口返回的完整 Cookie 字符串转换为连接所需字典。"""
    if not isinstance(cookie, str):
        raise ValueError("机器人 Cookie 必须是字符串")
    cookie_text = cookie.strip()
    if cookie_text.lower().startswith("cookie:"):
        cookie_text = cookie_text.split(":", 1)[1].strip()
    values: dict[str, str] = {}
    for item in cookie_text.replace("\n", ";").split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name.strip() and value.strip():
            values[name.strip()] = value.strip()
    if not values:
        raise ValueError("机器人 Cookie 为空或格式不正确")
    return values
