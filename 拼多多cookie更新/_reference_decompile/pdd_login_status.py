# Source Generated with Decompyle++
# File: pdd_login_status.pyc (Python 3.10)

'''拼多多店铺 Cookie 同步程序。

店铺启动程序负责自动登录；本程序只负责同步结果：

1. 连接 ``D:\\aibot\\<group>\\<port>`` 对应的浏览器调试端口；
2. 浏览器返回有效 Cookie 时，获取店铺基础信息并上传 Cookie；
3. 没有拿到有效 Cookie 时，按店铺创建一条普通待处理事务：
   ``自动登录失败``。

中控地址从 ``D:\\aibot\\ipyuan.json`` 读取。文件格式为：
``{"ip": "127.0.0.1", "port": 8000, "interval": 600, "thread": 3}``。
自动 ck 模式会在本组完成后按 ``interval`` 关闭并重启多店管理器；由管理器
根据自己的自动配置启动下一分组。传入 ``--once`` 才只同步当前分组且不切换。
'''
from __future__ import annotations
import argparse
import configparser
import ctypes
import json
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping
import requests
DEFAULT_PROFILE_ROOT = Path('D:\\aibot')
DEFAULT_API_CONFIG_FILE = DEFAULT_PROFILE_ROOT / 'ipyuan.json'
DEFAULT_LOGIN_INFO_FILE = DEFAULT_PROFILE_ROOT / 'user_login_info.json'
AUTO_RUN_CONFIG_FILE = DEFAULT_PROFILE_ROOT / 'pdd_aotu_run.ini'
DEFAULT_MANAGER_EXE = Path('C:\\Users\\Admin\\Desktop\\pdd多店管理.exe')
MANAGER_PROCESS_NAME = 'pdd多店管理.exe'
HTTP_TIMEOUT = 15
DEFAULT_STORE_THREAD_COUNT = 3
AUTO_RUN_MUTEX_NAME = 'Local\\PddCookieAutoRun'
PDD_MERCHANT_INFO_URL = 'https://mms.pinduoduo.com/earth/api/merchant/queryMerchantInfoByMallId'
PDD_MERCHANT_INFO_HEADERS = {
    'accept': '*/*',
    'accept-language': 'zh-CN,zh;q=0.9',
    'cache-control': 'max-age=0',
    'content-type': 'application/json',
    'origin': 'https://mms.pinduoduo.com',
    'referer': 'https://mms.pinduoduo.com/mallcenter/info/basic',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin' }

class ConfigError(ValueError):
    '''Raised when the local middle-platform configuration is unusable.'''
    pass


class CookieExpiredError(RuntimeError):
    '''Raised when the browser did not provide a usable Pinduoduo session.'''
    pass

ServerConfig = dataclass(True, **('frozen',))(<NODE:12>)

def load_server_config(path = DEFAULT_API_CONFIG_FILE):
    '''Read ``ip``/``port``/``interval``/``thread`` from ``ipyuan.json``.'''
    config_path = Path(path)
    
    try:
        with config_path.open('r', 'utf-8-sig', **('encoding',)) as file:
            raw_config = json.load(file)
        None(None, None, None)
    if not None:
        pass

    if FileNotFoundError:
        exc = None
        
        try:
            raise ConfigError(f'''未找到中控配置文件：{config_path}''') from exc
            exc = None
            del exc
            if json.JSONDecodeError:
                exc = None
                
                try:
                    raise ConfigError(f'''中控配置文件不是合法 JSON：{config_path}''') from exc
                    exc = None
                    del exc
                    if not isinstance(raw_config, dict):
                        raise ConfigError('中控配置必须是一个 JSON 对象')
                    if not raw_config.get('ip'):
                        pass
                    host = str('').strip()
                    if not host:
                        raise ConfigError('中控配置缺少 ip')
                    
                    try:
                        port = int(raw_config['port'])
                    if (KeyError, TypeError, ValueError):
                        exc = None
                        
                        try:
                            raise ConfigError('中控配置中的 port 必须是 1-65535 的整数') from exc
                            exc = None
                            del exc
                            if not (port <= port) or not (port <= 65535):
                                raise ConfigError('中控配置中的 port 必须是 1-65535 的整数')
                            1
                            raise ConfigError('中控配置中的 port 必须是 1-65535 的整数')
                            
                            try:
                                interval = int(raw_config.get('interval', 600))
                            if (TypeError, ValueError):
                                exc = None
                                
                                try:
                                    raise ConfigError('中控配置中的 interval 必须是正整数') from exc
                                    exc = None
                                    del exc
                                    if interval <= 0:
                                        raise ConfigError('中控配置中的 interval 必须是正整数')
                                    
                                    try:
                                        thread = int(raw_config.get('thread', DEFAULT_STORE_THREAD_COUNT))
                                    if (TypeError, ValueError):
                                        exc = None
                                        
                                        try:
                                            raise ConfigError('中控配置中的 thread 必须是正整数') from exc
                                            exc = None
                                            del exc
                                            if thread <= 0:
                                                raise ConfigError('中控配置中的 thread 必须是正整数')
                                            if host.startswith(('http://', 'https://')):
                                                base_url = host.rstrip('/')
                                                if ':' not in base_url.rsplit('/', 1)[-1]:
                                                    base_url = f'''{base_url}:{port}'''
                                                else:
                                                    base_url = f'''http://{host}:{port}'''
                                            return ServerConfig(base_url, interval, thread, **('base_url', 'interval', 'thread'))








# WARNING: Decompyle incomplete


def _error_message(data):
    '''Collect a PDD error message without depending on one response spelling.'''
    if not isinstance(data, Mapping):
        return ''
    return ' '.join((lambda .0: for field in .0:
if not data.get(field):
passstr(''))(('error_msg', 'errorMsg', 'message', 'msg')))


def _is_expired_response(data):
    message = _error_message(data)
    if not '会话已过期' in message:
        pass
    return '登录已过期' in message


def get_pdd_shop_info(cookies, cookie_text, *, request_session = requests):
    """Return the store payload required by ``/api/v1/cookies/upsert/``.

    The request deliberately uses the browser's cookie *mapping*, while the
    complete cookie string is preserved unchanged for the middle platform.
    """
    response = request_session.post(PDD_MERCHANT_INFO_URL, PDD_MERCHANT_INFO_HEADERS, dict(cookies), { }, HTTP_TIMEOUT, **('headers', 'cookies', 'json', 'timeout'))
    response.raise_for_status()
    data = response.json()
    if _is_expired_response(data):
        raise CookieExpiredError('拼多多返回：会话已过期')
    result = data.get('result') if isinstance(data, Mapping) else None
    if not isinstance(result, Mapping):
        if not _error_message(data):
            pass
        message = '响应中没有 result'
        raise ValueError(f'''获取拼多多店铺信息失败：{message}''')
    if not result.get('mallId') and not result.get('mall_id'):
        pass
    shop_id = str('').strip()
    if not result.get('mallName') and not result.get('mall_name'):
        pass
    shop_name = str('').strip()
    if not shop_id or not shop_name:
        raise ValueError('拼多多店铺信息缺少 mallId 或 mallName')
    if not result.get('mallCategoryStr') and not result.get('mall_category_str'):
        pass
    if not str('notfind').strip():
        pass
    return {
        'platform': 'pdd',
        'shop_id': shop_id,
        'shop_name': shop_name,
        'main_category': 'notfind',
        'cookie': cookie_text }


def upsert_cookie(base_url, shop_info, *, request_session = requests):
    '''Create or update a shop Cookie in the 联樽中控 API.'''
    response = request_session.post(f'''{base_url.rstrip('/')}/api/v1/cookies/upsert/''', dict(shop_info), HTTP_TIMEOUT, **('json', 'timeout'))
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping) or not data.get('ok', False):
        message = data.get('message') if isinstance(data, Mapping) else '中控响应不是 JSON 对象'
        if not message:
            pass
        raise ValueError('中控拒绝保存 Cookie')
    return data


