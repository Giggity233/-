import requests
from session_manager import get_session

def csdlfou(cookie):
    headers = {
        "accept": "*/*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
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
    with session.get(url, headers=headers, cookies=cookie) as response:
        return response.json()

def jianyandl(page,shoptest):
    page.get('https://mms.pinduoduo.com/login/')
    page.ele('x://div[text()="账号登录"]').click(by_js=True)
    page.ele('x://input[@id="usernameId"]').input(shoptest['username'])
    page.wait(1)
    page.ele('x://input[@id="passwordId"]').input(shoptest['password'])
    page.wait(1)
    page.ele('x://button[./span[text()="登录"]]').click(by_js=True)
    page.wait(5)
    cookies=page.cookies().as_dict()
    aaa=csdlfou(cookies)
    bbb=aaa.get('error_msg','')
    if bbb=='会话已过期':
        return False
    else:
        page.get('https://mms.pinduoduo.com/chat-merchant/#/')
        return True

