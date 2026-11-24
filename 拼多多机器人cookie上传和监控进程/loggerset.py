import os
import sys
from pathlib import Path
from loguru import logger

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent


class MerchantLogger:
    """
    终极无报错版 商家日志工具
    调用方式：logger.info("日志内容", "商家名", "日志文件名")
    存储路径：log/商家名/日志文件名.log
    功能：50MB分割、保留7天、控制台彩色、文件分类
    """

    def __init__(self):
        logger.remove()
        self.handlers = {}  # 缓存日志处理器
        self.console_handler_id = None

    def _get_logger(self, merchant: str, filename: str):
        # 唯一标识：商家+文件名
        key = f"{merchant}_{filename}"
        if key in self.handlers:
            return

        # 创建日志目录
        log_path = APP_DIR / "log" / merchant / f"{filename}.log"
        os.makedirs(log_path.parent, exist_ok=True)

        # 为每个商家和文件创建独立的处理器
        handler_id = logger.add(
            sink=log_path,
            format=f"{{time:YYYY-MM-DD HH:mm:ss}} | {merchant} | {{level.name:<7}} | {{message}}",
            rotation="50 MB",
            retention="7 days",
            encoding="utf-8",
            enqueue=True,
            filter=lambda record: record["extra"].get("key") == key
        )
        self.handlers[key] = handler_id

        # 控制台输出（每次调用都使用当前商家名称）
        if self.console_handler_id is not None:
            logger.remove(self.console_handler_id)
        self.console_handler_id = logger.add(
            sink=lambda x: print(x, end=""),
            format=f"<green>{{time:YYYY-MM-DD HH:mm:ss}}</green> | <cyan>{merchant}</cyan> | <level>{{level.name:<7}}</level> | <level>{{message}}</level>",
            colorize=True
        )

    # 对外调用方法（完全保留你的调用方式）
    def info(self, msg: str, merchant: str, filename: str):
        key = f"{merchant}_{filename}"
        self._get_logger(merchant, filename)
        logger.bind(key=key).info(msg)

    def success(self, msg: str, merchant: str, filename: str):
        key = f"{merchant}_{filename}"
        self._get_logger(merchant, filename)
        logger.bind(key=key).success(msg)

    def warn(self, msg: str, merchant: str, filename: str):
        key = f"{merchant}_{filename}"
        self._get_logger(merchant, filename)
        logger.bind(key=key).warning(msg)

    def error(self, msg: str, merchant: str, filename: str):
        key = f"{merchant}_{filename}"
        self._get_logger(merchant, filename)
        logger.bind(key=key).error(msg)


merchant_log = MerchantLogger()  # 创建单例供所有模块使用

# ------------------- 测试（零报错，分类存储） -------------------
# if __name__ == "__main__":
#     log = MerchantLogger()
#
#     # 写入：log/美团外卖商家/dd运营日志.log
#     log.info("店铺今日9:00正常营业", "美团外卖商家", "dd运营日志")
#     log.warn("五花肉库存仅剩5斤", "美团外卖商家", "11运营日志")
#
#     # 写入：log/美团外卖商家/异常运营日志.log
#     log.error("支付接口调用失败", "美团外卖商家", "异常运营日志")
