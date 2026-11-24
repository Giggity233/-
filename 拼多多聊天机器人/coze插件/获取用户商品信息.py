# -*- coding: utf-8 -*-
"""
Coze 插件：获取用户商品信息
========================================================================
用途：对话流里按买家 uid 取商品 id（商品采集上传插件的入参来源）。

    商品 id 在 WS 推送里是没有的，WS 只给 uid / msg_id / content，
    所以这里按原版逻辑走两个接口：
        1. 先查该买家的订单 -> 取订单里的商品（也就能拿到订单号、金额、付款时间、物流单号）
        2. 没有订单时，查"用户足迹推荐商品"里的商品
    注意：首单是「补收差价专用商品」时会自动改用第二单，否则拿到的是补差价的假商品。

输入参数（在 Coze 插件入参里配置，名字保持一致）：
    userid  买家 uid（主程序 WS 推送的 userid）
    anti    anti.js 密令（主程序上传的 anti）
    cook    浏览器 cookie 字符串（主程序上传的 cook）

输出参数：
    goodsid         商品 id（拿不到为空串）
    orderid         订单号
    money           订单金额（元，两位小数）
    moneyban        半价金额（原版的 ceil(int(money)/2)）
    ordertime       付款时间（毫秒时间戳）
    trackingNumber  物流单号
    orderstatus     订单状态文案
    source          数据来源：order=订单 / footprint=足迹推荐 / 空=没拿到
    error           出错原因（正常为空串）
"""
import json
import math

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")


def pdd_headers(anti, cook):
    """拼多多接口通用请求头（登录态由 cook 提供）"""
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA,
        "Cookie": cook
    }


