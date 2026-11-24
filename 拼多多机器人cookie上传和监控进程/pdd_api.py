import requests
import execjs
import time
import json
from datetime import datetime, timedelta
import string
import hashlib
import random
import math
import base64
import sys
from pathlib import Path
from session_manager import get_session

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

with open(APP_DIR / 'anti.js', 'r', encoding='utf-8') as f:
    anti_code = f.read()

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

#获取用户商品信息
def pddorderxx(userid,cookies):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    }
    url = "https://mms.pinduoduo.com/latitude/order/userAllOrder"
    data = {
        "pageNo": 1,
        "pageSize": 10,
        "showHistory": True,
        "uid": str(userid)
    }
    data = json.dumps(data, separators=(',', ':'))
    session = get_session()
    with session.post(url, headers=headers, cookies=cookies, data=data) as response:
        if response.json()['success']==True:
            if response.json()['result']['total']==0:
                return None
            else:
                ordertest=response.json()
                orderzl={
                    'goodsid':ordertest["result"]["orders"][0]["orderGoodsList"]["goodsId"],
                    'orderid':ordertest["result"]["orders"][0]["orderSn"],
                    'orderstatus':ordertest["result"]["orders"][0]["orderStatusStr"],
                    'money':round(int(ordertest["result"]["orders"][0]['orderAmount'])/100,2),
                    'ordertime':int(ordertest["result"]["orders"][0]["payTime"])*1000,
                    'shopid':ordertest["result"]["orders"][0]["mallId"],
                }
                return orderzl
        else:
            return None

#当前用户的足迹信息
def pddzhujuid(userid,cookies):
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"99\", \"Google Chrome\";v=\"145\", \"Chromium\";v=\"145\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    }
    url = "https://mms.pinduoduo.com/latitude/goods/singleRecommendGoods"
    data = {
        "type": 2,
        "uid": str(userid),
        "pageNum": 1,
        "pageSize": 10
    }
    data = json.dumps(data, separators=(',', ':'))
    session = get_session()
    with session.post(url, headers=headers, cookies=cookies, data=data) as response:
        if response.json()['success']==True:
            if response.json()['result']['total']==0:
                return None
            return response.json()["result"]["headGoods"]["goodsId"]
        else:
            return None

# 查询用户聊天内容接口（整理完成）
def get_messages(cookies, uid, msg_id):
    url = "https://mms.pinduoduo.com/latitude/search/message/getMessages"
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "anti-content": anti,
        "cache-control": "max-age=0",
        "content-type": "application/json",
        "etag": "5u0ykjoo2XJqRzjnRpMgUdP8QnMlmDgi",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/mms-chat/search?msfrom=mms_sidenav",
        "sec-ch-ua": "\"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\", \"Microsoft Edge WebView2\";v=\"138\", \"Not)A;Brand\";v=\"8\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
    }

    # 当天时间范围
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)
    start_timestamp = int(start_of_day.timestamp())
    end_of_day = start_of_day + timedelta(days=1) - timedelta(seconds=1)
    end_timestamp = int(end_of_day.timestamp())

    data = {
        "uid": uid,
        "pageSize": 100,
        "startTime": start_timestamp,
        "endTime": end_timestamp,
        "msgId": msg_id,
        "keywords": ""
    }
    data = json.dumps(data, separators=(',', ':'))
    response = requests.post(url, headers=headers, cookies=cookies, data=data, timeout=15)
    ttt='无'
    tututut='无'
    if len(response.json()['result']['contentList'])>6:
        duihuas=response.json()['result']['contentList'][-6:]
    else:
        duihuas=response.json()['result']['contentList']
    for duihua in duihuas:
        if duihua['direction']==False:
            ttt+=f'买家:{duihua["content"]};\r'
        else:
            ttt+=f'卖家:{duihua["content"]};\r'
        if 'http' in duihua["content"]:
            tututut+=f'{duihua["content"]},'
    return ttt,tututut

