# -*- coding: utf-8 -*-
"""
Coze 插件：转人工
========================================================================
入参 rgmisid / zrgmisid = 人工ID（如 156335559）
    ↓ 请求 getAssignCsList
在 result.csList 中找到 value.id == 人工ID 的条目
    ↓ 取该条目的 key（如 840820290）作为 csid
用该 csid 调 move_conversation 转接
"""
import hashlib
import json
import random
import string
import time

import requests

BASE_URL = "http://117.72.204.36:8000"
PLATFORM = "pdd"
TIMEOUT = 15

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0")


def pdd_headers(anti, cook):
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


# ===================== 入参兼容层 =====================
def _get_input(args, *keys, default=None):
    """
    兼容两种入参方式：
      1) Coze 真机： args.input.xxx
      2) 本地 dict： args["xxx"] 或 args["input"]["xxx"]
    """
    candidates = []

    # Coze 的 args.input（可能是对象，也可能是 dict）
    try:
        inp = getattr(args, "input", None)
        if inp is not None:
            for k in keys:
                if hasattr(inp, k):
                    candidates.append(getattr(inp, k))
                elif isinstance(inp, dict) and k in inp:
                    candidates.append(inp[k])
    except Exception:
        pass

    # 本地 dict 直传
    if isinstance(args, dict):
        for k in keys:
            if k in args:
                candidates.append(args[k])
        inner = args.get("input")
        if isinstance(inner, dict):
            for k in keys:
                if k in inner:
                    candidates.append(inner[k])

    for v in candidates:
        if v is not None:
            return v
    return default


# ===================== 中控平台 =====================
def jing_shi_tixing(shopid, content):
    """警示提醒：在中控平台建一条紧急待办"""
    try:
        resp = requests.post(BASE_URL + "/api/v1/pending-tasks/create/", json={
            "shop_id": str(shopid),
            "platform": PLATFORM,
            "time_type": "urgent",
            "handling_item": content
        }, timeout=TIMEOUT)
        return resp.json()
    except Exception as e:
        return {"ok": False, "message": str(e)}


# ===================== 拼多多后台 =====================
def md5_custom(input_string):
    return ''.join('%02x' % b for b in hashlib.md5(input_string.encode('utf-8')).digest())


def get_random(global_uid, uid, text):
    def random_to_string(length=16, seed=''):
        chars = string.ascii_lowercase + string.digits
        result = seed + ''.join(random.choices(chars, k=length))
        return result[:length] if len(result) >= length else random_to_string(length, result)

    base_str = '@'.join([str(global_uid), str(uid), str(text), "rpZigw#&iy$!KQD8"])
    return md5_custom(base_str)[:16] + md5_custom(random_to_string())[:16]


def get_hash(uid):
    data = "uid=%s&mall_id=undefined&request_id=%s" % (uid, int(time.time() * 1000))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def fasong_wenzi(cook, shopid, uid, content):
    """发文字（转人工前置语）"""
    fake_anti = "anti_%s" % int(time.time())
    headers = pdd_headers(fake_anti, cook)
    url = "https://mms.pinduoduo.com/plateau/chat/send_message"
    data = {
        "data": {
            "cmd": "send_message",
            "request_id": int(time.time() * 1000),
            "message": {
                "to": {"role": "user", "uid": uid},
                "from": {"role": "mall_cs"},
                "ts": int(time.time()),
                "content": content,
                "msg_id": None,
                "type": 0,
                "is_aut": 0,
                "manual_reply": 1,
                "status": "read",
                "is_read": 1,
                "hash": get_hash(uid)
            },
            "random": get_random(shopid, uid, content)
        },
        "client": "WEB",
        "anti_content": fake_anti
    }
    resp = requests.post(url, headers=headers,
                         data=json.dumps(data, separators=(',', ':')), timeout=10)
    return resp.json()


def huoqu_csid_by_renyuanid(anti, cook, ren_gong_id):
    """
    调用 getAssignCsList，把「人工ID」匹配成「csid」。
    返回: (csid or None, 原始返回)
    """
    url = "https://mms.pinduoduo.com/latitude/assign/getAssignCsList"
    payload = {
        "data": {},
        "client": "WEB",
        "anti_content": anti
    }
    resp = requests.post(url, headers=pdd_headers(anti, cook),
                         data=json.dumps(payload, separators=(',', ':')), timeout=10)
    try:
        ret = resp.json()
    except Exception:
        return None, resp.text

    cs_list = (ret.get("result") or {}).get("csList") or {}
    target = str(ren_gong_id).strip()
    for csid_key, info in cs_list.items():
        # 兼容 info 是 dict 或字符串
        info_id = info.get("id") if isinstance(info, dict) else info
        if str(info_id) == target:
            return csid_key, ret
    return None, ret


def zhuanyi(anti, cook, csid, uid, remark):
    """把会话转给指定客服（csid = csList 的 key）"""
    url = "https://mms.pinduoduo.com/plateau/chat/move_conversation"
    csid_val = int(csid) if str(csid).isdigit() else csid
    data = {
        "data": {
            "cmd": "move_conversation",
            "request_id": int(time.time() * 1000),
            "conversation": {
                "csid": csid_val,
                "uid": uid,
                "need_wx": False,
                "remark": remark
            },
            "anti_content": anti
        },
        "client": "WEB",
        "anti_content": anti
    }
    resp = requests.post(url, headers=pdd_headers(anti, cook),
                         data=json.dumps(data, separators=(',', ':')), timeout=10)
    print(resp.json())
    return resp.json()


def handler(args):
    """Coze 插件入口"""
    shopid = ""
    try:
        userid  = str(_get_input(args, "userid", default=""))
        shopid  = str(_get_input(args, "shopid", default=""))
        cook    = str(_get_input(args, "cook",   default=""))
        anti    = str(_get_input(args, "anti",   default=""))
        remark  = _get_input(args, "remark", default="无原因直接转移")
        # 兼容两种字段名：zrgmisid / rgmisid
        rgmisid = str(_get_input(args, "zrgmisid", "rgmisid", default="")).strip()

        if not rgmisid:
            msg = "传入的 rgmisid/zrgmisid 为空，无法执行转接"
            jing_shi_tixing(shopid, "店铺%s 转人工失败：%s" % (shopid, msg))
            return {"status": "no_account", "csid": "", "msg": msg}

        # 1. 前置话术
        fasong_wenzi(cook, shopid, userid, "稍等亲亲，这边让对接客服来回复您")

        # 2. 人工ID → csid
        csid, raw = huoqu_csid_by_renyuanid(anti, cook, rgmisid)
        if not csid:
            raw_str = json.dumps(raw, ensure_ascii=False)[:200] if isinstance(raw, dict) else str(raw)[:200]
            msg = "未在 getAssignCsList 中匹配到人工ID=%s 对应的csid；返回原文: %s" % (rgmisid, raw_str)
            jing_shi_tixing(shopid, "店铺%s 转人工失败：%s" % (shopid, msg))
            return {"status": "no_account", "csid": "", "msg": msg}

        # 3. 转接
        ret = zhuanyi(anti, cook, csid, userid, remark)
        ok = ret.get('success') is True and ret.get('result', {}).get('result') == 'ok'
        return {"status": "ok" if ok else "fail", "csid": str(csid),
                "msg": json.dumps(ret, ensure_ascii=False)[:300]}
    except Exception as e:
        err_msg = str(e)
        jing_shi_tixing(shopid, f"店铺{shopid} 转人工插件异常：{err_msg}")
        return {"status": "error", "csid": "", "msg": err_msg}


