"""查询当前机器人账号可转接的人工账号 ID。"""

from __future__ import annotations

import os
import threading
from collections.abc import Mapping
from typing import Callable, Optional

import requests


DEFAULT_TRANSFER_ACCOUNT_URL = "http://115.231.97.229:6001/Api/GetPDDShop_AccountDa.ashx"


class TransferAccountServiceError(RuntimeError):
    """人工账号接口调用失败或返回格式无效。"""


class TransferAccountService:
    def __init__(
        self,
        *,
        session: Optional[requests.Session] = None,
        url: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.session = session or requests.Session()
        self.url = (url or os.environ.get("JD_TRANSFER_ACCOUNT_URL") or DEFAULT_TRANSFER_ACCOUNT_URL).strip()
        self.timeout_seconds = timeout_seconds

    def list_human_account_ids(self, robot_account_name: str) -> list[str]:
        account_name = str(robot_account_name or "").strip()
        if not account_name:
            raise ValueError("机器人账号不能为空")
        try:
            response = self.session.post(
                self.url,
                json={"AccName": account_name, "ShopName": ""},
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise TransferAccountServiceError("人工账号接口请求失败") from error
        except ValueError as error:
            raise TransferAccountServiceError("人工账号接口未返回 JSON") from error
        if not isinstance(payload, Mapping) or str(payload.get("code")) != "0":
            raise TransferAccountServiceError("人工账号接口返回失败")
        rows = payload.get("Data")
        if not isinstance(rows, list):
            raise TransferAccountServiceError("人工账号接口数据格式错误")

        result: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            account_id = row.get("AccountId") or row.get("AccountID") or row.get("account_id")
            if account_id is None or isinstance(account_id, bool):
                continue
            account_id = str(account_id).strip()
            if (
                not account_id
                or account_id in seen
                or str(row.get("AccountType")) != "1"
                or str(row.get("Status")) != "1"
            ):
                continue
            seen.add(account_id)
            result.append(account_id)
        return result


def get_human_account_ids(robot_account_name: str) -> list[str]:
    return TransferAccountService().list_human_account_ids(robot_account_name)


class TransferAccountCache:
    """以机器人登录账号为键的进程内人工账号缓存。"""

    def __init__(self, provider: Callable[[str], list[str]]) -> None:
        self.provider = provider
        self._values: dict[str, tuple[str, ...]] = {}
        self._lock = threading.Lock()

    def get(self, robot_account_name: str) -> list[str]:
        key = str(robot_account_name or "").strip()
        if not key:
            raise ValueError("机器人账号不能为空")
        with self._lock:
            cached = self._values.get(key)
            if cached is not None:
                return list(cached)

            account_ids = self.provider(key)
            normalized = tuple(
                dict.fromkeys(
                    str(account_id).strip()
                    for account_id in account_ids
                    if str(account_id).strip()
                )
            )
            self._values[key] = normalized
            return list(normalized)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


_human_account_cache = TransferAccountCache(get_human_account_ids)


def get_cached_human_account_ids(robot_account_name: str) -> list[str]:
    """本次程序运行内，同一机器人账号只请求一次人工账号接口。"""
    return _human_account_cache.get(robot_account_name)


__all__ = [
    "TransferAccountCache",
    "TransferAccountService",
    "TransferAccountServiceError",
    "get_cached_human_account_ids",
    "get_human_account_ids",
]
