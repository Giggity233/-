# -*- coding: utf-8 -*-
"""
Coze 插件：获取商品信息采集上传
========================================================================
用途：按 goodsid 采集商品详情/属性/30天销量，上传到「蘑菇头中控平台」的商品库。
      上传接口已换成 接口文档(2).md 的 POST /api/v1/ai/products/upsert/，
      不再使用 115.231.97.229:6001（同时去掉旧的工厂商品校验和内部店铺信息查询）。

采集顺序：
    0. 先查中控平台是否已有该商品，已有就直接跳过（不重复上传、也不再采集）  ← 新增
    1. 商品详情（价格、主图、详情图、SKU）  mms.pinduoduo.com
    2. 30 天销量                            mms.pinduoduo.com
    3. 商品属性                             mms.pinduoduo.com
    4. 组装 zl 上传中控平台商品库

输入参数（在 Coze 插件入参里配置，名字保持一致）：
    goodsid  商品 id（由「获取用户商品信息」插件给）
    anti     anti.js 密令（主程序上传的 anti）
    cook     浏览器 cookie 字符串（主程序上传的 cook）
    shopid   店铺编号（主程序 WS 推送的 shopid）

输出参数：
    status      ok=上传成功 / skip=平台已有该商品、已跳过 / fail=上传失败 / error=出错
    goods_name  商品名称（skip 时为空）
    msg         说明信息 / 接口原文
"""
import json

import requests

# ---- 蘑菇头中控平台（接口文档(2).md 里的示例是 http://127.0.0.1:8000，按实际部署地址改这里）----
BASE_URL = "http://117.72.204.36:8000"
PLATFORM = "pdd"
TIMEOUT = 15

UA_PDD = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36")


def pdd_headers(anti, cook, referer="https://mms.pinduoduo.com/goods/goods_list"):
    """拼多多后台接口请求头（登录态由 cook 提供）"""
    return {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,
        "cache-control": "max-age=0",
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": referer,
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA_PDD,
        "Cookie": cook
    }


# ===================== 拼多多后台：采集 =====================
def huoqu_details(goodid, anti, cook):
    """商品详情：价格区间、名称、创建时间、主图、详情图、SKU"""
    url = "https://mms.pinduoduo.com/glide/v2/mms/query/commit/on_shop/detail"
    resp = requests.post(url, headers=pdd_headers(anti, cook),
                         data=json.dumps({"goods_id": goodid}, separators=(',', ':')), timeout=15)
    return resp.json()


def shux(goodid, anti, cook, max_attempts=2):
    """商品属性（失败重试 2 次），拿不到返回 None"""
    url = "https://mms.pinduoduo.com/draco-ms/mms/query-goods-property"
    for _ in range(max_attempts):
        resp = requests.post(url, headers=pdd_headers(anti, cook),
                             data=json.dumps({"goods_id": goodid}, separators=(',', ':')), timeout=15)
        try:
            resp.json()['result']['goods_properties']
            return resp.json()
        except Exception:
            continue
    return None


