# Source Generated with Decompyle++
# File: pdd_group_cookie_runner.pyc (Python 3.10)

'''独立的拼多多店铺 Cookie 更新器。

不依赖、也不会关闭或重启 ``pdd多店管理.exe``。程序会：

1. 按 ``D:\\aibot\\groupN\\<调试端口>\\user-data`` 发现店铺；
2. 直接用该店铺自己的浏览器用户目录打开拼多多商家后台；
3. Cookie 有效时将店铺信息上传到中控；
4. 启动时从中控 Cookie 列表读取人工账号密码，Cookie 无效时按店铺匹配并自动登录；
5. 自动登录仍没有得到有效 Cookie 时，创建普通待处理事务 ``自动登录失败``。

默认会一直按 group1、group2……轮询；``ipyuan.json`` 的 ``interval`` 是相邻
分组之间的等待秒数，``thread`` 是同时处理的店铺数（未配置时为 3）。按 Ctrl+C
可停止。使用 ``--once`` 可只执行一轮，便于测试。
'''
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
import requests
from pdd_login_status import CookieExpiredError, ConfigError, DEFAULT_API_CONFIG_FILE, DEFAULT_LOGIN_INFO_FILE, DEFAULT_PROFILE_ROOT, HTTP_TIMEOUT, find_shop_record, get_pdd_shop_info, load_server_config, report_auto_login_failure, upsert_cookie
PDD_HOME_URL = 'https://mms.pinduoduo.com/home/'
PDD_LOGIN_URL = 'https://mms.pinduoduo.com/login/'
DEFAULT_BROWSER_WAIT_SECONDS = 30
DEFAULT_LOGIN_WAIT_SECONDS = 45
AUTO_LOGIN_STEP_WAIT_SECONDS = 3
ShopLoginCredential = dataclass(True, **('frozen',))(<NODE:12>)

def fetch_shop_login_credentials(base_url):
    '''Fetch the current PDD human-account credentials once per program run.'''
    response = requests.get(f'''{base_url.rstrip('/')}/api/v1/cookies/''', {
        'platform': 'pdd' }, HTTP_TIMEOUT, **('params', 'timeout'))
    response.raise_for_status()
    payload = response.json()
    data = payload.get('data') if isinstance(payload, Mapping) else None
    if not isinstance(data, list):
        raise ValueError('中控店铺 Cookie 接口响应中没有 data 列表')
    credentials = []
    for shop in data:
        if not isinstance(shop, Mapping):
            continue
        if not shop.get('shop_id'):
            pass
        shop_id = str('').strip()
        if not shop.get('shop_name'):
            pass
        shop_name = str('').strip()
        accounts = shop.get('human_accounts')
        if not isinstance(accounts, list):
            continue
        for account in accounts:
            if not isinstance(account, Mapping):
                continue
            if not account.get('account_type_name'):
                pass
            account_type_name = str('').strip()
            if not account.get('account_type'):
                pass
            account_type = str('').strip().lower()
            if account_type_name != '人工账号' and account_type != 'human':
                continue
            if not account.get('login_account'):
                pass
            login_account = str('').strip()
            if not account.get('login_password'):
                pass
            login_password = str('')
            if not login_account or not login_password:
                continue
            credentials.append(ShopLoginCredential(shop_id, shop_name, login_account, login_password, **('shop_id', 'shop_name', 'login_account', 'login_password')))
            return credentials


def match_shop_login_credential(group_name, port, login_info_file, credentials):
    '''Match a group port to the API account by archived shop ID or name.'''
    record = find_shop_record(login_info_file, group_name, port)
    if not record:
        return None
    if not record.get('shop_id'):
        pass
    archived_id = str('').strip()
    if not record.get('shop_name'):
        pass
    archived_name = str('').strip()
    candidates = list(credentials)
    if archived_id:
        for credential in candidates:
            if credential.shop_id == archived_id:
                return credential
            if archived_name:
                for credential in candidates:
                    if credential.shop_name == archived_name:
                        return credential
                    return None


