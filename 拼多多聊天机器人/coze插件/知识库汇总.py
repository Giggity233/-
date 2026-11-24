# -*- coding: utf-8 -*-
"""
Coze 插件：知识库汇总（商品资料 + 全部有效知识，一次拿全）
========================================================================
用途：对话流里按「店铺 + 商品」一次取到该商品能用的全部资料，直接喂给大模型。

调的是中控平台的统一出口：POST /api/v1/ai/knowledge/resolve/
    返回 data 里同时有：
        product    商品资料（标题、属性、SKU、主图、详情图）
        knowledge  该商品的有效知识：special_prompts（特殊提示词）/ qas（问答对）/ keywords（关键词）
    知识是四层汇总来的，每条都带 source：customer(客户) / store(店铺) / material(材质) / product(商品)
    关键词还带 match_type：exact(完全一样) / contains(包含)
    该接口不执行 AI 匹配，只按场景（售前/售后）整理好返回。

输入参数（在 Coze 插件入参里配置，名字保持一致）：
    shopid     店铺编号（主程序 WS 推送的 shopid）
    goods_id   商品号（由「获取用户商品信息」插件给）
    user_text  买家消息内容（用来和关键词做命中判断，可空）
    scene      可选，售前 / 售后，默认 售前
    platform   可选，默认 pdd

输出参数（**全部是 str**，不用在 Coze 里做类型转换）：
    status           ok=成功 / fail=平台返回失败 / error=出错
    product          商品资料 JSON 字符串
    special_prompts  特殊提示词：**纯文本**（不是 JSON），按「1，内容\t2，内容\t」拼接
    qas              问答对 JSON 字符串（数组）
    keywords         关键词 JSON 字符串（数组，含 match_type / match_type_name）
    answer           关键词命中结果：user_text 命中关键词时输出它的 answer（命中多条取第一条），没命中输出空字符串
    msg              失败原因
"""
import json

import requests

# ---- 蘑菇头中控平台地址（按实际部署地址改这里）----
BASE_URL = "http://117.72.204.36:8000"
TIMEOUT = 20


def _cheng_wenben(texts):
    """
    把多条文本按「1，内容\\t2，内容\\t」拼成一段纯文本（末尾也带 \\t）
    例：["回复消息不能回复“呀”这个字", "第二条"] -> "1，回复消息不能回复“呀”这个字\t2，第二条\t"
    """
    return "".join("%d，%s\t" % (i + 1, t) for i, t in enumerate(texts))


def _pipei_keyword(user_text, keywords):
    """
    user_text 和关键词做命中判断：命中就返回它的 answer，没命中返回空字符串
    命中多条时按**第一条**算

    按每条关键词自己的 match_type 判断：
        exact    -> user_text 和关键词完全一样才算命中
        contains -> user_text 里包含关键词就算命中（默认）
    """
    for kw in keywords:
        word = str(kw.get("keyword") or "")
        if not word:
            continue
        if str(kw.get("match_type") or "contains") == "exact":
            hit = user_text == word
        else:
            hit = word in user_text
        if hit:
            return str(kw.get("answer") or "")
    return ""


def _shuchu(status, data, answer="", msg=""):
    """
    统一拼出参：**所有字段都是字符串**，避免 Coze 里 str/dict 来回转换出错

    knowledge 拆成三块单独返回：special_prompts（特殊提示词）/ qas（问答对）/ keywords（关键词）
    """
    knowledge = data.get("knowledge") or {}
    # 特殊提示词只取 content，拼成「1，内容\t2，内容\t」的纯文本
    prompts = [str(p.get("content") or "") for p in (knowledge.get("special_prompts") or [])]
    return {
        "status": status,
        "product": json.dumps(data.get("product") or {}, ensure_ascii=False),
        "special_prompts": _cheng_wenben(prompts),
        "qas": json.dumps(knowledge.get("qas") or [], ensure_ascii=False),
        "keywords": json.dumps(knowledge.get("keywords") or [], ensure_ascii=False),
        "answer": str(answer),
        "msg": str(msg)
    }


def handler(args):
    """Coze 插件入口"""
    try:
        shopid = str(args.input.shopid)
        goods_id = str(args.input.goods_id)
        try:
            user_text = str(args.input.user_text)
        except Exception:
            user_text = ""
        try:
            scene = str(args.input.scene) or "售前"
        except Exception:
            scene = "售前"
        try:
            platform = str(args.input.platform) or "pdd"
        except Exception:
            platform = "pdd"

        payload = {"platform": platform, "shopid": shopid, "goods_id": goods_id, "scene": scene}
        resp = requests.post(BASE_URL + "/api/v1/ai/knowledge/resolve/", json=payload, timeout=TIMEOUT)
        ret = resp.json()

        if ret.get("ok") is not True:
            return _shuchu("fail", {}, msg=str(ret.get("message"))[:200])

        data = ret.get("data") or {}
        keywords = (data.get("knowledge") or {}).get("keywords") or []
        return _shuchu("ok", data, answer=_pipei_keyword(user_text, keywords))
    except Exception as e:
        return _shuchu("error", {}, msg=str(e))