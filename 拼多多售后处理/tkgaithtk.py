import requests
import time
import execjs
with open("anti.js", "r", encoding="utf-8") as file:
    anticode = file.read()


def thefirstsubmit(cookies,orderSn,afterSalesId):
    headers = {
        "accept": "application/json",
        "accept-language": "zh-CN,zh;q=0.9",
        "anti-content": execjs.compile(anticode).call("get_anti", int(time.time())),
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://mms.pinduoduo.com",
        "priority": "u=1, i",
        "referer": "https://mms.pinduoduo.com/aftersales-ssr/detail?id=23623918757415&orderSn=261018-359042915940947",
        "sec-ch-ua": "\"Not:A-Brand\";v=\"8\", \"Chromium\";v=\"156\", \"Google Chrome\";v=\"156\"",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "\"Windows\"",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"
    }
    url = 'https://mms.pinduoduo.com/mercury/mms/afterSales/rejectRefundSubmitFormData'
    data = {
        "formName": "新售后驳回标准化流程_收纳和家用建材_step1",
        "formDataList": [
            {
                "keyLabel": "",
                "value": "option1",
                "key": "RadioGroup1",
                "valueLabel": "与消费者协商售后方案"
            },
            {
                "value": "[{\"keyLabel\":\"协商方案\",\"value\":\"[{\\\"value\\\":\\\"return_refund\\\",\\\"valueLabel\\\":\\\"退货后退全款\\\"}]\",\"key\":\"CheckboxGroupNegotiatedSolution\"},{\"keyLabel\":\"退款金额\",\"key\":\"RefundAmount\"},{\"keyLabel\":\"协商话术\",\"value\":\"'亲，很抱歉给您带来了不好的购物体验～' 我们想与您协商“退货退款”，您看可以吗～\",\"key\":\"RefundWords\"},{\"keyLabel\":\"上传凭证\",\"value\":\"[]\",\"key\":\"MmsUpload\"}]",
                "key": "ProMultiSolution1"
            },
            {
                "key": "FormId",
                "value": "form1",
                "keyLabel": "",
                "valueLabel": ""
            }
        ],
        "orderSn": orderSn,
        "afterSalesId": int(afterSalesId),
        "bizType": 10,
        "bizId": str(afterSalesId)
    }
    response = requests.post(url, headers=headers, cookies=cookies, json=data)
    print(response.json())


cookies ={
    "_bee": "6eM0GCkkBPgSNah7PkYXaGpJRCvCVEH0",
    "_nano_fp": "XpmbX5Ubn5EaXpdYlT_tlhBmgaSIiB4t1s9gqHgq",
    "api_uid": "Cike6Gre9QOOZwCXROztAg==",
    "rckk": "6eM0GCkkBPgSNah7PkYXaGpJRCvCVEH0",
    "_f77": "1f30c9a6-13b6-4915-90df-6603efd12223",
    "ru2k": "b02bf11a-e69a-4c6e-be78-f626fe49623e",
    "ru1k": "1f30c9a6-13b6-4915-90df-6603efd12223",
    "JSESSIONID": "27FF8DCC608F74E504BFEF23BC24906A",
    "x-visit-time": "1793303866966",
    "mms_b84d1838": "3616,3706,3523,3660,3709,3614,3678,3599,3605,3677,3531,3559,3687,3754,3482,1202,1203,1204,1205,3417",
    "PASS_ID": "1-rDWKTZWpo31J5tUJDRzlmoW+H2zTs23qmgsG+R4m3ysQ6bbzAIOWpK705N18mBSACL7ZqUPcwxAWxyaOmGG9Ew_688901674_190123133",
    "_a42": "b02bf11a-e69a-4c6e-be78-f626fe49623e"
}
thefirstsubmit(cookies,"260722-670653509210185","23529934216417")
