import json
import sys
from pdd_api import pddanti
import zk_api
import time
from coze_api import cozehuoquid,cozeduihua
from pathlib import Path
from loggerset import merchant_log  # 直接从 loggerset 导入单例
import re

_config_path = Path(sys.executable).parent / "data" / "xitong.json" if getattr(sys, 'frozen', False) else Path(__file__).parent / "data" / "xitong.json"

with open(_config_path, 'r', encoding='utf-8') as f:
    xitongjson = json.load(f)
buzhuan = xitongjson['buzhuan']
zhuan = xitongjson['zhuan']
xithf = xitongjson['xithf']
_config_refresh_interval = xitongjson.get('config_refresh_interval', 3600)
_last_config_refresh = time.time()


def _check_config_refresh():
    global _last_config_refresh, buzhuan, zhuan, xithf, _config_refresh_interval
    now = time.time()
    if now - _last_config_refresh > _config_refresh_interval:
        with open(_config_path, 'r', encoding='utf-8') as f:
            xitongjson = json.load(f)
        buzhuan = xitongjson['buzhuan']
        zhuan = xitongjson['zhuan']
        xithf = xitongjson['xithf']
        _config_refresh_interval = xitongjson.get('config_refresh_interval', 3600)
        _last_config_refresh = time.time()


#整理监听到的信息
def new_messagezl(new_message):
    try:
        if 'push_data' in new_message and new_message['push_type']==2:
            uid = new_message['push_data']['data'][-1]['message']['from']['uid']
            msg_id=new_message['push_data']['data'][-1]['message']['msg_id']
            content=new_message['push_data']['data'][-1]['message']['content']
            try:
                username=new_message['push_data']['data'][-1]['message']['nickname']
            except:
                username='无'
            for i in xithf:
                if i in content:
                    content="zdyi"
                    break
            message = new_message['push_data']['data'][-1]['message']
            template_name = message.get('template_name', '')
            # print(template_name)
            if template_name:
                if template_name in buzhuan:
                    content = template_name  # 需要回复的官方信息
                elif template_name in zhuan:
                    content = "转人工"  # 需要回复的官方信息
                else:
                    pass
            zl={
                'shopid':new_message['push_data']['data'][-1]['message']['to']['uid'],
                'userid':uid,
                'username':username,
                'content':content,
                'msgid':msg_id,
                'template_name':template_name
            }
            return zl
        else:
            return None
    except:
        return None

# ===================== 【全局工具：链接清洗函数】只留图片，过滤视频 + 其他所有链接 =====================
def clean_media_text(text):
    if not text or str(text).strip() == "":
        return "无"

    text = str(text).strip()
    url_pattern = re.compile(r'https?://\S+')

    IMG_EXTS = (
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.svg',
        '.mp4', '.avi', '.mov', '.wmv', '.flv', '.mkv', '.webm', '.m4v',
        '.mpg', '.mpeg', '.3gp', '.ts', '.m3u8', '.rmvb', '.vob'
    )

    def replace_func(match):
        url = match.group(0)
        url_low = url.lower()

        # 只保留：以图片后缀结尾的链接
        if url_low.endswith(IMG_EXTS):
            return url
        # 其他所有链接（视频 + 普通网页等）全部删除
        return ''

    # 执行替换：只留图片链接
    cleaned = url_pattern.sub(replace_func, text)
    cleaned = cleaned.strip()

    # 清理后为空则返回无
    return cleaned if cleaned else "无"


def testzl(new_message, cook, ges):
    if ges==0:
        chattest = new_messagezl(new_message)
        if chattest is None:
            return None

        # 注入cook（上传coze的参数）
        chattest['cook'] = cook

        if 'content' in chattest:
            chattest['content'] = clean_media_text(chattest['content'])

        # 内容为空时替换为商品卡片标记
        if str(chattest.get('content', '')) == "无":
            chattest['content'] = "user_goods_card"

        return chattest
    else:
        content = new_message['push_data']['data'][-1]['message']['content']
        if '订单编号' in content:
            return "user_goods_card"
        for i in xithf:
            if i in content:
                return "zdyi"
        message = new_message['push_data']['data'][-1]['message']
        template_name = message.get('template_name', '')
        print(template_name)
        if template_name:
            if template_name in buzhuan:
                content = template_name  # 需要回复的官方信息

            elif template_name in zhuan:
                content = "转人工"  # 需要回复的官方信息
            else:
                pass

        return content


def print_and_return_messages(messages_lists, cookiesstr):
    testdata=''

    for i in range(len(messages_lists)):
        messtext=json.loads(messages_lists[i])
        if i==0:
            testdata = testzl(messtext, cookiesstr, i)
        else:
            houcontent=testzl(messtext, cookiesstr, i)
            testdata['content']=testdata['content']+str(houcontent)

    if '将该会话转移给' in testdata['content']:
        return True
    for gebuzhuan in buzhuan:
        if testdata['content']!=gebuzhuan and gebuzhuan in testdata['content']:
            testdata['content']=testdata['content'].replace(gebuzhuan,'')
    return testdata


def chamainzhu(messages_lists,cookiesstr,workflow_id,shopname):
  try:
    _check_config_refresh()
    testdata=print_and_return_messages(messages_lists, cookiesstr)
    if testdata==True:
        return True

    userid=testdata['userid']
    merchant_log.success(f"店铺{shopname}{userid}:{testdata['content']}",shopname,"聊天记录")
    if testdata['content'] =="zdyi":
        return True

    testdata['anti'] = pddanti()  # 每次调用实时生成anti密令（上传coze的参数）
    # 按店铺 ID 取人工账号；其 mmsId 即 Coze 转人工所需的 zrgmisid。
    zhuanyuan = zk_api.huoqu_zhuanyuan(testdata['shopid']).get('Data', [])
    testdata['zrgmisid'] = str(zhuanyuan[0].get('mmsId', '')) if zhuanyuan else ''

    conversation_id=cozehuoquid()
    sendmessagetest=cozeduihua(conversation_id, testdata, workflow_id)

    merchant_log.success(f"Coze返回 {userid}:{sendmessagetest}",shopname,"聊天记录")
    return True
  except Exception as e:
      merchant_log.error(f"机器人异常:{e}", shopname, "运行日志")
      return False


# ===================== 启动预检：转接人 =====================
def getzhecsid(cookies, shopid):
    response = zk_api.huoqu_zhuanyuan(shopid)
    data_list = response.get('Data', [])
    if data_list:
        # 中控人工账号的 mmsId 就是转人工使用的 misid，无须再到可转接列表二次匹配。
        zrgmisid = str(data_list[0].get('mmsId', ''))
        username = data_list[0].get('AccountName', '') or ''
        return zrgmisid, username, response
    return None, '', response


def check_transfer_person(cookies, shopid, shopname):
    zrgmisid, username, response = getzhecsid(cookies, shopid)
    if not zrgmisid:
        data_list = response.get('Data', [])
        first_da = data_list[0] if data_list else {}
        account_name = first_da.get('AccountName', '') or ''

        notify_msg = f"{account_name} 店铺{shopname} 转接人为空，检测人工账号是否在线"
        merchant_log.error(f"店铺{shopname}转接人为空，消息：{notify_msg}", shopname, "运行日志")
        zk_api.add_pending_task(response.get('shop_id'), notify_msg)
    return username
