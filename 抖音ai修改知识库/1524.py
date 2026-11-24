# -*- coding: utf-8 -*-
"""批量调用扣子工作流处理 ltjlapi_json 下的问答 JSON。

适配新版纯数组输出格式：
[
  {"问题": "...", "回答": "..."},
  ...
]

shopid / goodsid 从文件名解析：douyin_{shopid}_{goodsid}_qa.json。
每个文件的完整内容作为 input 传给工作流，shopid / goods_id 作为参数。
兼容旧版 users 结构：文件名解析不到时，从文件内容兜底。
"""

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ============ 在这里改参数 ============
FOLDER_NAME = "ltjlapi_json"   # 同级目录下的文件夹名
CONCURRENCY = 3                # 并发数
MODE = 0                       # 0=goodsid为奇数时运行；1=goodsid为偶数时运行
SKIP_EMPTY_USERS = True        # 问答为空（空数组 / users 为空）时跳过，不调用工作流
# =====================================

TOKEN = "sat_sGdV6nr5vvCprf9n4FbDSRo29b5SPd8WDjCdKUy7Yjm0bq3vf4cORuFI0Gadwcsa"
WORKFLOW_ID = "7701455332942020617"
API_URL = "https://api.coze.cn/v1/workflow/run"

# 文件名格式：douyin_{shopid}_{goodsid}_qa.json
FILENAME_RE = re.compile(
    r"^douyin_(?P<shopid>\d+)_(?P<goodsid>\d+)_qa\.json$",
    re.IGNORECASE,
)


def _parse_filename(name):
    """从文件名解析 (shopid, goodsid)，解析不到返回 (None, None)。"""
    match = FILENAME_RE.match(name)
    if not match:
        return None, None
    return match.group("shopid"), match.group("goodsid")


def _extract_shopid(data):
    """兼容旧格式：从内容里取 shopid / shop_id / shopSN。"""
    if not isinstance(data, dict):
        return None
    for key in ("shopid", "shop_id", "shopSN"):
        value = data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _extract_goodsid(data):
    """兼容旧格式：从内容里取 goodsid / goods_id。"""
    if not isinstance(data, dict):
        return None
    for key in ("goodsid", "goods_id"):
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            try:
                return int(text)
            except ValueError:
                return None
    return None


def _should_run(gid, mode):
    is_odd = (gid % 2 == 1)
    return is_odd if mode == 0 else (not is_odd)


def _count_pairs(data):
    """统计问答对数量：新格式取数组长度，旧格式累加 users 下各列表长度。"""
    if isinstance(data, list):
        return len(data)
    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return 0
    return sum(len(pairs) for pairs in users.values() if isinstance(pairs, list))


def _presale_ratio_text(data):
    """新格式没有分类字段，显示 '-'；旧格式优先取 stats.presale_ratio_output，没有就现算。"""
    if isinstance(data, list):
        return "-"

    stats = data.get("stats") if isinstance(data, dict) else None
    if isinstance(stats, dict):
        ratio = stats.get("presale_ratio_output")
        if ratio is not None:
            try:
                return f"{float(ratio):.0%}"
            except (TypeError, ValueError):
                pass

    users = data.get("users") if isinstance(data, dict) else None
    if not isinstance(users, dict):
        return "-"
    total = presale = 0
    for pairs in users.values():
        if not isinstance(pairs, list):
            continue
        for item in pairs:
            if not isinstance(item, dict):
                continue
            total += 1
            if item.get("分类") == "presale":
                presale += 1
    return f"{presale / total:.0%}" if total else "-"


def run_coze_workflow(content, shopid, goodsid):
    """content 是文件原始字符串（纯数组 JSON），shopid / goodsid 由调用方解析好传入。"""
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "workflow_id": WORKFLOW_ID,
        "parameters": {
            "goods_id": str(goodsid),
            "shopid": str(shopid),
            "input": content,
        },
    }

    response = requests.post(API_URL, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    res = response.json()

    if res.get("code") != 0:
        raise RuntimeError(f"工作流执行失败: {res.get('code')} {res.get('msg')}")

    return res.get("data", "")


def main():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), FOLDER_NAME)
    if not os.path.isdir(folder):
        print(f"文件夹不存在: {folder}")
        return

    tasks = []
    skipped = 0
    total_pairs = 0

    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            data = json.loads(content)
        except Exception as e:
            print(f"[跳过] {name} 读取或解析失败: {e}")
            skipped += 1
            continue

        # 优先从文件名解析；解析不到再从内容兜底（兼容旧格式）
        shopid, goodsid_text = _parse_filename(name)
        gid = int(goodsid_text) if goodsid_text else _extract_goodsid(data)
        if not shopid:
            shopid = _extract_shopid(data)

        if gid is None:
            print(f"[跳过] {name} 缺少 goodsid（文件名或内容）")
            skipped += 1
            continue
        if not shopid:
            print(f"[跳过] {name} 缺少 shopid（文件名或内容）")
            skipped += 1
            continue

        if not _should_run(gid, MODE):
            skipped += 1
            continue

        pairs = _count_pairs(data)
        if SKIP_EMPTY_USERS and pairs == 0:
            print(f"[跳过] {name} 问答为空")
            skipped += 1
            continue

        total_pairs += pairs
        ratio = _presale_ratio_text(data)
        print(f"[待处理] {name} | goodsid={gid} | 问答={pairs} | 售前占比={ratio}")
        tasks.append((name, content, shopid, gid))

    print(f"\n文件夹: {folder}")
    print(
        f"待处理: {len(tasks)} 个，跳过: {skipped} 个，"
        f"总问答数: {total_pairs}，并发数: {CONCURRENCY}\n"
    )

    if not tasks:
        return

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {
            pool.submit(run_coze_workflow, c, s, g): n
            for n, c, s, g in tasks
        }
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                print(f"[完成] {name}\n{fut.result()}\n")
            except Exception as e:
                print(f"[失败] {name}: {e}\n")


if __name__ == "__main__":
    main()