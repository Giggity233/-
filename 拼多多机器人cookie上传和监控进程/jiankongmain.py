from autodl import jianyandl
import time
import threading
import ctypes
import sys
from pathlib import Path
from ht_api import (
    huoqu_dianpu,
    huoqu_zhuanyuan,
    jing_shi_tixing,
    shangchuan_jiqiren_cookie,
)
from pdd_api import pddresolve_csid, pddgetshopname
from DrissionPage import ChromiumOptions, Chromium
import json
from loggerset import merchant_log  # 导入单例
from jiankong import dangqianmain

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

with open(APP_DIR / 'data' / 'jiankong.json', 'r', encoding='utf-8') as f:
    jiankong_data = json.load(f)

SLEEP_TIME=int(jiankong_data['sleep_time'])
TRANSFER_TIMEOUT = int(jiankong_data['transfer_timeout'])
CHANGSHU=int(jiankong_data['changshu'])
COOKIE_UPLOAD_INTERVAL = 60 * 60
COOKIE_UPLOAD_RETRY_INTERVAL = 5 * 60

# 设置控制台标题
def set_console_title(title):
    ctypes.windll.kernel32.SetConsoleTitleW(title)


#获取页面对应信息
def getzhegroupbowtests(groupnum):
    path = rf'D:\aibot\user_login_info.json'
    with open(path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
    return json_data[groupnum]


#获取自动化能够操作的page页面
def getzhepages(groupnum,port):
    path = rf'D:\aibot\group{groupnum}\{port}\user-data\EBWebView'
    co1 = ChromiumOptions().set_local_port(int(port)).set_user_data_path(path)
    browser = Chromium(co1)
    page = browser.latest_tab
    return page


def getzhecsid(cookies,accname):
    """Resolve the configured human's ``mmsId`` to PDD's transfer ``csid``."""
    try:
        pass_id_parts = cookies['PASS_ID'].split('_')
        shop_id = pass_id_parts[-2]
        cookie_account_id = str(pass_id_parts[-1]).strip()
        response = huoqu_zhuanyuan(shop_id)
        human_accounts = response.get('Data') or []
        if not human_accounts:
            message = f"店铺{shop_id}转人工失败：中控未配置人工客服账号"
            jing_shi_tixing(shop_id, message)
            merchant_log.error(message, accname, "异常监控日志")
            return None

        # The central-platform interface defines the first configured human
        # account as this shop's transfer target.
        human_account = human_accounts[0]
        human_id = str(human_account.get('mmsId') or '').strip()
        if not human_id:
            message = f"店铺{shop_id}转人工失败：人工账号未同步 mmsId"
            jing_shi_tixing(shop_id, message)
            merchant_log.error(message, accname, "异常监控日志")
            return None

        csid = pddresolve_csid(cookies, human_id)
        if not csid:
            account_name = human_account.get('AccountName') or human_id
            message = f"店铺{shop_id}转人工失败：可转接列表未找到人工账号 {account_name}（mmsId={human_id}）"
            jing_shi_tixing(shop_id, message)
            merchant_log.error(message, accname, "异常监控日志")
            return None

        # ``move_conversation`` cannot transfer a conversation to the same
        # PDD sub-account that owns the current Cookie.  This configuration
        # must be fixed (a distinct robot Cookie or another human account)
        # rather than repeatedly sending a self-transfer request.
        if human_id == cookie_account_id:
            account_name = human_account.get('AccountName') or human_id
            warning_key = f"{shop_id}_{human_id}"
            message = (
                f"店铺{shop_id}转人工已拦截：人工账号 {account_name} 与当前监控 Cookie "
                "是同一拼多多子账号，不能转给自己；请使用独立的机器人账号 Cookie，"
                "或在中控配置另一个人工账号。"
            )
            if warning_key not in registered_self_transfer_shops:
                jing_shi_tixing(shop_id, message)
                registered_self_transfer_shops.add(warning_key)
            merchant_log.error(message, accname, "异常监控日志")
            return None

        return csid
    except Exception as e:
        merchant_log.error(f"获取转人工 csid 异常: {e}", accname, "异常监控日志")
        return None


def register_offline_shop(accname):
    """店铺登录失败：在中控平台建一条紧急待办（代替原来的发微信群通知）"""
    shop = huoqu_dianpu(accname)
    if not shop:
        merchant_log.error(f"掉线店铺在中控平台找不到: {accname}", "总", "异常监控日志")
        return

    shop_key = f"{shop.get('shop_id')}_{shop.get('shop_name')}"
    if shop_key in registered_offline_shops:  # 只登记一次，避免重复登记
        return

    try:
        jing_shi_tixing(shop.get("shop_id"),
                        f"{accname} 店铺{shop.get('shop_name')}登录失败，请查看😭😭😭")
        merchant_log.info(f"掉线店铺警示提醒已发送: {shop.get('shop_name')}", "总", "异常监控日志")
    except Exception as e:
        merchant_log.error(f"掉线店铺登记异常: {e}", "总", "异常监控日志")
    registered_offline_shops.add(shop_key)


# 记录已登记的掉线店铺，避免重复登记
registered_offline_shops = set()
# Avoid creating the same configuration-warning task on every retry.
registered_self_transfer_shops = set()


groupnumjidi = 'group'
inputnum = input("请输入监控的分组:")
# 设置控制台标题
set_console_title(f"分组{inputnum}监控")
groupnum = groupnumjidi + str(inputnum)
shoptests = getzhegroupbowtests(groupnum)

# 记录程序启动日志
merchant_log.info(f"程序启动成功，监控分组: {inputnum}", "总", "监控运行日志")


# 监控函数
def monitor_shop(shoptest, groupnum):
    # Each monitor owns one robot browser account.  Upload immediately after
    # startup, then refresh the central copy every hour.  Failed uploads retry
    # after five minutes without delaying message monitoring.
    next_cookie_upload_at = 0.0
    while True:
        try:
            page = getzhepages(groupnum, shoptest['port'])
            page.get('https://mms.pinduoduo.com/chat-merchant/#/')
            cookies=page.cookies().as_dict()
            shopname = pddgetshopname(cookies)
            if shopname=='会话已过期':
                merchant_log.warn(f"检测到掉线", shopname, "异常监控日志")
                a = jianyandl(page, shoptest)
                if a==False:
                    register_offline_shop(shoptest['username'])
                    time.sleep(SLEEP_TIME)
                    continue
                else:

                    cookies = page.cookies().as_dict()
                    shopname = pddgetshopname(cookies)
            if time.monotonic() >= next_cookie_upload_at:
                try:
                    shangchuan_jiqiren_cookie(cookies, shopname)
                    next_cookie_upload_at = time.monotonic() + COOKIE_UPLOAD_INTERVAL
                    merchant_log.info("机器人 Cookie 上传成功", shopname, "监控运行日志")
                except Exception as e:
                    next_cookie_upload_at = time.monotonic() + COOKIE_UPLOAD_RETRY_INTERVAL
                    merchant_log.error(f"机器人 Cookie 上传失败: {e}", shopname, "异常监控日志")
            csid = getzhecsid(cookies, shoptest['username'])
            if not csid:
                merchant_log.error("未获取到转人工 csid，稍后重试", shopname, "异常监控日志")
                time.sleep(SLEEP_TIME)
                continue
            n=0
            while True:
                n+=1
                try:
                    cookies = page.cookies().as_dict()
                    shopname1 = pddgetshopname(cookies)
                    if shopname1=='会话已过期':
                        merchant_log.warn(f"检测到掉线", shopname, "异常监控日志")
                        a=jianyandl(page,shoptest)
                        if a == False:
                            register_offline_shop(shoptest['username'])
                            time.sleep(SLEEP_TIME)
                            continue
                        else:
                            cookies = page.cookies().as_dict()
                            shopname = pddgetshopname(cookies)
                    if time.monotonic() >= next_cookie_upload_at:
                        try:
                            shangchuan_jiqiren_cookie(cookies, shopname)
                            next_cookie_upload_at = time.monotonic() + COOKIE_UPLOAD_INTERVAL
                            merchant_log.info("机器人 Cookie 上传成功", shopname, "监控运行日志")
                        except Exception as e:
                            next_cookie_upload_at = time.monotonic() + COOKIE_UPLOAD_RETRY_INTERVAL
                            merchant_log.error(f"机器人 Cookie 上传失败: {e}", shopname, "异常监控日志")
                    dangqianmain(cookies, csid,shopname)
                    time.sleep(CHANGSHU)
                except Exception as e:
                    merchant_log.error(f"监控异常: {e}", shopname, "异常监控日志")
                    time.sleep(10)
                    continue
        except Exception as e:
            merchant_log.error(f"监控异常: {e}", "总", "异常监控日志")
            time.sleep(10)
            continue


# 启动多线程监控
threads = []
for i, shoptest in enumerate(shoptests):
    # 每个线程间隔4秒启动
    if i > 0:
        time.sleep(3)
    t = threading.Thread(target=monitor_shop, args=(shoptest, groupnum))
    t.daemon = True  # 设置为守护线程
    t.start()
    threads.append(t)

# 主线程保持运行
for t in threads:
    t.join()



