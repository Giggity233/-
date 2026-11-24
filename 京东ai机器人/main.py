"""PyCharm entry point for the JD robot batch-control window."""

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path

from jd_cookie_runner import JdCookieRunner
from jd_control_panel import run_control_panel
from jd_robot_cookie_api import DEFAULT_API_BASE_URL, DEFAULT_PLATFORM, parse_cookie_string


# 如中控平台地址变更，只需修改这里；接口文档允许京东平台值为 jingdong。
API_BASE_URL = DEFAULT_API_BASE_URL
PLATFORM = DEFAULT_PLATFORM
WORKFLOW_FILE = Path(__file__).resolve().parent / "data" / "workflowid.json"


def choose_workflow(path: Path = WORKFLOW_FILE) -> tuple[str, str]:
    """在打开店铺控制页前选择 data/workflowid.json 中的工作流。"""
    try:
        workflows = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("无法读取工作流配置 {}：{}".format(path, error)) from error
    if not isinstance(workflows, dict) or not workflows:
        raise RuntimeError("workflowid.json 必须是非空对象，格式为“名称: 工作流编号”")
    options = [(str(name), str(workflow_id).strip()) for name, workflow_id in workflows.items()]
    if any(not workflow_id for _, workflow_id in options):
        raise RuntimeError("workflowid.json 中存在空工作流编号")

    print("\n可选 Coze 工作流：")
    for index, (name, _) in enumerate(options, start=1):
        print("  {}. {}".format(index, name))
    while True:
        choice = input("请输入工作流序号：").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("请输入 1 到 {} 之间的数字。".format(len(options)))


def run_test_cookie(cookie: str | Mapping[str, object]) -> None:
    """传入一份完整 Cookie，直接测试单店机器人连接。按 Ctrl+C 停止。"""
    if isinstance(cookie, str):
        cookies = parse_cookie_string(cookie)
    elif isinstance(cookie, Mapping):
        cookies = dict(cookie)
    else:
        raise TypeError("cookie 必须是完整 Cookie 字符串或字典")
    asyncio.run(JdCookieRunner(cookies).run_forever())


def main() -> None:
    workflow_name, workflow_id = choose_workflow()
    run_control_panel(
        api_base_url=API_BASE_URL,
        platform=PLATFORM,
        workflow_name=workflow_name,
        workflow_id=workflow_id,
    )


if __name__ == "__main__":
    main()
