# -*- coding: utf-8 -*-
"""
zk_api.py —— 蘑菇头中控平台接口（本地底座用）
========================================================================
接口文档：E:\\project\\item1\\pdd机器人9527\\接口文档(2).md
本地只用到两个：

    huoqu_zhuanyuan(shopid)              GET  /api/v1/cookies/?platform=pdd
                                         取该店铺的专员账号（人工客服）
    add_pending_task(shop_id, content)   POST /api/v1/pending-tasks/create/
                                         警示提醒（代替原来的发微信群）

"""
import requests

# ---- 中控平台地址（按实际部署地址改这里）----
BASE_URL = "http://117.72.204.36:8000"
PLATFORM = "pdd"
TIMEOUT = 15
CENTER_HEADERS = {"Accept": "application/json"}


def _get_shops():
    """取该平台全部店铺（平台连不上就直接抛异常，不掩盖故障）"""
    # 中控只接收平台标识；显式传空 Cookie，禁止携带浏览器/PDD Cookie。
    resp = requests.get(BASE_URL + "/api/v1/cookies/", params={"platform": PLATFORM},
                        headers=CENTER_HEADERS, cookies={}, timeout=TIMEOUT)
    return resp.json().get("data") or []


def huoqu_zhuanyuan(shopid):
    """
    按店铺 ID 取该店铺的专员账号（人工客服）

    返回形状和原内部接口一致，方便上游沿用老逻辑：
        {"shop_id": 平台店铺编号, "Data": [{"AccountName": 账号名, "mmsId": 账号ID}]}
    """
    shop = next((s for s in _get_shops()
                 if str(s.get("shop_id")) == str(shopid)), None)
    if shop is None:
        return {"shop_id": str(shopid or ""), "Data": []}

    data = [{"AccountName": a.get("account_name") or a.get("name") or "",
             "mmsId": a.get("account_id") or a.get("id") or ""}
            for a in (shop.get("human_accounts") or [])]
    return {"shop_id": shop.get("shop_id") or "", "Data": data}


def add_pending_task(shop_id, content):
    """警示提醒：在中控平台建一条紧急待办"""
    payload = {"time_type": "urgent", "handling_item": content, "platform": PLATFORM}
    if shop_id:
        payload["shop_id"] = str(shop_id)
    # 待办请求也不允许向中控发送 Cookie。
    resp = requests.post(BASE_URL + "/api/v1/pending-tasks/create/", json=payload,
                         headers=CENTER_HEADERS, cookies={}, timeout=TIMEOUT)
    return resp.json()
