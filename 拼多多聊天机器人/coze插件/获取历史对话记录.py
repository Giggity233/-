# -*- coding: utf-8 -*-
"""
Coze 插件：获取历史对话记录
========================================================================
用途：对话流里按 uid 拉取当天聊天记录，供大模型理解上下文。

输入参数（在 Coze 插件入参里配置，名字保持一致）：
    userid         买家 uid（主程序 WS 推送的 userid）
    msgid          消息 id（主程序 WS 推送的 msgid）
    anti           anti.js 密令（主程序上传的 anti）
    cook           浏览器 cookie 字符串（主程序上传的 cook）
    history_count  可选，取最近多少条对话，默认 15
    page_size      可选，接口一次拉取条数，默认 100

输出参数：
    total_count    当天该用户的真实消息总数
    chatjl         买卖双方对话文本，形如「买家:xxx,\\r卖家:yyy,\\r」
    chatimg        对话里出现过的图片链接（逗号分隔）
    error          出错时的原因（正常为空串）
"""
import json
from datetime import datetime, timedelta

import requests

# 拼多多商家后台请求头（登录态由 cook 提供）
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0")


def get_messages(uid, msg_id, anti, cook, history_count=15, page_size=100):
    """
    拉取当天聊天记录

    返回：(total_count, chatjl, chatimg)
    """
    url = "https://mms.pinduoduo.com/latitude/search/message/getMessages"
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": anti,          # 风控参数，由主程序实时生成后传入
        "cache-control": "max-age=0",
        "content-type": "application/json",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/mms-chat/search?msfrom=mms_sidenav",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": UA,
        "Cookie": cook                 # 直接把 cookie 字符串塞进请求头
    }

    # 当天 00:00:00 ~ 23:59:59
    now = datetime.now()
    start_of_day = datetime(now.year, now.month, now.day)
    data = {
        "uid": uid,
        "pageSize": page_size,
        "startTime": int(start_of_day.timestamp()),
        "endTime": int((start_of_day + timedelta(days=1) - timedelta(seconds=1)).timestamp()),
        "msgId": msg_id,
        "keywords": ""
    }

    resp = requests.post(url, headers=headers,
                         data=json.dumps(data, separators=(',', ':')), timeout=15)
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError("接口返回失败: %s" % str(result)[:200])

    content_list = result["result"]["contentList"]
    total_count = len(content_list)

    # 只取最近 history_count 条
    duihuas = content_list[-history_count:] if total_count > history_count else content_list

    ttt = ''        # 对话文本
    tututut = ''    # 图片链接
    for duihua in duihuas:
        if duihua['direction'] is False:
            ttt += '买家:%s,\r' % duihua["content"]
        else:
            ttt += '卖家:%s,\r' % duihua["content"]
        if 'http' in duihua["content"]:
            tututut += '%s,' % duihua["content"]

    if not ttt:
        ttt = "无"
    if not tututut:
        tututut = "无"
    if tututut.endswith(','):
        tututut = tututut[:-1]

    return total_count, ttt, tututut


def handler(args):
    """Coze 插件入口"""
    try:
        userid = str(args.input.userid)
        msgid = str(args.input.msgid)
        anti = str(args.input.anti)
        cook = str(args.input.cook)

        # 可选参数：没填时用默认值
        try:
            history_count = int(args.input.history_count)
        except Exception:
            history_count = 15
        try:
            page_size = int(args.input.page_size)
        except Exception:
            page_size = 100

        total_count, chatjl, chatimg = get_messages(
            userid, msgid, anti, cook, history_count, page_size)

        return {
            "total_count": total_count,
            "chatjl": chatjl,
            "chatimg": chatimg,
            "error": ""
        }
    except Exception as e:
        # 出错时也按约定返回，避免对话流中断
        return {
            "total_count": 0,
            "chatjl": "无",
            "chatimg": "无",
            "error": str(e)
        }