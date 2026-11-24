# -*- coding: utf-8 -*-
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# ============ 在这里改参数 ============
FOLDER_NAME = "ltjlapi_json"   # 同级目录下的文件夹名
CONCURRENCY = 3          # 并发数
MODE = 0                 # 0=goodsid为奇数时运行；1=goodsid为偶数时运行
# =====================================

TOKEN = "sat_sGdV6nr5vvCprf9n4FbDSRo29b5SPd8WDjCdKUy7Yjm0bq3vf4cORuFI0Gadwcsa"
WORKFLOW_ID = "7692297912043061290"
API_URL = "https://api.coze.cn/v1/workflow/run"


def run_coze_workflow(content):
    """入参是聊天记录 JSON 文件的内容（字符串，不读文件）。"""
    data = content if isinstance(content, dict) else json.loads(content)
    shopid = data.get("shopid") or data.get("shop_id") or data.get("shopSN")
    goods_id = data.get("goodsid") or data.get("goods_id")
    if not shopid or not goods_id:
        raise ValueError("内容中缺少 shopid 或 goodsid")

    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "workflow_id": WORKFLOW_ID,
        "parameters": {
            "goods_id": goods_id,
            "shopid": shopid,
            "input": content,
        },
    }

    response = requests.post(API_URL, json=payload, headers=headers)
    response.raise_for_status()
    res = response.json()

    if res.get("code") != 0:
        raise RuntimeError(f"工作流执行失败: {res.get('code')} {res.get('msg')}")

    return res.get("data", "")


def _extract_goodsid(data):
    gid = data.get("goodsid")
    if gid is None:
        gid = data.get("goods_id")
    if gid is None:
        return None
    return int(str(gid).strip())


def _should_run(gid, mode):
    is_odd = (gid % 2 == 1)
    return is_odd if mode == 0 else (not is_odd)


def main():
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), FOLDER_NAME)
    if not os.path.isdir(folder):
        print(f"文件夹不存在: {folder}")
        return

    tasks = []
    skipped = 0

    for name in sorted(os.listdir(folder)):
        if not name.lower().endswith(".json"):
            continue
        path = os.path.join(folder, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            gid = _extract_goodsid(json.loads(content))
        except Exception as e:
            print(f"[跳过] {name} 读取或解析失败: {e}")
            skipped += 1
            continue

        if gid is None:
            print(f"[跳过] {name} 缺少 goodsid")
            skipped += 1
            continue

        if not _should_run(gid, MODE):
            skipped += 1
            continue

        tasks.append((name, content))

    print(f"文件夹: {folder}")
    print(f"待处理: {len(tasks)} 个，跳过: {skipped} 个，并发数: {CONCURRENCY}\n")

    if not tasks:
        return

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = {pool.submit(run_coze_workflow, c): n for n, c in tasks}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                print(f"[完成] {name}\n{fut.result()}\n")
            except Exception as e:
                print(f"[失败] {name}: {e}\n")


if __name__ == "__main__":
    main()