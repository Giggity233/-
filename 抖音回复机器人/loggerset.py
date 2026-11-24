"""按店铺写入并在控制台显示自动回复日志。"""

from __future__ import annotations

import re
import sys
import threading
from pathlib import Path

from loguru import logger


APP_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


class MerchantLogger:
    """为每个店铺创建独立文件日志，并将业务日志以绿色输出到控制台。"""

    def __init__(self) -> None:
        logger.remove()
        self._handlers: dict[str, int] = {}
        self._lock = threading.RLock()
        logger.add(
            sys.stderr,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss} | {extra[merchant]} | "
                "{level.name:<7} | {message}</green>\n"
            ),
            colorize=True,
            filter=lambda record: "merchant" in record["extra"],
        )

    @staticmethod
    def _safe_name(value: str) -> str:
        value = str(value).strip() or "未知店铺"
        return re.sub(r'[\\/:*?"<>|]', "_", value)

    def _ensure_file_handler(self, merchant: str, filename: str) -> tuple[str, str]:
        safe_merchant = self._safe_name(merchant)
        safe_filename = self._safe_name(filename)
        key = f"{safe_merchant}_{safe_filename}"
        with self._lock:
            if key not in self._handlers:
                log_path = APP_DIR / "log" / safe_merchant / f"{safe_filename}.log"
                log_path.parent.mkdir(parents=True, exist_ok=True)
                self._handlers[key] = logger.add(
                    log_path,
                    format="{time:YYYY-MM-DD HH:mm:ss} | {extra[merchant]} | {level.name:<7} | {message}",
                    rotation="50 MB",
                    retention="7 days",
                    encoding="utf-8",
                    enqueue=True,
                    filter=lambda record, expected_key=key: record["extra"].get("logger_key") == expected_key,
                )
        return key, safe_merchant

    def _log(self, level: str, msg: str, merchant: str, filename: str) -> None:
        key, safe_merchant = self._ensure_file_handler(merchant, filename)
        logger.bind(logger_key=key, merchant=safe_merchant).log(level, str(msg))

    def info(self, msg: str, merchant: str, filename: str) -> None:
        self._log("INFO", msg, merchant, filename)

    def success(self, msg: str, merchant: str, filename: str) -> None:
        self._log("SUCCESS", msg, merchant, filename)

    def warn(self, msg: str, merchant: str, filename: str) -> None:
        self._log("WARNING", msg, merchant, filename)

    def error(self, msg: str, merchant: str, filename: str) -> None:
        self._log("ERROR", msg, merchant, filename)


merchant_log = MerchantLogger()
