# -*- coding: utf-8 -*-
"""抖音商品抓取并上传知识库 —— 本地 execjs 调用版本

合并内容：
1. 按照 import requests.py 的方式，使用 execjs 读取并调用 dy_jl_ab.js 生成加密
2. 保留商品抓取 / 知识库上传逻辑
"""

from __future__ import annotations

import json
import time
import urllib.parse
from datetime import datetime
from typing import Any

import requests
import execjs  # 引入 execjs 模块

# ============================================================================
# 第一部分：a_bogus 生成（使用 execjs 调用外部 JS 文件）
# ============================================================================

# 读取本地的 JS 文件，完全按照第一段代码的方式
try:
    with open('../抖音机器人回复/js/dy_jl_ab.js', 'r', encoding='utf-8') as f:
        dyjs = f.read()
except FileNotFoundError:
    raise RuntimeError("未找到 js/dy_jl_ab.js 文件，请检查本地路径是否正确！")

# ============================================================================
# 第二部分：业务逻辑（抓取抖音商品 + 上传知识库）
# ============================================================================

# 蘑菇头中控平台地址，按实际修改
BASE_URL = "http://117.72.204.36:8000"


def parse_cookie_string(cookie_str: str) -> dict:
    cookie_dict = {}
    if not isinstance(cookie_str, str) or not cookie_str.strip():
        return cookie_dict

    cookie_pairs = [pair.strip() for pair in cookie_str.split(';') if pair.strip()]

    for pair in cookie_pairs:
        if '=' not in pair:
            cookie_dict[pair.strip()] = ""
            continue
        key, value = pair.split('=', 1)
        key = key.strip()
        value = value.strip()
        if value.lower() == 'null':
            value = None
        cookie_dict[key] = value

    return cookie_dict


def time_str_to_timestamp(time_str: str | int, format_str: str = "%Y-%m-%d %H:%M:%S") -> int:
    try:
        if isinstance(time_str, (int, float)):
            return int(time_str)
        dt = datetime.strptime(str(time_str), format_str)
        return int(dt.timestamp())
    except ValueError as e:
        print(f"时间格式解析失败：{e}")
        return 0
    except Exception as e:
        print(f"转换时间戳异常：{e}")
        return 0


def extract_key_and_name(product_format_data: dict) -> list:
    result = []
    if not isinstance(product_format_data, dict):
        return result

    for outer_key, inner_list in product_format_data.items():
        for item in inner_list:
            name = item.get("name", "").strip()
            if len(name) < 30:
                result.append({
                    "AttributeName": outer_key,
                    "AttributeValue": name,
                })
            else:
                result.append({
                    "AttributeName": outer_key,
                    "AttributeValue": name[:30],
                })
    return result


def convert_to_attr_list(raw_dict) -> list:
    attr_list = []
    for key, value in raw_dict.items():
        if value is None or value == "":
            continue
        attr_list.append({
            "AttributeName": key,
            "AttributeValue": (str(value) if not isinstance(value, str) else value)[:20],
        })
    return attr_list


