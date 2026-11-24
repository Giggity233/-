# -*- coding: utf-8 -*-
"""
Coze 插件：推发消息
========================================================================
用途：由 Coze 工作流决定发什么，插件负责真正发到买家会话里。
      对应原版 pdd_api.py 的 pddsendmassage / pddsendimg / pddsendvideo。

输入参数（在 Coze 插件入参里配置，名字保持一致）：
    userid      买家 uid（主程序 WS 推送的 userid）
    shopid      店铺 uid（主程序 WS 推送的 shopid）
    cook        浏览器 cookie 字符串（主程序上传的 cook）
    anti        anti.js 密令（主程序上传的 anti，发图片时要用真值）
    content     要发的内容（**类型插件自己判断**，不用传类型）：
                  [视频]::::视频地址      -> 发视频
                  [图片]::::图片地址@@高@@宽@@大小 -> 发图片（@@ 参数可省）
                  这是您的教程图片 https://x/a.jpg  -> 提取链接，按后缀发图片
                  看看这个 https://x/a.mp4           -> 提取链接，按后缀发视频
                  纯文字                              -> 发文字
    height      图片高度（`[图片]::::` 里带 @@ 参数时不需要传）
    width       图片宽度（同上）
    image_size  图片大小 KB（同上）

输出参数：
    status   ok=发送成功 / fail=发送失败 / error=出错
    msg      接口原始返回（截断）或错误原因

判断规则（插件内部完成，不再需要 msg_type）：
    1. 含 [视频]:::: -> 视频，取 :::: 后面的地址
    2. 含 [图片]:::: -> 图片，取 :::: 后面的地址（带 @@ 就顺便拆出高/宽/大小）
    3. 其它情况：内容里找链接，链接以图片后缀结尾 -> 图片，否则 -> 视频（前缀文字丢弃，只发链接）
    4. 内容里没有链接 -> 当纯文字发

说明：
    - 文字消息原版用的是假 anti（anti_时间戳），图片消息才用真 anti，视频消息不用 anti，这里照原版来。
    - cookie 统一放在请求头 Cookie 里（不用转 dict）。
"""
import hashlib
import json
import random
import re
import string
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36")


def md5_custom(input_string):
    return ''.join('%02x' % b for b in hashlib.md5(input_string.encode('utf-8')).digest())


def get_random(global_uid, uid, text):
    """发送接口的 random 参数（拼多多前端算法）"""
    def random_to_string(length=16, seed=''):
        chars = string.ascii_lowercase + string.digits
        result = seed + ''.join(random.choices(chars, k=length))
        return result[:length] if len(result) >= length else random_to_string(length, result)

    base_str = '@'.join([str(global_uid), str(uid), str(text), "rpZigw#&iy$!KQD8"])
    return md5_custom(base_str)[:16] + md5_custom(random_to_string())[:16]


def get_hash(uid):
    """发送接口的 hash 参数"""
    data = "uid=%s&mall_id=undefined&request_id=%s" % (uid, int(time.time() * 1000))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


def base_headers(cook, anti=None):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
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
    if anti:
        headers["anti-content"] = anti
    return headers


def fasong_wenzi(cook, mell_uid, uid, content):
    """发文字：POST /plateau/chat/send_message（原版就是假 anti）"""
    fake_anti = "anti_%s" % int(time.time())
    headers = base_headers(cook, fake_anti)
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
            "random": get_random(mell_uid, uid, content)
        },
        "client": "WEB",
        "anti_content": fake_anti
    }
    resp = requests.post(url, headers=headers,
                         data=json.dumps(data, separators=(',', ':')), timeout=10)
    return resp.json()