# 商家发送信息接口
def pddsendmassage(cookies, mell_uid, uid, content, img=None, max_retries=2):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": f"anti_{int(time.time())}",
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "referer": "https://mms.pinduoduo.com/chat-merchant/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    url = "https://mms.pinduoduo.com/plateau/chat/send_message"

    def get_random(global_uid: str, uid: str, text: str) -> str:
        def random_to_string(length=16, seed=''):
            chars = string.ascii_lowercase + string.digits
            result = seed + ''.join(random.choices(chars, k=length))
            return result[:length] if len(result) >= length else random_to_string(length, result)

        base_str = '@'.join([str(global_uid), str(uid), str(text), "rpZigw#&iy$!KQD8"])

        def md5_custom(input_string: str) -> str:
            # 用标准库 hashlib 实现 MD5 计算并转为 hex 字符串
            md5_hash = hashlib.md5(input_string.encode('utf-8')).digest()
            return ''.join(f'{byte:02x}' for byte in md5_hash)

        part1 = md5_custom(base_str)[:16]
        part2 = md5_custom(random_to_string())[:16]
        return part1 + part2

    def get_hash(uid: str) -> str:
        data = f"uid={uid}&mall_id=undefined&request_id={int(time.time() * 1000)}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

    def get_base64_image_size(base64_str: str) -> int:
        """
        计算Base64格式图片的原始字节大小
        参数:
            base64_str: 包含Base64编码的字符串（可含data URI前缀，如data:image/png;base64,）
        返回:
            图片原始大小（字节数，int）
        """
        # 步骤1：去除data URI前缀（如存在）
        if 'base64,' in base64_str:
            base64_str = base64_str.split('base64,')[1]
        # 步骤2：去除所有换行符（\n、\r），避免影响长度计算
        base64_str = base64_str.replace('\n', '').replace('\r', '')
        # 步骤3：计算处理后的Base64字符串长度
        processed_length = len(base64_str)

        return processed_length * 3 // 4

    for attempt in range(max_retries):
        try:
            pdd_random = get_random(mell_uid, uid, content)
            pdd_hash = get_hash(uid)

            data = {
                "data": {
                    "cmd": "send_message",
                    "request_id": int(time.time() * 1000),
                    "message": {
                        "to": {"role": "user", "uid": uid},
                        "from": {"role": "mall_cs"},
                        "ts": int(time.time()),
                        "content": content if not img else img['url'],
                        "msg_id": None,
                        "type": 0 if not img else 1,
                        "is_aut": 0,
                        "manual_reply": 1,
                        "status": "read",
                        "is_read": 1,
                        "hash": pdd_hash
                    },
                    "random": pdd_random
                },
                "client": "WEB",
                "anti_content": f"anti_{int(time.time())}"
            }

            # 图片处理
            if img:
                with open(img['path'], "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                data['data']['message']['size'] = {
                    "height": img['height'],
                    "width": img['width'],
                    "image_size": math.ceil(get_base64_image_size('data:image/png;base64,' + b64) / 1024)
                }
                data['data']['message']['info'] = {"thumb_data": b64}

            data = json.dumps(data, separators=(',', ':'))
            session = get_session()
            with session.post(url, headers=headers, cookies=cookies, data=data, timeout=10) as res:
                if res.status_code >= 500 and attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

                return res.json()

        except Exception as e:
            if attempt >= max_retries - 1:
                return {"success": False, "error": str(e)}
            time.sleep(2 ** attempt)


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
    with session.get(url, headers=headers, cookies=cookies) as response:
        try:
            return response.json()['result']['mall_name']
        except:
            return response.json()['error_msg']


#查询账号转移列表接口
def pddtransfer_query(cookies):
    """Return PDD's transferable-CS mapping keyed by the real ``csid``.

    The value's ``id`` is the middle-platform human account ID; it cannot be
    passed to ``move_conversation`` directly.
    """
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
    data = {
        "data": {},
        "client": "WEB",
        "anti_content": anti
    }

    session = get_session()
    with session.post(
        url,
        headers=headers,
        cookies=cookies,
        data=json.dumps(data, separators=(',', ':')),
        timeout=10,
    ) as resp:
        resp.raise_for_status()
        response_data = resp.json()

    cs_list = (response_data.get("result") or {}).get("csList") or {}
    if not isinstance(cs_list, dict):
        raise RuntimeError(f"getAssignCsList returned an invalid csList: {response_data!r}")
    return cs_list


def pddresolve_csid(cookies, human_account_id):
    """Resolve a configured human account ID to the required PDD ``csid``."""
    target_id = str(human_account_id).strip()
    if not target_id:
        return None

    for csid, account in pddtransfer_query(cookies).items():
        account_id = account.get("id") if isinstance(account, dict) else account
        if str(account_id).strip() == target_id:
            return str(csid)
    return None


def pddmove_conversation(cookies, csid, uid):
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "cache-control": "no-cache",
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "pragma": "no-cache",
        "priority": "u=1, i",
        "sec-ch-ua": "\"Not;A=Brand\";v=\"99\", \"Microsoft Edge\";v=\"139\", \"Chromium\";v=\"139\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36 Edg/139.0.0.0",
        "anti-content": anti
    }
    url = "https://mms.pinduoduo.com/plateau/chat/move_conversation"
    csid_value = int(csid) if str(csid).isdigit() else csid
    # 构造请求数据
    data = {
        "data": {
            "cmd": "move_conversation",
            "request_id": int(time.time() * 1000),
            "conversation": {
                "csid": csid_value,
                "uid": uid,
                "need_wx": False,
                "remark": "无原因直接转移"
            },
            "anti_content": anti
        },
        "client": "WEB",
        "anti_content": anti
    }

    data = json.dumps(data, separators=(',', ':'))

    try:
        session = get_session()
        with session.post(url, headers=headers, cookies=cookies, data=data, timeout=10) as response:
            res_json = response.json()
            return res_json
    except Exception as e:
        print(f"{uid}|转移异常: {e}")
        return False


def xiangying(cookies):
    anti = execjs.compile(anti_code).call("get_anti", int(time.time()))
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
        "anti-content": anti,
        "cache-control": "max-age=0",
        "content-type": "application/json",
        "etag": "5u0ykjoo2XJqRzjnRpMgUdP8QnMlmDgi",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/mms-chat/search?msfrom=mms_sidenav",
        "sec-ch-ua": "\"Chromium\";v=\"138\", \"Microsoft Edge\";v=\"138\", \"Microsoft Edge WebView2\";v=\"138\", \"Not)A;Brand\";v=\"8\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0"
    }
    url = "https://mms.pinduoduo.com/plateau/chat/latest_conversations"
    # 构建请求数据
    data = {
        "data": {"offset": 1, "size": 20},
        "client": 1,
        "anti_content": anti
    }
    session = get_session()
    with session.post(url=url, headers=headers, json=data, cookies=cookies) as response:
        result=response.json()
        conversations=result['result']['conversations']
        return conversations