def create_pending_task(base_url, shop_id, *, handling_item, time_type = requests, request_session = 'normal'):
    '''Create a pending task for an existing PDD store in the middle platform.'''
    response = request_session.post(f'''{base_url.rstrip('/')}/api/v1/pending-tasks/create/''', {
        'shop_id': str(shop_id),
        'platform': 'pdd',
        'time_type': time_type,
        'handling_item': handling_item }, HTTP_TIMEOUT, **('json', 'timeout'))
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, Mapping) or not data.get('ok', False):
        message = data.get('message') if isinstance(data, Mapping) else '中控响应不是 JSON 对象'
        if not message:
            pass
        raise ValueError('中控拒绝创建待处理事务')
    return data


def find_shop_record(path, group_name, port):
    '''Find the shop record saved by the browser-startup program for one port.'''
    
    try:
        with open(path, 'r', 'utf-8-sig', **('encoding',)) as file:
            data = json.load(file)
        None(None, None, None)
    if not None:
        pass

    if (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    group_items = data.get(group_name, []) if isinstance(data, dict) else []
    if not isinstance(group_items, list):
        return None
    return next((lambda .0: for item in .0:
if isinstance(item, dict) and item.get('port') == port:
itemcontinueNone)(group_items), None)
# WARNING: Decompyle incomplete


def report_auto_login_failure(base_url, port, group_name, *, login_info_file):
    """Report a non-urgent automatic-login failure for the port's saved shop."""
    shop_record = find_shop_record(login_info_file, group_name, port)
    if not shop_record:
        pass
    if not { }.get('shop_id'):
        pass
    shop_id = str('').strip()
    if not shop_id:
        print(f'''端口 {port} 未返回 Cookie，且未找到对应 shop_id，无法创建待处理事务。''')
        return False
    
    try:
        create_pending_task(base_url, shop_id, '自动登录失败', 'normal', **('handling_item', 'time_type'))
        print(f'''端口 {port}：已为店铺 {shop_id} 创建普通待处理事务：自动登录失败。''')
    if (requests.RequestException, ValueError):
        exc = None
        
        try:
            print(f'''端口 {port}：创建自动登录失败待处理事务失败：{exc}''')
        finally:
            exc = None
            del exc
            return False
            exc = None
            del exc




def get_browser_data(port, group_name, *, base_url, login_info_file = DEFAULT_LOGIN_INFO_FILE):
    """Upload a browser's Cookie, or report automatic-login failure if absent."""
    from DrissionPage import ChromiumPage
    
    try:
        page = ChromiumPage(port)
        cookies = page.cookies().as_dict()
        cookie_text = page.cookies().as_str()
    if Exception:
        exc = None
        
        try:
            print(f'''端口 {port} 无法取得 Cookie：{exc}''')
            report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
        finally:
            exc = None
            del exc
            return None
            exc = None
            del exc
            if not cookie_text.strip():
                report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
                return None
            
            try:
                shop_info = get_pdd_shop_info(cookies, cookie_text)
                upsert_result = upsert_cookie(base_url, shop_info)
                action = '新增' if upsert_result.get('created') else '更新'
                print(f'''端口 {port}：{action}店铺 {shop_info['shop_name']}（{shop_info['shop_id']}）Cookie 成功。''')
            if CookieExpiredError:
                print(f'''端口 {port}：未拿到有效 Cookie，按自动登录失败处理。''')
                report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
                return None
            if (requests.RequestException, ValueError, OSError):
                exc = CookieExpiredError
                
                try:
                    print(f'''端口 {port} 同步失败：{exc}''')
                if Exception:
                    exc = CookieExpiredError
                    
                    try:
                        print(f'''端口 {port} Cookie 同步异常：{exc}''')
                    finally:
                        exc = None
                        del exc
                        return None
                        exc = None
                        del exc







def get_ports_from_directory(group_name, profile_root = DEFAULT_PROFILE_ROOT):
    '''List numeric browser-port folders in one aibot group.'''
    group_path = profile_root / group_name
    
    try:
        pass
    if FileNotFoundError:
        print(f'''未找到浏览器分组目录：{group_path}''')
        return None



def process_group(group_name, *, base_url, profile_root = DEFAULT_LOGIN_INFO_FILE, login_info_file = DEFAULT_PROFILE_ROOT):
    '''Synchronise all browser profiles of one group once.'''
    ports = get_ports_from_directory(group_name, profile_root)
    print(f'''{group_name}：发现端口 {ports}''')
    results = []
    for port in ports:
        shop_info = get_browser_data(port, group_name, base_url, login_info_file, **('base_url', 'login_info_file'))
        if shop_info:
            results.append(shop_info)
    print(f'''{group_name}：本轮成功同步 {len(results)}/{len(ports)} 个店铺。''')
    return results


def _group_mapping():
    return (lambda .0: { }# WARNING: Decompyle incomplete
)(range(1, 59))


def get_auto_groups(profile_root = DEFAULT_PROFILE_ROOT):
    '''Return non-empty group folders in the order used by the auto-run manager.'''
    groups = []
    for entry in profile_root.iterdir():
        if not (entry.is_dir() and entry.name.lower().startswith('group')) or not entry.name[5:].isdigit():
            continue
        if any((lambda .0: for child in .0:
if child.is_dir():
passchild.name.isdigit())(entry.iterdir())):
            groups.append(entry.name.lower())
    return sorted(groups, (lambda name: int(name[5:])), **('key',))


def set_next_auto_group(current_group, *, profile_root = AUTO_RUN_CONFIG_FILE, auto_run_config = DEFAULT_PROFILE_ROOT):
    '''Advance ``pdd_aotu_run.ini`` so the restarted manager opens the next group.

    The manager stores a zero-based group index: ``1`` means ``group2``.
    '''
    
    try:
        groups = get_auto_groups(profile_root)
    if FileNotFoundError:
        print(f'''未找到分组根目录：{profile_root}''')
        return None
    if not groups:
        print('未找到可自动切换的分组目录。')
        return None
    normalized_current = current_group.lower()
    
    try:
        current_index = groups.index(normalized_current)
    if ValueError:
        FileNotFoundError
        FileNotFoundError
        print(f'''当前分组 {current_group} 不在自动分组列表中，无法推进索引。''')
        return None
    next_group = groups[(current_index + 1) % len(groups)]
    parser = configparser.ConfigParser()
    parser.optionxform = str
    
    try:
        with auto_run_config.open('r', 'utf-8-sig', **('encoding',)) as file:
            parser.read_file(file)
        ValueError(None, None, None)
    if not None:
        pass



    FileNotFoundError
    FileNotFoundError
    FileNotFoundError
    if FileNotFoundError:
        print(f'''未找到自动ck配置文件：{auto_run_config}''')
        return None
    if (OSError, configparser.Error):
        exc = FileNotFoundError
        
        try:
            print(f'''读取自动ck配置失败：{exc}''')
        finally:
            exc = None
            del exc
            return None
            exc = None
            del exc
            if not parser.has_section('count'):
                parser.add_section('count')
            parser.set('count', 'index', str(int(next_group[5:]) - 1))
            
            try:
                with auto_run_config.open('w', 'utf-8', **('encoding',)) as file:
                    parser.write(file, False, **('space_around_delimiters',))
                FileNotFoundError(None, None, None)
            if OSError:
                exc = None
                
                try:
                    print(f'''写入下一分组配置失败：{exc}''')
                finally:
                    exc = None
                    del exc
                    return None
                    exc = None
                    del exc



# WARNING: Decompyle incomplete


def close_manager(process_name = MANAGER_PROCESS_NAME):
    '''Request a normal manager shutdown before switching to the next group.'''
    import psutil
    import win32con
    import win32gui
    import win32process
    processes = (lambda .0: [ process for process in .0 if process.info.get('name', '').casefold() == process_name.casefold() ])(psutil.process_iter([
        'name']))
    if not processes:
        print(f'''未发现正在运行的 {process_name}，直接启动下一分组。''')
        return True
    pids = (lambda .0: {}# WARNING: Decompyle incomplete
)(processes)
    
    def close_window(window_handle, _extra):
        (_thread_id, process_id) = win32process.GetWindowThreadProcessId(window_handle)
        if process_id in pids:
            win32gui.PostMessage(window_handle, win32con.WM_CLOSE, 0, 0)
            return None

    win32gui.EnumWindows(close_window, None)
    print(f'''已请求正常关闭 {process_name}，等待它保存自动分组状态。''')
    (_gone, alive) = psutil.wait_procs(processes, 15, **('timeout',))
    for process in alive:
        
        try:
            process.kill()
        if psutil.Error:
            exc = None
            
            try:
                print(f'''强制关闭管理器进程失败（PID {process.pid}）：{exc}''')
            finally:
                exc = None
                del exc
                continue
                exc = None
                del exc
                return True




def run_manager(executable):
    '''Open the multi-store manager, which reads the auto-run INI and switches group.'''
    if not executable.is_file():
        print(f'''未找到拼多多多店管理程序：{executable}''')
        return False
    
    try:
        subprocess.Popen([
            str(executable)], str(executable.parent), **('cwd',))
        print(f'''已启动拼多多多店管理：{executable}''')
    if OSError:
        exc = None
        
        try:
            print(f'''启动拼多多多店管理失败：{exc}''')
        finally:
            exc = None
            del exc
            return False
            exc = None
            del exc




def wait_for_group_browser(group_name, *, profile_root = 60, timeout = DEFAULT_PROFILE_ROOT):
    '''Wait until the restarted manager exposes at least one group browser port.'''
    ports = get_ports_from_directory(group_name, profile_root)
    if not ports:
        return False
    deadline = time.monotonic() + timeout
    print(f'''等待 {group_name} 浏览器启动：{ports}''')
    if time.monotonic() < deadline:
        for port in ports:
            
            try:
                response = requests.get(f'''http://127.0.0.1:{port}/json/version''', 1, **('timeout',))
                if response.ok:
                    pass
            if requests.RequestException:
                continue

            time.sleep(1)
            if not time.monotonic() < deadline:
                print(f'''等待 {group_name} 浏览器启动超时，继续尝试该分组。''')
                return False


def acquire_auto_run_lock():
    '''Allow only one persistent auto-ck controller at a time.'''
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, AUTO_RUN_MUTEX_NAME)
    if not handle:
        raise OSError('无法创建自动ck单实例锁')
    if kernel32.GetLastError() == 183:
        kernel32.CloseHandle(handle)
        return None
    return int(handle)


