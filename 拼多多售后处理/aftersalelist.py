import json
import os
import requests

def read_shop_list():
    """
    读取脚本同级目录下的 shop.json，返回其中的 shop 列表。

    :return: list，例如 ["义乌创泽日用品厂", "璀璨原石店", "义乌创创日用品厂"]
    """
    # 以脚本所在目录为基准，避免受运行目录影响
    base_dir = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(base_dir, "shop.json")

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("shop", [])

def cookie_to_json(cookie_str: str) -> dict:
    """
    输入：str 格式的 cookie 字符串
    输出：JSON 字符串
    """
    result = {}

    for item in cookie_str.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue

        key, value = item.split("=", 1)   # 只切第一个 '='，保留 value 中的 '='
        key = key.strip()
        value = value.strip()

        # 去掉首尾引号，如 token="abc"
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]

        if key:
            result[key] = value

    return result

def getzhecookie():
    response = requests.get(
        "http://117.72.204.36:8000/api/v1/cookies/",
        params={"platform": "拼多多"},
        timeout=15,
    )
    return response.json()['data']


def getzhequeryList(cookies):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9",
        "cache-control": "max-age=0",
        "content-type": "application/json",
        "etag": "BzKVFWmX7s2aoJz02iOKn4I0y8eVMFft",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/aftersales/aftersale_list",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"8\", \"Chromium\";v=\"156\", \"Google Chrome\";v=\"156\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
    }
    url = 'https://mms.pinduoduo.com/mercury/mms/afterSales/queryList'
    data = {
        "pageSize": 100,
        "pageNumber": 1,
        "quickSearchType": 7,
        "orderByCreatedAtDesc": True
    }
    response = requests.post(url, headers=headers, cookies=cookies, json=data)
    return response.json()['result']['list']


shoplist=read_shop_list()
allcookiesxx=getzhecookie()
for cookiesxx in allcookiesxx:
    if cookiesxx["shop_name"] in shoplist:
        cookies=cookie_to_json(cookiesxx["cookie"])
        queryList=getzhequeryList(cookies)
        for query in queryList:
            if query['afterSalesTypeName']=="退款":
                print("处理")
        print(queryList)


