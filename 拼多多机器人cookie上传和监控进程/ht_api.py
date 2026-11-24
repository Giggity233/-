# -*- coding: utf-8 -*-
"""
ht_api.py —— 蘑菇头中控平台接口（监控进程用）
========================================================================
接口文档：接口文档(2).md        平台地址：http://117.72.204.36:8000
原来这里的 http://115.231.97.229:6001 内部接口已全部换掉：

    huoqu_dianpu(accname)                GET  /api/v1/cookies/?platform=pdd
                                         按账号名（或店铺名）找店铺，含 human_accounts（专员）/ bot_accounts（机器人）
    jing_shi_tixing(shop_id, content)    POST /api/v1/pending-tasks/create/
                                         警示提醒：建一条紧急待办（代替原来的发微信群 / 发 CRM 通知）
    htsccookie(cookies, cookiesstr)      POST /api/v1/cookies/upsert/
                                         上传店铺 Cookie

没有对应接口、已删除的旧函数：
    htgetgoodspd（工厂商品校验）、send_wechat / fasweix（发微信群）、
    shnagchuan（订单聊天记录上传）、send_chongqing_shop_notify / send_kaifeng_shop_notify（CRM 群通知）
"""
import requests
from session_manager import get_session

# ---- 中控平台地址 ----
BASE_URL = "http://117.72.204.36:8000"
PLATFORM = "pdd"
TIMEOUT = 15


def huoqu_dianpu(accname):
    """
    按账号名找店铺（找不到再按店铺名找）；找不到返回 None

    参数：
        accname: 客服账号名（user_login_info.json 里的 username）
    """
    session = get_session()
    with session.get(BASE_URL + "/api/v1/cookies/", params={"platform": PLATFORM}, timeout=TIMEOUT) as resp:
        shops = resp.json().get("data") or []

    for shop in shops:                          # 先按账号名匹配（专员账号 / 机器人账号都算）
        names = [a.get("account_name") or a.get("name")
                 for a in (shop.get("human_accounts") or []) + (shop.get("bot_accounts") or [])]
        if accname and accname in names:
            return shop
    for shop in shops:                          # 再按店铺名匹配
        if accname and str(shop.get("shop_name")) == str(accname):
            return shop
    return None


def huoqu_zhuanyuan(shop_id):
    """Return the human agents configured for a shop in the legacy shape.

    ``mmsId`` is resolved to PDD's actual transfer ``csid`` by the monitor.
    """
    session = get_session()
    with session.get(
        BASE_URL + "/api/v1/cookies/",
        params={"platform": PLATFORM},
        timeout=TIMEOUT,
    ) as resp:
        shops = resp.json().get("data") or []

    shop = next((item for item in shops if str(item.get("shop_id")) == str(shop_id)), None)
    if shop is None:
        return {"shop_id": str(shop_id or ""), "Data": []}

    data = [
        {
            "AccountName": account.get("account_name") or account.get("name") or "",
            "mmsId": account.get("account_id") or account.get("id") or "",
        }
        for account in (shop.get("human_accounts") or [])
    ]
    return {"shop_id": shop.get("shop_id") or "", "Data": data}


def jing_shi_tixing(shop_id, content):
    """警示提醒：在中控平台建一条紧急待办"""
    payload = {"time_type": "urgent", "handling_item": content, "platform": PLATFORM}
    if shop_id:
        payload["shop_id"] = str(shop_id)
    session = get_session()
    with session.post(BASE_URL + "/api/v1/pending-tasks/create/", json=payload, timeout=TIMEOUT) as resp:
        return resp.json()


def shangchuan_zhanghao(cookies, accname):
    """
    回传当前登录账号的 ID 给中控平台（平台没抓到 ID 时靠这里补上）

    PASS_ID 结构：1-xxxx_<主账号>_<子账号>，例如
        1-b7AeZq..._468163277_181118665
    取最后两段：主账号（店铺编号）=468163277，当前子账号 ID=181118665

    参数：
        cookies: cookie 字典
        accname: 账号名（user_login_info.json 里的 username）
    """
    parts = cookies['PASS_ID'].split('_')
    shop_id = parts[-2]
    account_id = parts[-1]
    payload = {"account_name": accname, "account_id": int(account_id), "shop_id": str(shop_id)}
    session = get_session()
    with session.post(BASE_URL + "/api/v1/accounts/capture-id/", json=payload, timeout=TIMEOUT) as resp:
        print(resp.json())
        return resp.json()


def shangchuan_jiqiren_cookie(cookies, shopname=""):
    """Upload this monitor's PDD cookie to the robot-cookie store.

    ``page.cookies().as_dict()`` contains the current browser cookies.  The
    central platform expects the complete Cookie header as one string, while
    the shop ID is encoded in the penultimate ``PASS_ID`` segment.
    """
    pass_id = str(cookies.get("PASS_ID") or "")
    pass_id_parts = pass_id.split("_")
    if len(pass_id_parts) < 3:
        raise ValueError("机器人 Cookie 缺少有效的 PASS_ID，无法确定店铺编号")

    cookie_string = "; ".join(
        f"{name}={value}" for name, value in cookies.items() if value is not None
    )
    if not cookie_string:
        raise ValueError("机器人 Cookie 为空，未上传")

    payload = {
        "platform": PLATFORM,
        "shop_id": str(pass_id_parts[-2]),
        "cookie": cookie_string,
    }
    if shopname:
        payload["shop_name"] = shopname

    session = get_session()
    with session.post(
        BASE_URL + "/api/v1/robot-cookies/upsert/",
        json=payload,
        timeout=TIMEOUT,
    ) as resp:
        resp.raise_for_status()
        result = resp.json()

    if result.get("ok") is False:
        raise RuntimeError(result.get("message") or "机器人 Cookie 上传失败")
    return result
