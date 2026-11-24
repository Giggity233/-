# -*- coding: utf-8 -*-
"""抖店/抖音 IM 订单查询 - 本地 ExecJS 版本

功能：
1. 使用 execjs 读取本地 js/dy_jl_ab.js 生成 a_bogus
2. 查询 IM 订单及商品足迹
3. 包含本地测试入口 (__main__)
"""

from __future__ import annotations

import json
import time
import urllib.parse

import requests
import execjs

# ============================================================================
# 一、a_bogus 生成（execjs 调用外部 JS 文件）
# ============================================================================

# 读取本地的 JS 文件
try:
    with open('js/dy_jl_ab.js', 'r', encoding='utf-8') as f:
        dyjs = f.read()
except FileNotFoundError:
    raise RuntimeError("未找到 js/dy_jl_ab.js 文件，请检查本地路径是否正确！")


# ============================================================================
# 二、业务代码
# ============================================================================

def cookie_str_to_json(cookie_str: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for part in cookie_str.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            cookies[key] = value.strip()
    return cookies


def getorder(cookies, user_id, talkid):
    """查询订单；无订单返回 None；网络/解析异常直接抛出。"""
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://im.jinritemai.com",
        "priority": "u=1, i",
        "referer": "https://im.jinritemai.com/",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "x-secsdk-csrf-token": "000100000001b2c9a46295673ac94171853f029d650bd68b22c4f75ce584ed3dc366c830a05d187df02c8d41083f,1115151",
    }

    url = "https://pigeon.jinritemai.com/backstage/cmpoent/order/query"
    params = {
        "biz_type": "4",
        "PIGEON_BIZ_TYPE": "2",
        "_ts": str(int(time.time() * 1000)),
        "_pms": "1",
        "FUSION": "true",
        "_v": "1.0.1.5278",
    }
    data = {
        "security_user_id": str(user_id),
        "page_no": 0,
        "page_size": 5,
        "tab_type": 0,
        "search_words": "",
        "is_init_tab": 0,
        "biz_type": 2,
        "from_conversation_short_id": str(talkid),
        "version": "1.0",
        "open_params": {},
        "workstation_opt_version": "v2",
        "service_entity_id": "",
        "workstation_opt_gray": True,
    }
    pa = urllib.parse.urlencode(params)
    da = json.dumps(data, separators=(",", ":")).replace(" ", "")

    # ========================================================================
    # 【核心替换点】：完全按照第一段代码的方式，通过 execjs 生成 a_bogus
    # ========================================================================
    ab = execjs.compile(dyjs).call('enc', pa, da, headers["user-agent"])
    params["a_bogus"] = ab

    response = requests.post(
        url, headers=headers, params=params, data=da, cookies=cookies, timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    queryorderxx = payload.get("data") or []
    if not queryorderxx:
        return None

    first = queryorderxx[0]
    sku_list = first.get("sku_order_list") or []
    if sku_list:
        goodsid = sku_list[0].get("product_id", 0)
        money = sku_list[0].get("actual_pay_amount_str", "0")
    else:
        goodsid = 0
        money = "0"

    return {
        "orderid": first.get("order_id", 0),
        "goodsid": goodsid,
        "money": money,
        "wuliustate": first.get("order_status_desc", ""),
    }


def getzhuji(user_id, talk_id, cookies):
    """取商品足迹号；查不到时返回 1（保持原有兜底行为），网络异常直接抛出。"""
    url = (
        f"https://pigeon.jinritemai.com/backstage/workstation/get_consulting_products"
        f"?user_id={user_id}&conv_id={talk_id}&_pms=1&_v=1.0.1.5278"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://im.jinritemai.com",
        "priority": "u=1, i",
        "referer": "https://im.jinritemai.com/",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    response = requests.get(url, headers=headers, cookies=cookies, timeout=15)
    response.raise_for_status()
    payload = response.json()
    products = (payload.get("data") or {}).get("consulting_product") or []
    if not products:
        return 1
    return products[0].get("product_id", 1)


def goodsmain(cookiesyuan, user_id, talkid):
    cookies = cookie_str_to_json(cookiesyuan)
    orderxx = getorder(cookies, user_id, talkid)
    if orderxx is None:
        goodsid = getzhuji(user_id, talkid, cookies)
        orderxx = {
            "orderid": 0,
            "goodsid": goodsid,
            "money": 0,
            "wuliustate": "售前",
        }
    return orderxx


