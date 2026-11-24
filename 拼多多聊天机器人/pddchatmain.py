from loggerset import merchant_log  # 直接从 loggerset 导入单例
from DrissionPage import ChromiumOptions, Chromium
import json
from Listen_Ws import AsyncListenWs
import asyncio
import pdd_ws
import chatluoji
from pdd_api import pddchange_state, pddgetshopname
import threading
import time
import ctypes
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError


APP_DIR = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent


# 设置控制台标题
def set_console_title(title):
    ctypes.windll.kernel32.SetConsoleTitleW(title)


# 获取页面对应信息
def getzhegroupbowtests(groupnum):
    path = rf'D:\aibot\user_login_info.json'
    with open(path, 'r', encoding='utf-8') as file:
        json_data = json.load(file)
    return json_data[groupnum]


# 获取自动化能够操作的page页面
def getzhepages(groupnum, port):
    path = rf'D:\aibot\group{groupnum}\{port}\user-data\EBWebView'
    co1 = ChromiumOptions().set_local_port(int(port)).set_user_data_path(path)
    browser = Chromium(co1)
    page = browser.latest_tab
    return page


# 获取监听对象
def getzhelisten(page):
    listen_ws = AsyncListenWs(page)
    return listen_ws


# 全局变量用于存储消息缓冲区
message_buffers = {}  # key: user_id, value: (messages_list, last_time, timer)
message_lock = threading.Lock()

# 处理消息的包装函数，用于在线程中执行
def _execute_chamainzhu(messages_list, cookiesstr, workflow_id, shopname):
    try:
        result = chatluoji.chamainzhu(messages_list, cookiesstr, workflow_id, shopname)
        return result
    except Exception as e:
        merchant_log.error(f"处理消息时出错: {e}", shopname, "运行日志")
        return False

# 处理消息缓冲区的函数
def _process_buffer(user_id, cookiesstr, workflow_id, shopname):
    global message_buffers, message_lock
    messages_list = None

    # 只在获取消息缓冲区时持有锁
    with message_lock:
        if user_id in message_buffers:
            messages_list, _, _ = message_buffers[user_id]
            del message_buffers[user_id]

    # 释放锁后再处理消息
    if messages_list:
        # 使用线程池执行，设置120秒超时
        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                # 执行chamainzhu函数，设置120秒超时
                future = executor.submit(_execute_chamainzhu, messages_list, cookiesstr, workflow_id, shopname)
                future.result(timeout=120)
            except TimeoutError:
                merchant_log.error(f"处理用户{user_id}的消息超时（超过120秒），任务自动结束", shopname, "运行日志")
            except Exception as e:
                merchant_log.error(f"处理消息时出错: {e}", shopname, "运行日志")

# 处理单个消息的函数
def process_message(msg, cookiesstr, workflow_id, shopname):
    global message_buffers, message_lock
    try:
        new_message = pdd_ws.run(msg)
        if new_message != None and isinstance(new_message, str) and new_message[0] != '[' and 'push_type' in new_message:
            # 解析用户ID
            msg_data = json.loads(new_message)
            if 'push_data' in msg_data and 'data' in msg_data['push_data'] and msg_data['push_data']['data']:
                user_id = msg_data['push_data']['data'][-1]['message']['from']['uid']
                
                with message_lock:
                    if user_id in message_buffers:  # 检查是否已有该用户的消息缓冲区
                        messages_list, _, timer = message_buffers[user_id]  # 清除之前的定时器
                        if timer:
                            timer.cancel()
                        messages_list.append(new_message)  # 添加新消息到列表并设置4秒定时器
                        message_buffers[user_id] = (messages_list, time.time(), 
                            threading.Timer(4, _process_buffer, 
                                args=(user_id, cookiesstr, workflow_id, shopname)))
                        message_buffers[user_id][2].start()
                    else:
                        message_buffers[user_id] = ([new_message], time.time(),
                            threading.Timer(6, _process_buffer, 
                                args=(user_id, cookiesstr, workflow_id, shopname)))  # 新用户，创建消息列表并设置6秒定时器
                        message_buffers[user_id][2].start()
    except Exception as e:
        pass
        # 出错时不做处理，继续监听


# 异步主函数（核心使用逻辑）
async def chatmain(page, shoptest, workflow_id):
    listen_ws = AsyncListenWs(page)
    cookies = page.cookies().as_dict()
    shopname = pddgetshopname(cookies)
    pddchange_state(cookies, 1)
    merchant_log.success(f"已强制在线", shopname, "运行日志")
    # 启动预检：转接人（转人工动作在 Coze 插件里做，这里先查清有没有人能转，查不到就写日志+发警示提醒）
    shopid = cookies.get('PASS_ID', '').split('_')[-2]
    username = chatluoji.check_transfer_person(cookies, shopid, shopname)
    merchant_log.success(f"店铺{shopname}转接人{username}", shopname, "运行日志")
    await listen_ws.start()
    # 循环获取监听信息
    async for msg in listen_ws.receive_messages():
        cookiesstr = page.cookies().as_str()
        # 为每个对话创建一个线程
        t = threading.Thread(target=process_message, args=(msg, cookiesstr, workflow_id, shopname))
        t.start()


def run_chatmain(page, shoptest, workflow_id):
    asyncio.run(chatmain(page, shoptest, workflow_id))


# ------------------- 改造后的监控主逻辑 -------------------
# 输入分组号
groupnumjidi = 'group'
inputnum = input("请输入监控的分组:")
# 设置控制台标题
set_console_title(f"分组{inputnum}")
groupnum = groupnumjidi + str(inputnum)
shoptests = getzhegroupbowtests(groupnum)

# 选择用户
# 从coze.json读取所有配置
with open(APP_DIR / 'data' / 'coze.json', 'r', encoding='utf-8') as f:
    cozedata = json.load(f)

# 生成选项列表
options = []
for key, value in cozedata.items():
    options.append(f"({key}) {value['client']}")

# 打印选择选项
print("请选择用户: " + "，".join(options))
choice = input("请输入选项(数字):")

user = cozedata[choice]['client']
workflow_id = cozedata[choice]['workflow_id']

# 监控函数
def monitor_shop(shoptest, groupnum, workflow_id):
    while True:
        try:
            # 初始化页面
            page = getzhepages(groupnum, shoptest['port'])
            page.get('https://mms.pinduoduo.com/chat-merchant/#/')
            merchant_log.info(f"店铺页面初始化完成", shoptest['username'], "运行日志")
            
            # 启动后隔1秒刷新一次页面
            time.sleep(1)
            page.refresh()
            merchant_log.info(f"店铺页面已刷新", shoptest['username'], "运行日志")

            # 启动核心聊天监听（阻塞运行，异常后自动重启）
            run_chatmain(page, shoptest, workflow_id)

        except Exception as e:
            merchant_log.error(f"店铺运行异常: {e}", shoptest['username'], "异常监控日志")
            time.sleep(300)  # 异常后等待10秒重启
            continue


threads = []
for i, shoptest in enumerate(shoptests):
    if i > 0:
        time.sleep(2)
    t = threading.Thread(target=monitor_shop, args=(shoptest, groupnum, workflow_id))
    t.daemon = True
    t.start()
    threads.append(t)
    merchant_log.info(f"分组{inputnum} - 店铺{shoptest['shop_name']}线程启动", "总", "运行日志")

for t in threads:
    t.join()
