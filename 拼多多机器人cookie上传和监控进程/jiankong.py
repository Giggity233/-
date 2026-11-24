import time
import sys
from pathlib import Path
from loggerset import merchant_log
from pdd_api import xiangying, pddmove_conversation, pddsendmassage
import json

# 缓存结构: {buyer_uid: first_unreply_ts}
# 只存储用户发的第一条未回复消息时间
_unreplied_users = {}

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent

with open(APP_DIR / 'data' / 'jiankong.json', 'r', encoding='utf-8') as f:
    jiankong_data = json.load(f)

TRANSFER_TIMEOUT = int(jiankong_data['transfer_timeout'])
FALLBACK_TIMEOUT = int(jiankong_data['fallback_timeout'])


def dangqianmain(cookies, csid, shopname):
    global _unreplied_users
    
    try:
        conversations = xiangying(cookies)
    except Exception as e:
        merchant_log.error(f"获取会话列表异常: {e}", shopname, "异常监控日志")
        return
    
    now = int(time.time())
    mell_uid = cookies['PASS_ID'].split('_')[-2]
    
    # 当前会话中所有用户的UID集合
    current_users = set()
    
    # 遍历所有会话消息
    for conv in conversations:
        try:
            # 只处理用户发给店铺的消息
            if conv['from']['role'] == 'user' and conv['to']['role'] == 'mall_cs':
                buyer_uid = conv['from']['uid']
                current_users.add(buyer_uid)
                
                # 如果缓存中没有该用户，记录第一条消息时间
                if buyer_uid not in _unreplied_users:
                    _unreplied_users[buyer_uid] = int(conv['ts'])
            
            # 如果是店铺回复用户，删除缓存
            elif conv['from']['role'] == 'mall_cs' and conv['to']['role'] == 'user':
                buyer_uid = conv['to']['uid']
                current_users.add(buyer_uid)
                
                if buyer_uid in _unreplied_users:
                    del _unreplied_users[buyer_uid]
        
        except Exception as e:
            merchant_log.error(f"处理消息异常: {e}", shopname, "异常监控日志")
            continue
    
    # 删除缓存中不在当前会话的用户（会话已关闭或转移）
    to_remove = [uid for uid in _unreplied_users if uid not in current_users]
    for uid in to_remove:
        del _unreplied_users[uid]
    
    # 检查缓存中用户的超时情况
    for buyer_uid in list(_unreplied_users.keys()):
        first_ts = _unreplied_users[buyer_uid]
        wait_time = now - first_ts
        
        # 超时判断：fallback_timeout秒 <= 等待时间 < 转接阈值
        if FALLBACK_TIMEOUT <= wait_time < TRANSFER_TIMEOUT:
            merchant_log.warn(f"超时转出 - 用户:{buyer_uid}, 等待时间:{wait_time}秒", shopname, "异常监控日志")
            try:
                pddsendmassage(cookies, mell_uid, buyer_uid, "亲亲，人工客服正在为您处理，请稍等哈")
                result = pddmove_conversation(cookies, csid, buyer_uid)
                transfer_ok = (
                    isinstance(result, dict)
                    and result.get('success') is True
                    and (result.get('result') or {}).get('result') == 'ok'
                )
                # PDD reports 100063 when the conversation is already owned
                # by the target account.  For this monitor the target is the
                # current Cookie's human account, so it is an idempotent
                # success rather than a retryable failure.
                already_at_cookie_human = (
                    isinstance(result, dict)
                    and result.get('success') is True
                    and (result.get('result') or {}).get('response') == 'move_conversation'
                    and str((result.get('result') or {}).get('error_code')) == '100063'
                )
                if transfer_ok or already_at_cookie_human:
                    del _unreplied_users[buyer_uid]  # 转出成功，删除缓存
                    if already_at_cookie_human:
                        merchant_log.success(
                            f"用户已在当前 Cookie 人工账号名下，无需重复转接 - 用户:{buyer_uid}",
                            shopname,
                            "异常监控日志",
                        )
                    else:
                        merchant_log.success(f"转出成功 - 用户:{buyer_uid}", shopname, "异常监控日志")
                else:
                    merchant_log.error(f"转出失败 - 用户:{buyer_uid}, 返回:{result}", shopname, "异常监控日志")
            except Exception as e:
                merchant_log.error(f"转出异常 - 用户:{buyer_uid}, 错误:{e}", shopname, "异常监控日志")
