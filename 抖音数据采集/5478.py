import requests


headers = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "priority": "u=1, i",
    "referer": "https://fxg.jinritemai.com/ffa/eco/experience-score?%24_source=doudian-ai&btm_ppre=a2427.b76571.c902327.d871297&btm_pre=a2427.b687601.c67024&btm_show_id=da7426d0-fe59-407b-aef5-fb14de863e5f",
    "sec-ch-ua": "\"Google Chrome\";v=\"153\", \"Not_A Brand\";v=\"8\", \"Chromium\";v=\"153\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36"
}
cookies = {
    "zsgw_business_data": "%7B%22uuid%22%3A%222ca3c23b-572f-4dcf-82dd-9f1a938020ff%22%2C%22platform%22%3A%22pc%22%2C%22source%22%3A%22seo.fxg.jinritemai.com%22%7D",
    "Hm_lvt_b6520b076191ab4b36812da4c90f7a5e": "1789582622",
    "s_v_web_id": "verify_mu4fad4c_puVnujVK_zdrZ_49uD_A5jm_x8RjbLaIZRV8",
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
    "COMPASS_LUOPAN_DT": "session_7686196306578456886",
    "SHOP_ID": "266072853",
    "PIGEON_CID": "7613323028357684762",
    "ecom_gray_shop_id": "266072853",
    "csrf_session_id": "8602faeb96b1c86b7d7bfb5a17d0c09d",
    "sid_guard": "10f194d5781cd4b813033553d099bebe%7C1789917077%7C5184000%7CThu%2C+19-Nov-2026+15%3A11%3A17+GMT",
    "session_tlb_tag": "sttt%7C2%7CEPGU1Xgc1LgTAzVT0Jm-vv_________2ANbobe5IKMEl2X6Z9QyPj95mwivBsp_s1ATKiBsY3AU%3D",
    "sid_ucp_v1": "1.0.0-KDRkZDUwNmRlOGJmZTdmNDkwYmI0NWVlZmZlNGYxYjMzMGJmOGNmODkKGQjA79Cwls3QAxCV77_VBhiwISAMOAJA8QcaAmxxIiAxMGYxOTRkNTc4MWNkNGI4MTMwMzM1NTNkMDk5YmViZQ",
    "ssid_ucp_v1": "1.0.0-KDRkZDUwNmRlOGJmZTdmNDkwYmI0NWVlZmZlNGYxYjMzMGJmOGNmODkKGQjA79Cwls3QAxCV77_VBhiwISAMOAJA8QcaAmxxIiAxMGYxOTRkNTc4MWNkNGI4MTMwMzM1NTNkMDk5YmViZQ",
    "BUYIN_SASID": "SID2_7687634381423952167",
    "ecom_us_lt_buyin_top": "36eee4574b77f46d06633fd7032f62b0400441a482975b8f12a5732919305ecf",
    "ecom_us_lt_ss_buyin_top": "36eee4574b77f46d06633fd7032f62b0400441a482975b8f12a5732919305ecf",
    "uidpasaddaehruigqreajf": "0",
    "gfkadpd": "4272,23756"
}
url = 'https://fxg.jinritemai.com/governance/shop/experiencescore/getTrendByVersion'
params = {
    "trend_type": "1",
    "time": "30",
    "exp_version": "v10"
}
response = requests.get(url, headers=headers, cookies=cookies, params=params)

print(response.text)
print(response)