def release_auto_run_lock(handle):
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return None


def cli(argv = None):
    parser = argparse.ArgumentParser('同步拼多多浏览器 Cookie 到联樽中控', **('description',))
    parser.add_argument('group', '分组编号（1-58）或分组名（group1-group58）', **('help',))
    parser.add_argument('--profile-root', Path, DEFAULT_PROFILE_ROOT, **('type', 'default'))
    parser.add_argument('--api-config', Path, DEFAULT_API_CONFIG_FILE, '中控 IP、端口和轮询间隔配置；默认 D:\\aibot\\ipyuan.json', **('type', 'default', 'help'))
    parser.add_argument('--api-base-url', '临时覆盖 ipyuan.json 中的中控地址', **('help',))
    parser.add_argument('--login-info', Path, DEFAULT_LOGIN_INFO_FILE, **('type', 'default'))
    parser.add_argument('--watch', 'store_true', '兼容参数；自动ck默认按分组交接', **('action', 'help'))
    parser.add_argument('--once', 'store_true', '仅同步当前分组，不关闭或重启管理器', **('action', 'help'))
    parser.add_argument('--restart', 'store_true', '兼容自动ck：本组完成后关闭管理器并启动下一分组', **('action', 'help'))
    parser.add_argument('--manager-exe', Path, DEFAULT_MANAGER_EXE, '拼多多多店管理.exe 的路径', **('type', 'default', 'help'))
    parser.add_argument('--interval', int, '覆盖 ipyuan.json 的轮询间隔（秒）', **('type', 'help'))
    args = parser.parse_args(list(argv) if argv is not None else None)
    raw_group = args.group.strip().lower()
    group_name = raw_group if raw_group in _group_mapping().values() else _group_mapping().get(raw_group)
    if not group_name:
        parser.error('group 必须是 1-58 或 group1-group58')
    if args.interval is not None and args.interval <= 0:
        parser.error('--interval 必须是正整数')
    if args.api_base_url:
        base_url = args.api_base_url.rstrip('/')
        if not args.interval:
            pass
        interval = 600
    else:
        
        try:
            config = load_server_config(args.api_config)
        if ConfigError:
            exc = None
            
            try:
                print(f'''启动失败：{exc}''')
            finally:
                exc = None
                del exc
                return 1
                exc = None
                del exc
                base_url = config.base_url
                if not args.interval:
                    pass
                interval = config.interval
                print(f'''中控地址：{base_url}；目标分组：{group_name}''')
                
                try:
                    process_group(group_name, base_url, args.profile_root, args.login_info, **('base_url', 'profile_root', 'login_info_file'))
                    if args.once:
                        pass
                if KeyboardInterrupt:
                    print('已停止 Cookie 同步。')
                    return 0




if __name__ == '__main__':
    raise SystemExit(cli())
