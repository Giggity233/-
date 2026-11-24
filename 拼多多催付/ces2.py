import requests
import execjs

with open('anti.js', 'r', encoding='utf-8') as f:
    anti_code = f.read()
anti = execjs.compile(anti_code).call("get_anti")
headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "anti-content":anti,
    "content-type": "application/json",
    "priority": "u=1, i",
    "referer": "https://mms.pinduoduo.com/chat-merchant/",
    "sec-ch-ua": "\"Not-A.Brand\";v=\"99\", \"Google Chrome\";v=\"157\", \"Chromium\";v=\"157\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
}
cookies ={
    "x-visit-time": "1795448242250",
    "_bee": "avEOtsGOwcge0A0O3y43QWyKqEY8TQAt",
    "rckk": "avEOtsGOwcge0A0O3y43QWyKqEY8TQAt",
    "api_uid": "CkldV2rbekTAbABVoL5XAg==",
    "_nano_fp": "XpmbX5mjl0dJX0TYnT_o3EzzpoN03aIAnnkbMTA8",
    "ru2k": "35d582e0-dcea-46b4-9975-6bf32d2d1240",
    "ru1k": "f3d85ced-4186-473d-8329-0c1ed9d0c826",
    "_f77": "f3d85ced-4186-473d-8329-0c1ed9d0c826",
    "mms_b84d1838": "3616,3706,3523,3660,3709,3614,3599,3605,3677,3531,3559,3687,3754,3482,1202,1203,1204,1205,3417",
    "JSESSIONID": "E7BEC4DAA9C59B0961D8D76676318D86",
    "PASS_ID": "1-af+PXtYUj8U8Mkc0eWB8+C0uz5YXHtkMZ6P3eBVlDZ/LjYUIFNRvM0aENCMnVQvBN/sLWHEHVKOYKyo9gHbOkQ_582453883_191797286",
    "_a42": "35d582e0-dcea-46b4-9975-6bf32d2d1240"
}
url = 'https://mms.pinduoduo.com/chats/unpaidOrders'
params = {
    "pageNo": "1",
    "pageSize": "10"
}
response = requests.get(url, headers=headers, cookies=cookies, params=params)

print(response.text)
print(response)