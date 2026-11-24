import requests


headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "anti-content": "0asAfoOqYySgYgd9l0nlqvqtv3gtPpyPt_CH3OUH3OE4SyKW-a_teZkI_2FY8aOHNFc-S_j6Z_sEcKQppwtZSPfA4CdKGySi_2k11T1EIyEGyPhnkf4Zo52d3xgX-8bJCahVhu9wysoLmCni96-i5ByeW5pvEDuQdqifpk8EjK27be49ynIRcOTPzrIINPxmERbp-q1IYBuzg4GHglNCYITPn36uLsfWPC1dQZ21wKkCcIQihU2I2t7Y4nb_Dx6vc95HEqzEfuETUiCMyVgqLsshPvATQg7KVDwtLVjJP0v5KhTLhCktI8DhS6F5MvEfi3gDL6ANwJHu6oQ0zfrYOkVNjpZbRjUmP4Kq8nWLerSJ0XmhUJjaCBjBAGeIfE3qp0fe9eImZ1mdYMC4p7fanvUVnSLNkULUlNcu7UnfZh6j_x4Pf5HeOe-X3Nx47Dzecue5IAkRf6NCX5J64ytH8fHB-DdEWzxI4C_ENdHDTx_5i7K06YcTfOEqQDw3PGMRcCeMccF6e1-wPtwUg8lXFkGC4YNDWw39NQRUrTZfxtYfqtwd6OKeJxtnX_TG50D7hw3t_KnxEuQNUew_obK--HHaE1p4ZcBsQcbF6lQ2gu6hdgQuNzvHKcMbjsVktsuBwGeNfZSczoZtLes3rC5nR5oRvUFMw4mih5UamB9lRkK67Qtr15WMGeBqvf9uKxf7mCFgb3EW8Rtrcap7AJWEy8JnhvsioJCQJMyyFLqK8wi8",
    "cache-control": "max-age=0",
    "content-type": "application/json",
    "etag": "BzKVFWmX7s2aoJz02iOKn4I0y8eVMFft",
    "origin": "https://mms.pinduoduo.com",
    "priority": "u=1, i",
    "referer": "https://mms.pinduoduo.com/goods/goods_list?msfrom=mms_sidenav",
    "sec-ch-ua": "\"Chromium\";v=\"154\", \"Google Chrome\";v=\"154\", \"Not A(Brand\";v=\"99\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36"
}
cookies = {
    "api_uid": "CimLQWqrzlAgLQCVLu3/Ag==",
    "rckk": "nquPMOKNVPcgjlXvbqZicNWymXBQztyN",
    "_bee": "nquPMOKNVPcgjlXvbqZicNWymXBQztyN",
    "ru1k": "b4e443a9-f4fe-464c-bd98-fd9ecd98d454",
    "_f77": "b4e443a9-f4fe-464c-bd98-fd9ecd98d454",
    "ru2k": "3b00c3fd-b0b2-4332-8c82-3247c5498f47",
    "_a42": "3b00c3fd-b0b2-4332-8c82-3247c5498f47",
    "webp": "true",
    "_nano_fp": "XpmJlpEYn0Xjl0Xbl9_auFPWUUHWG4~En92whd7J",
    "mms_b84d1838": "3700,3706,3523,3709,3678,3531,3687,3482,1202,1203,1204,1205,3417",
    "PASS_ID": "1-rx5+oSluhikkrR4Bu8OA4Fiq6e+PI5en5y3gP3VKz72ZHJzlayg9K90ebUE9yGzZzVRQBOzb26GKAmVRQXyWFA_735291215_156012866",
    "windows_app_shop_token_23": "eyJ0IjoicEJjS29JRGdMZUI2VDN6WjVWOU4xaG4vZ2VGQjZucnhMNlRwSmtLU0hMMXZJd3JYdWRMa1huY2NKdVNHY0VsYiIsInYiOjEsInMiOjIzLCJtIjo3MzUyOTEyMTUsInUiOjE1NjAxMjg2Nn0",
    "JSESSIONID": "2285302049105930F37F210D756F4B32",
    "x-visit-time": "1790895306359"
}
url = 'https://mms.pinduoduo.com/vodka/v2/mms/query/display/mall/goodsList'
data = '{"pre_sale_type":4,"page":1,"order_by":"sold_quantity_30d:desc,id:desc","out_goods_sn_gray_flag":true,"shipment_time_type":3,"is_onsale":1,"sold_out":0,"size":100}'.encode('utf-8', 'surrogateescape')
response = requests.post(url, headers=headers, cookies=cookies, data=data)

print(response.json())
print(response)