def discover_groups(profile_root):
    '''Return groups containing at least one numeric browser-port directory.'''
    groups = []
    
    try:
        entries = list(profile_root.iterdir())
    if OSError:
        exc = None
        
        try:
            raise ConfigError(f'''无法读取店铺根目录 {profile_root}：{exc}''') from exc
            exc = None
            del exc
            for entry in entries:
                match = re.fullmatch('group(\\d+)', entry.name, re.IGNORECASE)
                if not match or not entry.is_dir():
                    continue
                
                try:
                    has_profile = any((lambda .0: for child in .0:
if child.is_dir():
passchild.name.isdigit())(entry.iterdir()))
                if OSError:
                    has_profile = False
                

                if has_profile:
                    groups.append((int(match.group(1)), entry.name))
            return (lambda .0: [ name for _, name in .0 ])(sorted(groups))




def discover_shop_profiles(group_name, profile_root):
    '''Return ``(remote_debugging_port, user_data_dir)`` for one group.'''
    group_path = profile_root / group_name
    profiles = []
    
    try:
        entries = list(group_path.iterdir())
    if OSError:
        exc = None
        
        try:
            print(f'''{group_name}：无法读取分组目录：{exc}''')
        finally:
            exc = None
            del exc
            return None
            exc = None
            del exc
            for entry in entries:
                if not entry.is_dir() or not entry.name.isdigit():
                    continue
                user_data_dir = entry / 'user-data'
                if user_data_dir.is_dir():
                    profiles.append((int(entry.name), user_data_dir))
                    continue
                print(f'''{group_name}：端口 {entry.name} 缺少 user-data，已跳过。''')
            return sorted(profiles)




def find_edge_executable():
    """Find Microsoft Edge, which can load the manager's Chromium profile."""
    candidates = [
        Path.home() / 'AppData/Local/Microsoft/Edge/Application/msedge.exe',
        Path('C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'),
        Path('C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe')]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
        resolved = shutil.which('msedge.exe')
        if resolved:
            return Path(resolved)
        return None


def browser_is_ready(port):
    """Check the store's remote-debugging endpoint before attaching."""
    
    try:
        response = requests.get(f'''http://127.0.0.1:{port}/json/version''', 1, **('timeout',))
    if requests.RequestException:
        return False



def start_browser(browser_exe, port, user_data_dir):
    """Open one minimized Edge store window using the manager's profile layout."""
    webview_data_dir = user_data_dir / 'EBWebView'
    
    try:
        subprocess.Popen([
            str(browser_exe),
            f'''--user-data-dir={webview_data_dir}''',
            '--remote-allow-origins=http://127.0.0.1',
            f'''--remote-debugging-port={port}''',
            '--no-first-run',
            '--no-default-browser-check',
            '--noerrdialogs',
            '--disable-session-crashed-bubble',
            '--disable-notifications',
            '--disable-prompt-on-repost',
            '--disable-features=Translate,MediaRouter,OptimizationHints,msEdgeSidebarV2',
            '--start-minimized',
            PDD_HOME_URL], str(webview_data_dir), **('cwd',))
    if OSError:
        exc = None
        
        try:
            print(f'''端口 {port}：浏览器启动失败：{exc}''')
        finally:
            exc = None
            del exc
            return False
            exc = None
            del exc




def open_store_browser(port, user_data_dir, *, browser_exe, startup_wait):
    '''Attach to the store browser, launching it when its debug port is absent.'''
    from DrissionPage import ChromiumPage
    from DrissionPage._functions.settings import Settings
    Settings.set_auto_handle_alert(True)
    if not browser_is_ready(port):
        print(f'''端口 {port}：启动店铺浏览器并打开拼多多商家后台。''')
        if not start_browser(browser_exe, port, user_data_dir):
            return None
        deadline = time.monotonic() + startup_wait
        if time.monotonic() < deadline:
            if browser_is_ready(port):
                pass
            else:
                time.sleep(1)
                if not time.monotonic() < deadline:
                    print(f'''端口 {port}：浏览器调试端口启动超时。''')
                    return None
    
    try:
        page = ChromiumPage(port)
        
        try:
            page.get(PDD_HOME_URL)
        if Exception:
            close_store_browser(page)
            raise
        if Exception:
            exc = Exception
            
            try:
                print(f'''端口 {port}：无法连接店铺浏览器：{exc}''')
            finally:
                exc = None
                del exc
                return None
                exc = None
                del exc