def get_order_goods(userid, anti, cook):
    """
    查买家订单，返回订单里的商品信息；没有订单返回 None

    返回：{goodsid, orderid, orderstatus, trackingNumber, money, ordertime}
    """
    url = "https://mms.pinduoduo.com/latitude/order/userAllOrder"
    data = {
        "pageNo": 1,
        "pageSize": 10,
        "showHistory": True,
        "uid": str(userid)
    }
    resp = requests.post(url, headers=pdd_headers(anti, cook),
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    result = resp.json()
    print(result)
    if not result.get("success"):
        return None
    if result["result"]["total"] == 0:
        return None

    orders = result["result"]["orders"]
    # 首单是补收差价专用商品时，改用第二单
    if "补收差价专用商品" in orders[0]["orderGoodsList"]["goodsName"]:
        order = orders[1] if len(orders) > 1 else orders[0]
    else:
        order = orders[0]

    try:
        trackingNumber = order["trackingNumber"]
    except Exception:
        trackingNumber = 0

    return {
        "goodsid": order["orderGoodsList"]["goodsId"],
        "orderid": order["orderSn"],
        "orderstatus": order["orderStatusStr"],
        "trackingNumber": trackingNumber,
        "money": round(int(order["orderAmount"]) / 100, 2),   # 单位：分 -> 元
        "ordertime": int(order["payTime"]) * 1000             # 毫秒时间戳
    }


def get_footprint_goods(userid, anti, cook):
    """查买家足迹推荐商品，返回 goodsId；没有返回 None"""
    url = "https://mms.pinduoduo.com/latitude/goods/singleRecommendGoods"
    data = {
        "type": 2,
        "uid": str(userid),
        "pageNum": 1,
        "pageSize": 10
    }
    resp = requests.post(url, headers=pdd_headers(anti, cook),
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    result = resp.json()
    print(result)
    if not result.get("success"):
        return None
    if result["result"]["total"] == 0:
        return None
    return result["result"]["headGoods"]["goodsId"]


# def handler(args):
#     """Coze 插件入口"""
#     empty = {
#         "goodsid": "", "orderid": "", "money": "", "moneyban": "",
#         "ordertime": "", "trackingNumber": "", "orderstatus": "",
#         "source": "", "error": ""
#     }
#     try:
#         userid = str(args.input.userid)
#         anti = str(args.input.anti)
#         cook = str(args.input.cook)
#
#         # 1. 先查订单
#         order = get_order_goods(userid, anti, cook)
#         if order:
#             money = order["money"]
#             empty.update(order)
#             empty["moneyban"] = math.ceil(int(money) / 2)   # 半价金额（原版算法）
#             empty["source"] = "order"
#         else:
#             # 2. 没有订单，取足迹推荐商品
#             goodsid = get_footprint_goods(userid, anti, cook)
#             if goodsid:
#                 empty["goodsid"] = goodsid
#                 empty["source"] = "footprint"
#
#         # 3. 统一转成字符串返回
#         #    PDD 的 goodsId 是 12 位大整数（如 826908301715），
#         #    如果出参声明成整数类型，Coze 会因为它超出范围把它变成 null，
#         #    所以这里全部按字符串返回；Coze 出参类型也请统一设成 String。
#         return {k: ("" if v is None else str(v)) for k, v in empty.items()}
#     except Exception as e:
#         empty["error"] = str(e)
#         return {k: ("" if v is None else str(v)) for k, v in empty.items()}


a={
  "anti": "0apWtxiFXcQaY99__cVe6lZLb4EK4G2bYqD2L54oMZBGPwfDOwpycwwsqAQsxuDtG_OHPa49aOganKEnXTxXD5KH4xJQTAnkj7KzfwSyXrubMe1ZtqSRmbFx7xnGfDBSixsW0tUn64x-6ng4yfoagMnuZUqM2bhvepXZcVjxlDx86ItEE8xzSl2YXmeyO_hE7x8_9ccXgyeubiSCZ9jw1tY-Zzg_LEEVkiP3vD-EjzFt4cfyk6-7eDM6JhqepBlzzpF0ncqJE8cTIr32pMMaoxIa2bf1m3vZaUv_5pkOTOuS0-9_Z9AVlP3plA8w0llG_rZOv8bzBulIQIVkoWAaWFhK4d4KfW05Q89A15x6shM0ZPvB9j28dXXM1o6exu3vrChnSCIJBXPnqAyeQlFmMloM9blMJzQaKcSiARsDk3wra3S3tKsT5uORuJbcofhoPxoCSJN9Q_qCYlxyUjdg",
  "cookie": "mms_b84d1838=3616,150,180,3693,3700,3706,3523,3660,3709,3614,3599,3658,3605,3622,3677,3588,3254,3532,3642,3474,3475,3477,3479,3687,3482,1202,1203,1204,1205,3417; ru2k=b6ac81a5-908b-4f0f-b830-6c953f40859b; rckk=Vjp6cQYJHTMyY494kkdjOxDbV64HNuYi; api_uid=CimFxWqY3CEwkgBi66G6Ag==; _nano_fp=XpmJl0ToX5mxX5Tyno_0A4NSx1VxVafrV7rv_0ul; ru1k=62113d79-a168-4464-95f1-ae81a6f67e0b; _f77=62113d79-a168-4464-95f1-ae81a6f67e0b; _bee=Vjp6cQYJHTMyY494kkdjOxDbV64HNuYi; terminalFinger=PrFRXJf8Pi9kOfPiKEdjAEysSN22cQax; x-visit-time=1790240173071; JSESSIONID=41CC24F38D2C0DFCD05770C2FFEB274E; PASS_ID=1-/hLxs2tnyZhEdohjqtHHl1EVXqZXGFYZzqrVeoBq1bmt84mn5qG5foYmXJcWsFxS2Mu6J6sugOH/TDShLLrRPQ_468163277_181118665; _a42=b6ac81a5-908b-4f0f-b830-6c953f40859b",
  "userid": "6635301724136"
}
# get_order_goods('6635301724136', a['anti'], a['cookie'])