def xiaoliang(goodid, anti, cook):
    """30 天销量"""
    url = "https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList"
    data = {
        "goods_id_list": [str(goodid)],
        "pre_sale_type": 4,
        "page": 1,
        "shipment_time_type": 3,
        "is_onsale": 1,
        "sold_out": 0,
        "size": 10
    }
    resp = requests.post(url,
                         headers=pdd_headers(anti, cook,
                                             "https://mms.pinduoduo.com/goods/goods_list?msfrom=mms_sidenav"),
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    return resp.json()["result"]["goods_list"][0]["sold_quantity_for_thirty_days"]


# ===================== 中控平台：查询 / 上传 =====================
def chaxun_chanpin(goodid, shop_sn):
    """
    查中控平台是否已经有这个商品
    返回：True=已有（不用再上传） / False=没有或查询失败（继续走上传）
    """
    try:
        resp = requests.get(BASE_URL + "/api/v1/ai/products/",
                            params={"platform": PLATFORM, "shopid": shop_sn, "goods_id": goodid},
                            timeout=TIMEOUT)
        body = resp.json()
        return body.get("ok") is True and bool(body.get("data"))
    except Exception:
        return False


def shangchuan_chanpin(zl):
    """
    商品入库：POST /api/v1/ai/products/upsert/
    以「平台 + 店铺号 + 商品号」覆盖写入
    """
    resp = requests.post(BASE_URL + "/api/v1/ai/products/upsert/",
                         json={"platform": PLATFORM, "zl": zl}, timeout=TIMEOUT)
    return resp.json()


# ===================== 主流程 =====================
def caiji_shangchuan(goodid, anti, cook, shop_sn):
    """
    采集 + 上传

    返回：(status, goods_name, msg)
    """
    # 0. 平台已有该商品就直接跳过（不重复上传，也不再采集）
    if chaxun_chanpin(goodid, shop_sn):
        return "skip", "", "平台已有该商品（店铺%s 商品%s），跳过重复上传" % (shop_sn, goodid)

    # 1. 详情
    details = huoqu_details(goodid, anti, cook)
    if not details.get('result'):
        return "error", "", "商品详情接口返回异常：%s" % str(details)[:150]

    result = details["result"]
    goods_name = result.get("goods_name", "")

    # 2. 销量 + 属性
    sold_quantity = xiaoliang(goodid, anti, cook)
    shux1 = shux(goodid, anti, cook)
    if not shux1:
        return "fail", goods_name, "商品属性接口无返回"

    # 3. 组装 zl（中控平台不需要 username / PT）
    zl = {
        "shopSN": shop_sn,
        "goods_id": goodid,
        "goods_name": goods_name,
        "min_group_price": result["min_group_price"],
        "max_group_price": result["max_group_price"],
        "sold_quantity": sold_quantity,
        "created_at": result["created_at"],
        "mainimgurls": [img["url"] for img in result["carousel_gallery"]],
        "detailimgurls": [img["url"] for img in result["detail_gallery"]],
    }

    # SKU：款式、型号、SKU 明细、活动价
    kuans = []
    model = []
    skudetails = []
    jiabi = []
    for skuxx in result["skus"]:
        try:
            if skuxx["spec"][0]["spec_name"] not in kuans:
                kuans.append(skuxx["spec"][0]["spec_name"])
            if skuxx["spec"][1]["spec_name"] not in model:
                model.append(skuxx["spec"][1]["spec_name"])
            skudetails.append({
                "skuname": '%s%%%s' % (skuxx["spec"][0]["spec_name"], skuxx["spec"][1]["spec_name"]),
                "sku_id": skuxx['sku_id'],
                "price": skuxx['multi_price'],
                "quantity": skuxx['quantity'],
            })
            try:
                jiabi.append(int(skuxx["carnival_price"]))
            except Exception:
                pass
        except Exception:
            break
    zl["skudetails"] = skudetails
    # 活动价有值时覆盖价格区间
    try:
        zxiao = min(jiabi)
        zda = max(jiabi)
        if zxiao != 0:
            zl['min_group_price'] = zxiao
        if zda != 0:
            zl["max_group_price"] = zda
    except Exception:
        pass
    zl["skutypes"] = [
        {"skutypename": "款式", "values": kuans},
        {"skutypename": "型号", "values": model}
    ]

    # 商品属性
    values = []
    for sxxx in shux1['result']['goods_properties']:
        try:
            values.append({
                "AttributeName": sxxx['name'],
                "AttributeValue": sxxx["values"][0]["value"]
            })
        except Exception:
            continue
    zl["values"] = values

    # 4. 上传中控平台
    ret = shangchuan_chanpin(zl)
    if ret.get("ok") is True:
        return "ok", goods_name, "上传成功"
    return "fail", goods_name, "上传失败，平台返回：%s" % str(ret)[:200]


def handler(args):
    """Coze 插件入口"""
    try:
        goodsid = str(args.input.goodsid)
        anti = str(args.input.anti)
        cook = str(args.input.cook)
        shopid = str(args.input.shopid)

        status, goods_name, msg = caiji_shangchuan(goodsid, anti, cook, shopid)
        return {"status": status, "goods_name": goods_name, "msg": msg}
    except Exception as e:
        return {"status": "error", "goods_name": "", "msg": str(e)}