# cookie="__jdv=56585130|direct|-|none|-|1793607898696; __jdu=17936078986951065272660; shshshfpa=71760e58-a55a-1cc6-c5a3-aa9bc6af3afa-1793607899; shshshfpx=71760e58-a55a-1cc6-c5a3-aa9bc6af3afa-1793607899; areaId=15; ipLoc-djd=15-1213-0-0; __USE_NEW_PAGEFRAME__=true; __USE_NEW_PAGEFRAME_VERSION__=v11; language=zh_CN; dsm-lang=zh_CN; _pst=%E5%90%B4%E5%90%B4_%E5%AE%A2%E6%9C%8D; TrackID=1uEvbzwEhGjSKPAnxJaCgJvQlYaXiw0LS9lb1wgvwV8U4VWQKHLnihuLQCWR9a-Tv; light_key=AASBKE7rOxgWQziEhC_QY6yazDlYvnSQfz28DrMJLA3I-RmDnARO4wGSwgmZ18X6BcAsOnS-; _tp=mK9VtAiT%2FahI%2FMQH3cB%2FUAdM8vXAGFgmXweK3VhAU%2BTknv2Kvfz7%2Ftm34eVxOCFZ; pin=%E5%90%B4%E5%90%B4_%E5%AE%A2%E6%9C%8D; ceshi3.com=000; pinId=Nyor6ZopFgbCDkScltXL_g; unick=%E9%A2%9C%E5%80%BC%E5%AE%88%E4%BF%9D%E5%8D%AB-%E5%BA%86%E7%A5%9Dx5644; b-sec=YEEZAHX6OJVL6IBD7VSIJ5UQDLWCIVTTMLGBFOEDEHHXVPD3QFIY7TMNQN7X7NMZ; _s_vender_=BXVUPWFMPBOMT26TQWUF52C7T47OF5CJIPKYKBEALFOT2JDKYKGSF6RZQWGUJWKU3WV4UJVGPA3XE5ISNY7GZRKYQJ7QRZNP6BS3GJW3C7MBYQG247HLVK3KD5BRMENY26SS4AYZWASJFYX5BDFBKJ3QJPMR7YSVDLCNKMZJGQWIEQMIKAMH6TESLP2L4JOSB24VS2PVD4QHTAU4QXINBEG2MPCVVQJLS2G7VEDUGVBZYUO5HYZMDOFNBRDY2SAOCSVB4BHVGAIYK5LKZ7Q3XKDK44TAGVXMH542MZQLCUHR6K2PSUIAUVEWSBXOC2S7XVJ3D7ZGGYAMBBJBGUGLOHCLUQDEA2AA3BU6DFALGQFHCFFD55VA; _base_=YKH2KDFHMOZBLCUV7NSRBWQUJPBI7JIMU5R3EFJ5UDHJ5LCU7R2NILKK5UJ6GLA2RGYT464UKXAI5KK7PNC5B5UHJ2HVQ4ENFP57OC52A37DA6TER5IQVXP2KCUEKL4ATCNE6YVKRXISUN2OOIC3RYWGIKS2GMV77CV7EE2SG4SOQWCP5WPWO6EFS7HEHMRWVKBRVHB33TFD4P7THZXHMA7QPECXYZPOKQDPI6Y4T4HER3AS4UCGSJHFWXHCYYMA4GBTVIDTJQWVMODFYFTWGV5UAWCX5C6J372TDCL6LDNEERERTGCW76JQBJFSNLCWTQFUPBOIQ4J3RVQAQIWW3S2YBEGT65LDWDMXQI2MWFIEB7FVUPRQ; userIdentity=%E5%90%B4%E5%90%B4_%E5%AE%A2%E6%9C%8D|POP; mba_muid=17936078986951065272660; cid=9; 3AB9D23F7A4B3CSS=jdd03ZV6KCRR5MXTXBTBMMS52N6ANV6W6LUJA4XJOMKBDDH23J2HLNUVVTDP25TJK3TIHS3SXHWO2XIAVWZFSZW4XOKZTQEAAAANBZCAN3PIAAAAACPQKEHQ4AOVS44X; 3AB9D23F7A4B3C9B=ZV6KCRR5MXTXBTBMMS52N6ANV6W6LUJA4XJOMKBDDH23J2HLNUVVTDP25TJK3TIHS3SXHWO2XIAVWZFSZW4XOKZTQE; __jd_ref_cls=MDownLoadFloat_SdkLoaded; thor=22E1EEC0EDC77ED3628387C83AED1A42C98B7E0BD84B2C77E4A880530876463B9060D89B3DCA5E48135AB9FDC391B31A0B931535DC6DBD91E60778EA484B32A9672AD505202B765CEA0BD4D74314CDF22A50162206A06EEF2DB281FE6FE0105ED47F82F4287BAF941063B2F9FEB295C585E8C92B6DDDAF3120BAC385FFA39C82; shshshfpb=BApXW8XeIy8RAgKBIVx3ycndqw-x9aYsgBtEhf7Zp9xJ1P1mrqQMmRiVuQul8z2vJWz1S1sLph8FlIr0yuq0G5dJ9M1udNUQt; hf_time=1794383250837; __jda=144432416.17936078986951065272660.1793607899.1793607899.1794361874.2; __jdc=144432416; flash=3_85Jj7t0tRAD8aK8ScRJv_TQ75mxnQk7wxwIBomWDbfbUMz2hHFjopqUh8J-ZhkWgJG85lwnw1ekE3QT6mSQFnN3_0n81ERMblHCKCjMswecOhCEidNkJigX4Qta8XTA1j6SeC3dKTrRKUZxCee**; _s_base_=BXVUPWFMPBOMT26TQWUF52C7T57ZSX7SJM24R4OW5YZG7BQSQJI2CJMJ3L4UN345IZWC7QOPBSCBSSTXVQZTFEDKMBBZRYXGTML26V62WLGI2AP5NNVT6HECQN23KHDZ7UPKL5BCEDKCY6OVA5BAFMNN6F2NHJHAR2VCYLCPGNMGDK2AN3BQ; sdtoken=AAbEsBpEIOVjqTAKCQtvQu17H6BSfCAEvKONEmVhyfJ2reIoTUpfd2DlJJc_n90WX2KDcNttWzO2UDAYsE9d42WCM0X6s3BmFbLjpylD8AkqgkaPDlkRPQSCuTIZlrsMj8k3zXEVGL5U"
# run_test_cookie(cookie)
