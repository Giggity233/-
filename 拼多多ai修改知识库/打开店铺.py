from DrissionPage import ChromiumPage
page=ChromiumPage(1155)
page.get('https://mms.pinduoduo.com/home')
cookies = {
    "api_uid": "Ckhkgmqrm8mbLgB5YOPMAg==",
    "_nano_fp": "XpmJlpEqXpTqX5XYno_EuY72js6rA_CInAfR7IJb",
    "rckk": "NL8Xx0BAcRKPgsQ3sOkHEyyeCOVF90oN",
    "_bee": "NL8Xx0BAcRKPgsQ3sOkHEyyeCOVF90oN",
    "ru1k": "ee32f875-b5ef-4f19-8eb3-14dff1ca6b88",
    "_f77": "ee32f875-b5ef-4f19-8eb3-14dff1ca6b88",
    "ru2k": "7260f8fe-485a-4124-b7f6-eb920dfa732e",
    "_a42": "7260f8fe-485a-4124-b7f6-eb920dfa732e",
    "mms_b84d1838": "3616,108,150,180,3693,3700,3706,3523,3660,3709,3614,3599,3658,3605,3622,3669,3677,3588,3254,3532,3642,3474,3475,3477,3479,810,820,3687,3482,1202,1203,1204,1205,3417",
    "PASS_ID": "1-RRhNMTYkpm/0xs9eoFU7QwT0dx3xGEaaw61hxwGgSMWxIIBp8OpZpmfzmWeNXeDwRqLyYi3FnAIFZBt2K3nH/Q_926405575_193280810",
    "x-visit-time": "1791564227702",
    "JSESSIONID": "1BEA1BA8FF677942C797603042323B4A"
}
page.set.cookies(cookies)
page.get('https://mms.pinduoduo.com/home')

