"""京东聊天文本的统一清洗。"""

from __future__ import annotations

import re


_JD_EMOTICON_CODE = re.compile(r"#E-s\d+")


def normalize_jd_emoticons(text: str) -> str:
    """将京东 ``#E-s数字`` 表情代码统一转换为 ``[微笑]``。"""
    return _JD_EMOTICON_CODE.sub("[微笑]", text)


__all__ = ["normalize_jd_emoticons"]