def close_store_browser(page):
    '''Close the complete store browser while preserving its profile data.'''
    
    try:
        page.quit(5, True, False, **('timeout', 'force', 'del_data'))
        print('店铺浏览器已关闭。')
    if Exception:
        exc = None
        
        try:
            print(f'''关闭店铺浏览器失败：{exc}''')
        finally:
            exc = None
            del exc
            return None
            exc = None
            del exc




def cookie_payload_from_page(page):
    '''Validate the current browser session and build the middle-platform payload.'''
    cookies = page.cookies().as_dict()
    cookie_text = page.cookies().as_str()
    if not cookie_text.strip():
        raise CookieExpiredError('浏览器没有返回 Cookie')
    return get_pdd_shop_info(cookies, cookie_text)


def _open_account_login_tab(page):
    """Switch PDD's login page from QR login to the account/password form."""
    script = '\n        const candidates = [...document.querySelectorAll(\'button, a, div, span\')];\n        const tab = candidates.find((element) => {\n          const text = (element.innerText || \'\').trim();\n          return /^(账号登录|密码登录)$/.test(text);\n        });\n        if (tab) { tab.click(); return true; }\n        return Boolean(document.querySelector(\'#usernameId, input[name="username"], input[type="password"]\'));\n    '
    
    try:
        pass
    if Exception:
        return False



def _fill_account_login(page, login_account, login_password):
    """Fill PDD's account/password inputs and dispatch normal input events."""
    account_literal = json.dumps(login_account, False, **('ensure_ascii',))
    password_literal = json.dumps(login_password, False, **('ensure_ascii',))
    script = f'''\n        const account = document.querySelector(\'#usernameId, input[name="username"], input[type="text"]\');\n        const password = document.querySelector(\'#passwordId, input[name="password"], input[type="password"]\');\n        if (!account || !password) return false;\n        const setValue = (element, value) => {{\n          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, \'value\').set;\n          setter.call(element, value);\n          element.dispatchEvent(new Event(\'input\', {{bubbles: true}}));\n          element.dispatchEvent(new Event(\'change\', {{bubbles: true}}));\n        }};\n        setValue(account, {account_literal});\n        setValue(password, {password_literal});\n        return true;\n    '''
    
    try:
        pass
    if Exception:
        return False



def _submit_login(page):
    '''Click the login submit control without handling QR/SMS/captcha challenges.'''
    script = '\n        const selectors = [\n          \'button[type="submit"]\',\n          \'input[type="submit"]\',\n          \'[data-testid="login-submit"]\'\n        ];\n        for (const selector of selectors) {\n          const element = document.querySelector(selector);\n          if (element && !element.disabled) { element.click(); return true; }\n        }\n        const candidates = [...document.querySelectorAll(\'button, a, div[role="button"]\')];\n        const button = candidates.find((element) => /^(登录|立即登录)$/.test((element.innerText || \'\').trim()));\n        if (button && !button.disabled) { button.click(); return true; }\n        return false;\n    '
    
    try:
        pass
    if Exception:
        return False



