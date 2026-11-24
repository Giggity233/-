# -*- coding: utf-8 -*-
"""
pdd_api.py —— 本地只保留三个接口
========================================================================
发送消息、转人工、订单查询、聊天记录查询等都已迁到 Coze 插件（见 coze插件 目录），
本地不再需要，全部删除。剩下这三个是本地流程必需的：

    pddanti()          生成 anti 密令（上传给 Coze 的 anti 参数）
    pddchange_state()  强制客服在线（不在线收不到 WS 推送）
    pddgetshopname()   取店铺名（只用于日志）
"""
import execjs
import time
import json
import sys
from pathlib import Path
from session_manager import get_session


_app_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent
with open(_app_dir / 'anti.js', 'r', encoding='utf-8') as f:
    anti_code = f.read()


def pddanti():
    # 生成 anti 密令（上传给 Coze 的 anti 参数）
    return execjs.compile(anti_code).call("get_anti", int(time.time()))


#改成在线的状态,state为1时，在线，为0时，离线
##{'success': True, 'result': {'result': 'ok', 'server_time': 1773211625791, 'response': 'set_csstatus', 'request_id': 1773211628219, 'status': 3}}
def pddchange_state(cookies, state):
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    }
    url = "https://mms.pinduoduo.com/plateau/chat/set_csstatus"
    data = {
        "data": {
            "cmd": "set_csstatus",
            "request_id": int(time.time() * 1000),
            "status": state,
            "anti_content":anti
        },
        "client": "WEB",
        "anti_content": anti
    }
    data_json = json.dumps(data, separators=(',', ':'))
    session = get_session()
    with session.post(url=url, data=data_json, headers=headers, cookies=cookies, timeout=8) as response:
        return response.json()


#查询账号转移列表接口（本地启动预检用：看该店铺能转给谁）
def pddtransfer_query(cookies):
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "sec-ch-ua": "\"Chromium\";v=\"136\", \"Google Chrome\";v=\"136\", \"Not.A/Brand\";v=\"99\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    }
    url = "https://mms.pinduoduo.com/latitude/assign/getAssignCsList"
    data = {"wechatCheck": True}

    session = get_session()
    with session.post(url, headers=headers, cookies=cookies, json=data, timeout=10) as resp:
        return resp.json()["result"]["csList"]


#商家店铺名获取接口
def pddgetshopname(cookies):
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "anti-content": anti,
        "cache-control": "max-age=0",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/mallcenter/changeAccountInfo/accountSetting/accountInfo",
        "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\", \"Microsoft Edge\";v=\"144\", \"Microsoft Edge WebView2\";v=\"144\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0"
    }
    url = "https://mms.pinduoduo.com/earth/api/mallInfo/commonMallInfo"
    session = get_session()
    with session.get(url, headers=headers, cookies=cookies, timeout=15) as response:
        return response.json()['result']['mall_name']


if __name__ == '__main__':
    print(pddanti())
