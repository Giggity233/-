"""按店铺隔离的 Loguru 日志配置。"""

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

from loguru import logger


LOG_ROOT = Path(__file__).resolve().parent / "logs"
_configured_shop_keys: set[str] = set()
_configure_lock = threading.Lock()
_console_configured = False


def _configure_console_logger() -> None:
    """控制台保留运行状态，但不输出完整聊天记录。"""
    global _console_configured
    with _configure_lock:
        if _console_configured:
            return
        logger.remove()
        logger.add(
            sys.stderr,
            level="INFO",
            filter=lambda record: not record["extra"].get("console_silent", False),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {message}",
        )
        _console_configured = True


def _safe_folder_name(value: str) -> str:
    normalized = re.sub(r'[\\/:*?"<>|\s]+', "_", value.strip())
    return normalized.strip("._") or "unknown_shop"


def get_shop_logger(shop_id: str, shop_name: str = ""):
    """返回绑定店铺信息的 logger，并首次创建该店铺的三个日志文件。"""
    _configure_console_logger()
    normalized_id = str(shop_id or "").strip() or "unknown_shop"
    normalized_name = str(shop_name or "").strip()
    shop_key = _safe_folder_name(normalized_id)
    folder_name = shop_key
    if normalized_name:
        folder_name = "{}_{}".format(shop_key, _safe_folder_name(normalized_name))
    directory = LOG_ROOT / folder_name

    with _configure_lock:
        if shop_key not in _configured_shop_keys:
            directory.mkdir(parents=True, exist_ok=True)
            filter_for_shop = lambda record: record["extra"].get("shop_log_key") == shop_key
            logger.add(
                directory / "chat.log",
                level="INFO",
                filter=lambda record: filter_for_shop(record)
                and record["extra"].get("log_channel") == "chat",
                encoding="utf-8",
                rotation="20 MB",
                retention="14 days",
            )
            logger.add(
                directory / "error.log",
                level="ERROR",
                filter=filter_for_shop,
                encoding="utf-8",
                rotation="20 MB",
                retention="30 days",
                backtrace=True,
                diagnose=False,
            )
            logger.add(
                directory / "runtime.log",
                level="INFO",
                filter=lambda record: filter_for_shop(record)
                and record["extra"].get("log_channel") != "chat",
                encoding="utf-8",
                rotation="20 MB",
                retention="14 days",
            )
            _configured_shop_keys.add(shop_key)

    return logger.bind(
        shop_log_key=shop_key,
        shop_id=normalized_id,
        shop_name=normalized_name or normalized_id,
    )


__all__ = ["LOG_ROOT", "get_shop_logger"]