def attempt_account_password_login(page, wait_seconds, credential):
    '''Log in with the matched human account and return whether the session is valid.'''
    if credential is None:
        print('Cookie 无效：未匹配到该店铺的人工账号，无法自动登录。')
        return False
    print(f'''Cookie 无效，正在使用店铺 {credential.shop_name} 的人工账号自动登录。''')
    print(f'''当前自动登录账号：{credential.login_account}，密码：{credential.login_password}''')
    
    try:
        page.get(PDD_LOGIN_URL)
    if Exception:
        exc = None
        
        try:
            print(f'''无法打开拼多多登录页：{exc}''')
        finally:
            exc = None
            del exc
            return False
            exc = None
            del exc
            time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
            submitted = False
            deadline = time.monotonic() + wait_seconds
            if time.monotonic() < deadline:
                
                try:
                    cookies = page.cookies().as_dict()
                    if cookies.get('PASS_ID') or cookies.get('PDDAccessToken'):
                        cookie_payload_from_page(page)

                if not submitted:
                    if _open_account_login_tab(page):
                        print('已点击账号登录，等待 3 秒。')
                        time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
                    if _fill_account_login(page, credential.login_account, credential.login_password):
                        print('已填写账号密码，等待 3 秒。')
                        time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
                        submitted = _submit_login(page)
                        if submitted:
                            print('已点击登录，等待 3 秒。')
                            time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
                if not submitted:
                    time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
                if not time.monotonic() < deadline:
                    print('自动登录未获得有效 Cookie（可能需要扫码、短信或验证码）。')
                    return False




def _process_store_legacy(group_name, port, user_data_dir, *, base_url, browser_exe, browser_wait, login_wait, login_info_file, login_credentials):
    '''Open, update, attempt login, then report the outcome for one store.'''
    page = open_store_browser(port, user_data_dir, browser_exe, browser_wait, **('browser_exe', 'startup_wait'))
    if page is None:
        report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
        return False
    credential = match_shop_login_credential(group_name, port, login_info_file, login_credentials)
    
    try:
        shop_info = cookie_payload_from_page(page)
    if (CookieExpiredError, ValueError):
        if not attempt_account_password_login(page, login_wait, credential):
            report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
            return False
        
        try:
            shop_info = cookie_payload_from_page(page)
        if (CookieExpiredError, requests.RequestException, ValueError):
            exc = None
            
            try:
                print(f'''端口 {port}：自动登录后 Cookie 仍不可用：{exc}''')
                report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
            if (requests.RequestException, ValueError):
                exc = None
                
                try:
                    print(f'''端口 {port}：Cookie 验证失败：{exc}''')
                finally:
                    exc = None
                    del exc
                    return False
                    exc = None
                    del exc
                    
                    try:
                        
                        try:
                            result = upsert_cookie(base_url, shop_info)
                            action = '新增' if result.get('created') else '更新'
                            print(f'''{group_name} 端口 {port}：{action} {shop_info['shop_name']} Cookie 成功。''')
                        if (requests.RequestException, ValueError):
                            exc = None
                            
                            try:
                                print(f'''{group_name} 端口 {port}：Cookie 上传失败：{exc}''')
                            finally:
                                exc = None
                                del exc
                                close_store_browser(page)
                                return False
                                exc = None
                                del exc
                                close_store_browser(page)









def process_store(group_name, port, user_data_dir, *, base_url, browser_exe, browser_wait, login_wait, login_info_file, login_credentials):
    '''Process one store and always close its browser before returning.'''
    page = open_store_browser(port, user_data_dir, browser_exe, browser_wait, **('browser_exe', 'startup_wait'))
    if page is None:
        report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
        return False
    
    try:
        
        try:
            credential = match_shop_login_credential(group_name, port, login_info_file, login_credentials)
            
            try:
                shop_info = cookie_payload_from_page(page)
            if (CookieExpiredError, ValueError):
                if not attempt_account_password_login(page, login_wait, credential):
                    report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
            return False
            
            try:
                shop_info = cookie_payload_from_page(page)
            if (CookieExpiredError, requests.RequestException, ValueError):
                exc = (CookieExpiredError, ValueError)
                
                try:
                    print(f'''port {port}: Cookie still invalid after login: {exc}''')
                    report_auto_login_failure(base_url, port, group_name, login_info_file, **('login_info_file',))
                if requests.RequestException:
                    exc = (CookieExpiredError, ValueError)
                    
                    try:
                        print(f'''port {port}: Cookie validation failed: {exc}''')
                    if (requests.RequestException, ValueError):
                        exc = (CookieExpiredError, ValueError)
                        
                        try:
                            print(f'''{group_name} port {port}: Cookie upload failed: {exc}''')
                        finally:
                            exc = None
                            del exc
                            close_store_browser(page)
                            return False
                            exc = None
                            del exc
                            close_store_browser(page)