def fasong_tupian(cook, anti, mell_uid, uid, url_tupian, height, width, image_size):
    """发图片：同样走 send_message，type=1，这里必须用真 anti"""
    headers = base_headers(cook, anti)
    url = "https://mms.pinduoduo.com/plateau/chat/send_message"
    data = {
        "data": {
            "cmd": "send_message",
            "request_id": int(time.time() * 1000),
            "message": {
                "to": {"role": "user", "uid": uid},
                "from": {"role": "mall_cs"},
                "ts": int(time.time()),
                "content": str(url_tupian),
                "msg_id": None,
                "type": 1,
                "is_aut": 0,
                "manual_reply": 1,
                "status": "read",
                "is_read": 1,
                "hash": get_hash(uid),
                "size": {
                    "height": height,
                    "width": width,
                    "image_size": image_size
                }
            },
            "random": get_random(mell_uid, uid, '')
        },
        "client": "WEB",
        "anti_content": anti
    }
    resp = requests.post(url, headers=headers,
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    return resp.json()


def fasong_shipin(cook, uid, url_shipin):
    """发视频：走平台素材库接口"""
    headers = base_headers(cook)
    url = "https://mms.pinduoduo.com/plateau/message/library_file/send"
    data = {"uid": uid, "url": str(url_shipin)}
    resp = requests.post(url, headers=headers,
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    return resp.json()


# 图片后缀（和底座 clean_media_text 用同一套）
IMG_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg')


def _qu_link(content):
    """从内容里取出第一个链接（去掉尾部标点）"""
    urls = re.findall(r'https?://\S+', content)
    if not urls:
        return ""
    return urls[0].rstrip('，。,.、）)】]"\'！!')


def _shi_tupian(url):
    """按链接后缀判断是不是图片"""
    return url.lower().split('?')[0].endswith(IMG_EXTS)


def _panding(content, height, width, image_size):
    """
    判断要发什么，返回 (类型, 内容, 高, 宽, 大小)；类型：video / image / text
    """
    if '[视频]::::' in content:
        return "video", content.split('::::', 1)[1].strip(), 0, 0, 0

    if '[图片]::::' in content:
        part = content.split('::::', 1)[1].strip()
        if '@@' in part:                        # 原版格式：地址@@高@@宽@@大小
            a = part.split('@@')
            return ("image", a[0],
                    a[1] if len(a) > 1 else height,
                    a[2] if len(a) > 2 else width,
                    a[3] if len(a) > 3 else image_size)
        return "image", part, height, width, image_size

    url = _qu_link(content)                     # 没有前缀 / 带别的前缀：从内容里提取链接
    if not url:
        return "text", content, 0, 0, 0
    if '@@' in url:                             # 提取出来的链接带 @@尺寸，先拆开（和 [图片]:::: 同一套写法）
        a = url.split('@@')
        url = a[0]
        if len(a) > 1 and not height:
            height = a[1]
        if len(a) > 2 and not width:
            width = a[2]
        if len(a) > 3 and not image_size:
            image_size = a[3]
    if _shi_tupian(url):
        return "image", url, height, width, image_size
    return "video", url, 0, 0, 0


def handler(args):
    """Coze 插件入口"""
    try:
        userid = str(args.input.userid)
        shopid = str(args.input.shopid)
        cook = str(args.input.cook)
        anti = str(args.input.anti)
        content = str(args.input.content)

        # 图片尺寸入参（[图片]:::: 里带 @@ 时不需要传）
        def _canshu(name):
            try:
                return str(getattr(args.input, name) or "")
            except Exception:
                return ""
        height = _canshu("height")
        width = _canshu("width")
        image_size = _canshu("image_size")

        leixing, neirong, h, w, s = _panding(content, height, width, image_size)

        if leixing == "video":
            ret = fasong_shipin(cook, userid, neirong)
        elif leixing == "image":
            ret = fasong_tupian(cook, anti, shopid, userid, neirong, h, w, s)
        else:
            ret = fasong_wenzi(cook, shopid, userid, neirong)

        # 判成功：文字/图片看 result.result == 'ok'，视频看 success
        ok = (ret.get('success') is True and (
            ret.get('result', {}).get('result') == 'ok' if isinstance(ret.get('result'), dict) else True))
        return {"status": "ok" if ok else "fail", "msg": json.dumps(ret, ensure_ascii=False)[:400]}
    except Exception as e:
        return {"status": "error", "msg": str(e)}