def check_product_exists(shop_id, goods_id, platform="douyin"):
    """返回 True=已存在 / False=不存在 / None=检查失败。"""
    url = f"{BASE_URL}/api/v1/ai/products/"
    params = {
        "platform": platform,
        "shopid": str(shop_id),
        "goods_id": str(goods_id),
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
    except requests.RequestException as e:
        print(f"[知识库检查异常] {e}")
        return None

    if resp.status_code == 404:
        return False

    if resp.status_code != 200:
        print(f"[知识库检查失败] HTTP {resp.status_code}: {resp.text[:200]}")
        return None

    try:
        body = resp.json()
    except ValueError:
        print("[知识库检查失败] 返回不是 JSON")
        return None

    if body.get("ok") is True:
        return bool(body.get("data"))

    if body.get("ok") is False:
        msg = str(body.get("message", ""))
        low = msg.lower()
        if (
                "不存在" in msg
                or "未找到" in msg
                or "没有找到" in msg
                or "not found" in low
                or "no product" in low
                or "does not exist" in low
        ):
            return False
        print(f"[知识库检查失败] {msg}")
        return None

    return bool(body.get("data"))


def upload_product_to_knowledge(zl, platform="douyin"):
    payload = {"platform": platform, "zl": zl}
    resp = requests.post(
        f"{BASE_URL}/api/v1/ai/products/upsert/",
        json=payload,
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    if not body.get("ok"):
        raise RuntimeError(f"上传知识库失败：{body}")
    return body.get("data")


def getzheskushuju(cookies, goodsid):
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "priority": "u=1, i",
        "referer": "https://fxg.jinritemai.com/ffa/g/list",
        "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "x-tt-from-appid": "ffa-goods",
        "x-tt-from-end": "PC",
        "x-tt-from-page": "https://fxg.jinritemai.com/ffa/g/list",
        "x-tt-from-version": "1.0.1.520",
    }

    url = "https://fxg.jinritemai.com/product/tproduct/previewOnline"
    params = {
        "product_id": goodsid,
        "need_live_status": "true",
        "appid": "1",
    }

    data = {}
    pa = urllib.parse.urlencode(params)
    da = json.dumps(data, separators=(',', ':')).replace(' ', '')

    # ========================================================================
    # 【核心替换点】：完全按照第一段代码的方式生成 a_bogus
    # ========================================================================
    ab = execjs.compile(dyjs).call('enc', pa, da, headers['user-agent'])
    params['a_bogus'] = ab

    response = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=10)
    response.raise_for_status()

    skutypes = []
    skutypexxs = response.json()["data"]["spec_detail"]["specs"]
    for skutypexx in skutypexxs:
        values = [i['name'] for i in skutypexx['values']]
        skutypes.append({
            "skutypename": skutypexx['name'],
            "values": values,
        })

    skudetails = []
    for spec_price in response.json()["data"]["spec_prices"]:
        name = ''
        for i in spec_price['sell_properties']:
            name += i['value_name']
        skudetails.append({
            "skuname": name,
            "sku_id": spec_price['id'],
            "price": spec_price['price'],
            "quantity": spec_price['stock_num'],
        })

    product_format = convert_to_attr_list(response.json()["data"]["product_format"])
    return skutypes, skudetails, product_format