def process_group(group_name, *, profile_root, base_url, browser_exe, browser_wait, login_wait, thread, login_info_file, login_credentials):
    '''Update every shop in one group once and return ``(success, total)``.'''
    stores = discover_shop_profiles(group_name, profile_root)
    print(f'''{group_name}：发现 {len(stores)} 个店铺。''')
    if not stores:
        return (0, 0)
    print(f'''{group_name}：同时处理最多 {thread} 个店铺。''')
    success = 0
    with (lambda .0: { }# WARNING: Decompyle incomplete
)(stores) as futures:
        executor = ThreadPoolExecutor(thread, 'pdd-store', **('max_workers', 'thread_name_prefix'))
        for future in as_completed(futures):
            port = futures[future]
            
            try:
                success += int(future.result())
            if Exception:
                exc = None
                
                try:
                    print(f'''{group_name} 端口 {port}：处理失败：{exc}''')
                finally:
                    exc = None
                    del exc
                    continue
                    exc = None
                    del exc
                    None(None, None, None)
                if not None:
                    pass


    print(f'''{group_name}：本次完成，成功 {success}/{len(stores)}。''')
    return (success, len(stores))


def cli(argv = None):
    parser = argparse.ArgumentParser('独立轮询拼多多分组并更新 Cookie', **('description',))
    parser.add_argument('--profile-root', Path, DEFAULT_PROFILE_ROOT, **('type', 'default'))
    parser.add_argument('--api-config', Path, DEFAULT_API_CONFIG_FILE, **('type', 'default'))
    parser.add_argument('--api-base-url', '临时覆盖 ipyuan.json 的中控地址', **('help',))
    parser.add_argument('--login-info', Path, DEFAULT_LOGIN_INFO_FILE, **('type', 'default'))
    parser.add_argument('--edge', '--browser', 'edge', Path, 'Microsoft Edge 路径（默认自动查找；--browser 为兼容别名）', **('dest', 'type', 'help'))
    parser.add_argument('--interval', int, '相邻分组之间的等待秒数', **('type', 'help'))
    parser.add_argument('--browser-wait', int, DEFAULT_BROWSER_WAIT_SECONDS, **('type', 'default'))
    parser.add_argument('--login-wait', int, DEFAULT_LOGIN_WAIT_SECONDS, **('type', 'default'))
    parser.add_argument('--once', 'store_true', '只执行全部分组一轮后退出', **('action', 'help'))
    args = parser.parse_args(list(argv) if argv is not None else None)
    if min(args.browser_wait, args.login_wait) <= 0:
        parser.error('--browser-wait 和 --login-wait 必须是正整数')
    
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
            interval = args.interval if args.interval is not None else config.interval
            if interval <= 0:
                parser.error('--interval 必须是正整数')
            thread = config.thread
            if not args.edge:
                pass
            browser_exe = find_edge_executable()
            if browser_exe is None or not browser_exe.is_file():
                print('启动失败：未找到 Microsoft Edge，请通过 --edge 指定路径。')
                return 1
            if not args.api_base_url:
                pass
            base_url = config.base_url
            
            try:
                login_credentials = fetch_shop_login_credentials(base_url)
                print(f'''已读取中控人工账号：{len(login_credentials)} 个店铺。''')
            if (requests.RequestException, ValueError):
                exc = None
                
                try:
                    login_credentials = []
                    print(f'''读取中控人工账号失败：{exc}；需要登录的店铺将按失败上报。''')
                finally:
                    exc = None
                    del exc
                exc = None
                del exc
                
                try:
                    groups = discover_groups(args.profile_root)
                    if not groups:
                        print(f'''未在 {args.profile_root} 找到有店铺的 groupN 分组。''')
                if KeyboardInterrupt:
                    print('已停止独立 Cookie 更新器。')
                    return 0






if __name__ == '__main__':
    raise SystemExit(cli())
