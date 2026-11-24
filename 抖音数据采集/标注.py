import requests
cookies = {
    "ttwid": "1%7CvIK6Lk2YUcz2Qe4_omHsyM8eGiOu8pZfAR2kP9Y22bU%7C1789582622%7C5d74cf2ab4525b3f719592beb8a2ebb24ba881c216f033967044109bd3b40f85",
    "passport_csrf_token": "90b23a706516fa1138622613d1c72b36",
    "passport_csrf_token_default": "90b23a706516fa1138622613d1c72b36",
    "passport_mfa_token": "Cjc6sBBcrd4QuZZrtjowgKcrcw4PNIXd0tuqR8KL7TgXDnP6LM5%2FWnZNEnoM8AK0KQD3FAd4nWUzGkoKPAAAAAAAAAAAAABQ6HoHszO1%2BezEzb5k2zz3HDNJQAA33lt7EOuu8tkzuO%2BF4rcOTP8ph9x%2FV%2B6dAyPzehCtuJwOGPax0WwgAiIBA4c8Uus%3D",
    "odin_tt": "d0928f076daa601920be7973d34438546b28e7c71843c0c9f3c42a3853f5f769f0d2767ef21abd448df6e6ade61e76948a24e42578657f7aba5c2f0068cf133c",
    "passport_auth_status": "4cac31ef8f25fb55b483fb0e86e0674b%2C",
    "passport_auth_status_ss": "4cac31ef8f25fb55b483fb0e86e0674b%2C",
    "uid_tt": "409633199acbb54b745c5f97fffa837b",
    "uid_tt_ss": "409633199acbb54b745c5f97fffa837b",
    "sid_tt": "10f194d5781cd4b813033553d099bebe",
    "sessionid": "10f194d5781cd4b813033553d099bebe",
    "sessionid_ss": "10f194d5781cd4b813033553d099bebe",
    "is_staff_user": "false",
    "has_biz_token": "false",
    "PHPSESSID": "097ea96707139e04563679dcbe3e49f7",
    "PHPSESSID_SS": "097ea96707139e04563679dcbe3e49f7",
    "ecom_us_lt": "8f028cd8b1a60702231faf88a980bb02ea4b23e1fc7aa7fb8b993acf2f2abc52",
    "ecom_us_lt_ss": "8f028cd8b1a60702231faf88a980bb02ea4b23e1fc7aa7fb8b993acf2f2abc52",
    "ucas_c0": "CkEKBTEuMC4wELKIkpScq7fVahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DxuqvVBkjx7ufXBlCavL7M0J7902lYbxIUcpGR9axes6gwTmC5JLYgIDyhgew",
    "ucas_c0_ss": "CkEKBTEuMC4wELKIkpScq7fVahjmJiCk0aC5gK2mBiiwITDA79Cwls3QA0DxuqvVBkjx7ufXBlCavL7M0J7902lYbxIUcpGR9axes6gwTmC5JLYgIDyhgew",
    "sid_guard": "10f194d5781cd4b813033553d099bebe%7C1789582712%7C5184000%7CSun%2C+15-Nov-2026+18%3A18%3A32+GMT",
    "session_tlb_tag": "sttt%7C13%7CEPGU1Xgc1LgTAzVT0Jm-vv________-wid0hW68fEjk3-l_rBPu_5vaiEyOgpm3pJ3e022GgkFY%3D",
    "sid_ucp_v1": "1.0.0-KDY5ZmFlYzE4NmI2OTE3Yzg5Yzg2MDQyYmMzZTc2ZWY3NDQ4OWU2NzkKGQjA79Cwls3QAxD4uqvVBhiwISAMOAJA8QcaAmhsIiAxMGYxOTRkNTc4MWNkNGI4MTMwMzM1NTNkMDk5YmViZQ",
    "ssid_ucp_v1": "1.0.0-KDY5ZmFlYzE4NmI2OTE3Yzg5Yzg2MDQyYmMzZTc2ZWY3NDQ4OWU2NzkKGQjA79Cwls3QAxD4uqvVBhiwISAMOAJA8QcaAmhsIiAxMGYxOTRkNTc4MWNkNGI4MTMwMzM1NTNkMDk5YmViZQ",
    "COMPASS_LUOPAN_DT": "session_7686196306578456886",
    "ecom_us_lt_buyin_top": "5073f75539d5658172ce76f780475c213c5afdab94714343226a180877d5df58",
    "ecom_us_lt_ss_buyin_top": "5073f75539d5658172ce76f780475c213c5afdab94714343226a180877d5df58",
    "SHOP_ID": "266072853",
    "PIGEON_CID": "7613323028357684762"
}

#专员咨询量，店铺咨询量，平均响应时间，专员超时数量
#{'servConvCnt': 2, 'inChatNum': 0, 'avgRespDuration': '3分20秒', 'workTimeThreeMinRespRate': '50.00%', 'shopservConvCnt': 2, 'shopinChatNum': 0}
def getzhequeryStaffData(cookies):
    thisaccountid=cookies['PIGEON_CID']
    headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9",
        "origin": "https://im.jinritemai.com",
        "priority": "u=1, i",
        "referer": "https://im.jinritemai.com/",
        "sec-ch-ua": "\"Google Chrome\";v=\"153\", \"Not_A Brand\";v=\"8\", \"Chromium\";v=\"153\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
        "x-secsdk-csrf-token": "DOWNGRADE"
    }
    url = 'https://pigeon.jinritemai.com/backstage/queryStaffData'
    params = {
        "_pms": "1",
        "queryType": "1",
        "startTime": "20260920",
        "endTime": "20260920",
        "page": "1",
        "size": "20"
    }
    response = requests.get(url, headers=headers, cookies=cookies, params=params)
    queryStaffDatadata=response.json()
    staffDataModel=queryStaffDatadata["data"]["staffDataModel"]
    accounttestdata={}
    for accountdata in staffDataModel:
        if accountdata["staffUserInfo"]["staffId"]==thisaccountid:
            accounttestdata={
                "servConvCnt":accountdata["servConvCnt"],#专员已接待会话总数
                "inChatNum":accountdata["inChatNum"],#专员正在接待会话总数
                "avgRespDuration":accountdata["avgRespDuration"],#专员3分钟平均响应，
                "workTimeThreeMinRespRate":accountdata["workTimeThreeMinRespRate"]["fieldValue"],#专员3分钟回复率
                "shopservConvCnt":queryStaffDatadata["data"]["shopSumDetailModel"]["servConvCnt"],#店铺已接待会话总数
                "shopinChatNum":queryStaffDatadata["data"]["shopSumDetailModel"]["inChatNum"]#店铺正在接待会话总数
            }
            break
    return accounttestdata

a=getzhequeryStaffData(cookies)
print(a)