def huoqushangp(cookies, goodsid):
    """抓取抖音商品并上传知识库。"""
    result = {
        "ok": False,
        "goodsid": str(goodsid),
        "shop_id": "",
        "goods_name": "",
        "uploaded": False,
        "skipped": False,
        "message": "",
    }

    try:
        if isinstance(cookies, str):
            cookie_dict = parse_cookie_string(cookies)
        else:
            cookie_dict = dict(cookies)

        cookie_dict = {k: v for k, v in cookie_dict.items() if v is not None}

        shop_id = str(cookie_dict.get("SHOP_ID", "")).strip()
        result["shop_id"] = shop_id
        if not shop_id:
            result["message"] = "Cookie 中缺少 SHOP_ID，无法检查/上传知识库"
            return result

        exists = check_product_exists(shop_id, goodsid, platform="douyin")
        if exists is True:
            result["ok"] = True
            result["skipped"] = True
            result["message"] = f"知识库已存在抖音商品 {goodsid}（店铺 {shop_id}），跳过"
            return result
        if exists is None:
            result["message"] = "知识库检查失败，为避免重复上传，本次不调用抖音接口"
            return result

        zl: dict[str, Any] = {
            "platform": "douyin",
            "PT": "2",
            "username": "",
            "shopSN": shop_id,
            "goods_id": str(goodsid),
        }

        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "zh-CN,zh;q=0.9",
            "priority": "u=1, i",
            "sec-ch-ua": "\"Chromium\";v=\"142\", \"Google Chrome\";v=\"142\", \"Not_A Brand\";v=\"99\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Windows\"",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
            "x-tt-from-appid": "ffa-goods",
            "x-tt-from-end": "PC",
            "x-tt-from-page": "https://fxg.jinritemai.com/ffa/g/list",
            "x-tt-from-version": "1.0.1.511",
        }

        url = "https://fxg.jinritemai.com/product/tproduct/list"
        params = {
            "page": "0",
            "pageSize": "20",
            "id_name_code": str(goodsid),
            "draft_status": "0",
            "comment_percent": "",
            "group_id": "",
            "sku_type": "",
            "tab": "onSale",
            "business_type": "4",
            "is_online": "1",
            "not_for_sale_search_type": "1",
            "from_mng": "1",
            "check_status": "3",
            "status": "0",
            "supply_status": "",
            "need_auto_rectify_info": "true",
            "need_pay_no_stock_skus": "true",
            "order_field": "audit_time",
            "sort": "desc",
            "appid": "1",
            "_bid": "ffa_goods",
            "_lid": "468012705947",
        }

        response = requests.get(url, headers=headers, cookies=cookie_dict, params=params, timeout=15)
        response.raise_for_status()
        resp_json = response.json()

        if not resp_json.get("data"):
            result["message"] = "抖音商品列表接口未返回商品数据（商品可能不存在或 Cookie 失效）"
            return result

        shopxx = resp_json['data'][0]

        zl['goods_name'] = shopxx['name']
        zl['mainimgurls'] = shopxx['pics']
        zl['detailimgurls'] = shopxx['pics']
        zl['created_at'] = time_str_to_timestamp(shopxx['create_time'])
        zl['min_group_price'] = shopxx['price_lower']
        zl['max_group_price'] = shopxx['price_higher']
        zl['sold_quantity'] = shopxx['sell_num']

        zl['values'] = extract_key_and_name(shopxx['product_format_new'])
        result["goods_name"] = shopxx['name']

        try:
            skutypes, skudetails, product_format = getzheskushuju(cookie_dict, goodsid)
            zl['values'] = product_format
            zl['skutypes'] = skutypes
            zl['skudetails'] = skudetails
        except Exception as e:
            print(f"获取规格详情失败，使用权限缺失兜底：{e}")
            zl['skutypes'] = [{"skutypename": "权限缺失", "values": ["权限缺失"]}]
            zl['skudetails'] = [{"skuname": "权限缺失", "sku_id": 111000, "price": 0, "quantity": 0}]

        exists_again = check_product_exists(shop_id, goodsid, platform="douyin")
        if exists_again is True:
            result["ok"] = True
            result["skipped"] = True
            result["message"] = f"知识库已存在商品 {goodsid}，跳过上传"
            return result
        if exists_again is None:
            result["message"] = "上传前知识库检查失败，为避免重复，跳过上传"
            return result

        upload_product_to_knowledge(zl, platform="douyin")
        result["ok"] = True
        result["uploaded"] = True
        result["message"] = f"抖音商品 {goodsid} 已成功写入知识库"
        return result

    except requests.HTTPError as e:
        result["message"] = f"HTTP 请求失败：{e}"
        return result
    except requests.RequestException as e:
        result["message"] = f"网络异常：{type(e).__name__}: {e}"
        return result
    except Exception as e:
        result["message"] = f"{type(e).__name__}: {e}"
        return result


# ============================================================================
# 本地测试运行入口
# ============================================================================
if __name__ == '__main__':
    print("========== 开始执行本地测试 ==========")

    # 请在此处填入真实的 Cookie 字符串
    test_cookies = """
    填入你的完整 Cookie 字符串
    """.replace("\n", "").strip()

    # 请填入你要抓取的商品 ID
    test_goodsid = "填入商品ID"

    if not test_cookies or not test_goodsid:
        print("⚠️ 请先在代码底部填入 test_cookies 和 test_goodsid！")
    else:
        # 调用核心函数
        res = huoqushangp(test_cookies, test_goodsid)

        # 打印结果
        print("\n========== 执行结果 ==========")
        print(f"是否成功: {res['ok']}")
        print(f"提示信息: {res['message']}")
        print(f"店铺 ID: {res['shop_id']}")
        print(f"商品 ID: {res['goodsid']}")
        print(f"商品名称: {res['goods_name']}")
        print(f"是否上传: {res['uploaded']}")
        print(f"是否跳过: {res['skipped']}")
        print("==============================")