"""独立轮询拼多多分组并同步 Cookie。

恢复自 ``拼多多cookie更新和自动登录.exe`` 的 Python 3.10 字节码。日常同步
使用普通 Edge 取得 Cookie，并请求浏览器最小化；若 Edge 忽略最小化请求，则以
右上角小窗口运行。Cookie 已失效、需要自动登录时，会打开可见的普通浏览器窗口。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import requests

from pdd_login_status import (
    CookieExpiredError,
    ConfigError,
    DEFAULT_API_CONFIG_FILE,
    DEFAULT_LOGIN_INFO_FILE,
    DEFAULT_PROFILE_ROOT,
    HTTP_TIMEOUT,
    find_shop_record,
    get_pdd_shop_info,
    load_server_config,
    report_auto_login_failure,
    upsert_cookie,
)

PDD_HOME_URL = "https://mms.pinduoduo.com/home/"
PDD_LOGIN_URL = "https://mms.pinduoduo.com/login/"
DEFAULT_BROWSER_WAIT_SECONDS = 30
DEFAULT_LOGIN_WAIT_SECONDS = 45
AUTO_LOGIN_STEP_WAIT_SECONDS = 3

BrowserMode = str  # "routine" | "login"


@dataclass(frozen=True)
class ShopLoginCredential:
    """中控返回的一个店铺人工账号。"""

    shop_id: str
    shop_name: str
    login_account: str
    login_password: str


def fetch_shop_login_credentials(base_url: str) -> list[ShopLoginCredential]:
    """程序启动时只从中控读取一次人工账号。"""
    response = requests.get(
        f"{base_url.rstrip('/')}/api/v1/cookies/",
        params={"platform": "pdd"},
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, list):
        raise ValueError("中控店铺 Cookie 接口响应中没有 data 列表")

    credentials: list[ShopLoginCredential] = []
    for shop in data:
        if not isinstance(shop, Mapping):
            continue
        shop_id = str(shop.get("shop_id") or "").strip()
        shop_name = str(shop.get("shop_name") or "").strip()
        accounts = shop.get("human_accounts")
        if not isinstance(accounts, list):
            continue
        for account in accounts:
            if not isinstance(account, Mapping):
                continue
            account_type_name = str(account.get("account_type_name") or "").strip()
            account_type = str(account.get("account_type") or "").strip().lower()
            if account_type_name != "人工账号" and account_type != "human":
                continue
            login_account = str(account.get("login_account") or "").strip()
            login_password = str(account.get("login_password") or "")
            if login_account and login_password:
                credentials.append(
                    ShopLoginCredential(
                        shop_id=shop_id,
                        shop_name=shop_name,
                        login_account=login_account,
                        login_password=login_password,
                    )
                )
    return credentials


def match_shop_login_credential(
    group_name: str,
    port: int,
    login_info_file: Path,
    credentials: Iterable[ShopLoginCredential],
) -> ShopLoginCredential | None:
    """使用归档店铺 ID 优先、名称兜底的方式匹配人工账号。"""
    record = find_shop_record(login_info_file, group_name, port)
    if not record:
        return None
    archived_id = str(record.get("shop_id") or "").strip()
    archived_name = str(record.get("shop_name") or "").strip()
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


def discover_groups(profile_root: Path) -> list[str]:
    """找出至少包含一个数字端口目录的 groupN 分组。"""
    try:
        entries = list(profile_root.iterdir())
    except OSError as exc:
        raise ConfigError(f"无法读取店铺根目录 {profile_root}：{exc}") from exc

    groups: list[tuple[int, str]] = []
    for entry in entries:
        match = re.fullmatch(r"group(\d+)", entry.name, re.IGNORECASE)
        if not match or not entry.is_dir():
            continue
        try:
            has_profile = any(child.is_dir() and child.name.isdigit() for child in entry.iterdir())
        except OSError:
            has_profile = False
        if has_profile:
            groups.append((int(match.group(1)), entry.name))
    return [name for _, name in sorted(groups)]


def prompt_group_selection() -> str | None:
    """读取启动时的分组选择，``None`` 表示按原逻辑处理全部分组。"""
    while True:
        try:
            raw_value = input("请输入分组编号（0=全部分组，其他正整数=仅处理对应 groupN）：").strip()
        except EOFError:
            print("未读取到分组编号，程序已退出。")
            return ""

        if not raw_value.isdigit():
            print("请输入 0 或正整数。")
            continue

        group_number = int(raw_value)
        if group_number == 0:
            return None
        return f"group{group_number}"


def discover_shop_profiles(group_name: str, profile_root: Path) -> list[tuple[int, Path]]:
    """返回一个分组内 ``(远程调试端口, user-data 目录)`` 的列表。"""
    group_path = profile_root / group_name
    try:
        entries = list(group_path.iterdir())
    except OSError as exc:
        print(f"{group_name}：无法读取分组目录：{exc}")
        return []

    profiles: list[tuple[int, Path]] = []
    for entry in entries:
        if not entry.is_dir() or not entry.name.isdigit():
            continue
        user_data_dir = entry / "user-data"
        if user_data_dir.is_dir():
            profiles.append((int(entry.name), user_data_dir))
        else:
            print(f"{group_name}：端口 {entry.name} 缺少 user-data，已跳过。")
    return sorted(profiles)


def find_edge_executable() -> Path | None:
    """定位可使用店铺 Chromium 配置的 Microsoft Edge。"""
    candidates = (
        Path.home() / "AppData/Local/Microsoft/Edge/Application/msedge.exe",
        Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
        Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    resolved = shutil.which("msedge.exe")
    return Path(resolved) if resolved else None


def browser_is_ready(port: int) -> bool:
    """检查店铺浏览器的远程调试端口是否已就绪。"""
    try:
        response = requests.get(f"http://127.0.0.1:{port}/json/version", timeout=1)
        return response.ok
    except requests.RequestException:
        return False


def _routine_window_position() -> tuple[int, int]:
    """返回日常 Cookie 窗口在主屏幕右上角的坐标。"""
    width, margin = 440, 8
    try:
        import ctypes

        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
    except Exception:
        screen_width = 1920
    return max(0, screen_width - width - margin), margin


def start_browser(
    browser_exe: Path,
    port: int,
    user_data_dir: Path,
    *,
    mode: BrowserMode,
) -> bool:
    """按指定可见性启动一个店铺浏览器。

    ``routine`` 用于平常 Cookie 获取：先请求最小化，若 Edge 忽略该请求则显示在
    右上角。只有 ``login`` 用于 Cookie 失效后的自动登录。
    """
    webview_data_dir = user_data_dir / "EBWebView"
    args = [
        str(browser_exe),
        f"--user-data-dir={webview_data_dir}",
        "--remote-allow-origins=http://127.0.0.1",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--noerrdialogs",
        "--disable-session-crashed-bubble",
        "--disable-notifications",
        "--disable-prompt-on-repost",
        "--disable-features=Translate,MediaRouter,OptimizationHints,msEdgeSidebarV2",
    ]
    if mode == "routine":
        x, y = _routine_window_position()
        # Edge 支持时会最小化；不支持时仍按指定尺寸出现在右上角。
        args.extend((
            "--start-minimized",
            "--window-size=440,340",
            f"--window-position={x},{y}",
        ))
    elif mode == "login":
        # 自动登录需要人工看到验证码、短信或扫码提示，因此不隐藏或缩小窗口。
        args.extend(("--window-size=1180,820", "--window-position=40,40"))
    else:
        raise ValueError(f"未知浏览器模式：{mode}")
    args.append(PDD_HOME_URL)
    try:
        subprocess.Popen(args, cwd=str(webview_data_dir))
    except OSError as exc:
        print(f"端口 {port}：浏览器启动失败：{exc}")
        return False
    return True


def open_store_browser(
    port: int,
    user_data_dir: Path,
    *,
    browser_exe: Path,
    startup_wait: int,
    mode: BrowserMode,
) -> Any | None:
    """连接店铺浏览器；端口未启动时以给定模式创建浏览器。"""
    from DrissionPage import ChromiumPage
    from DrissionPage._functions.settings import Settings

    Settings.set_auto_handle_alert(True)
    if not browser_is_ready(port):
        label = {"routine": "日常 Cookie", "login": "自动登录窗口"}[mode]
        print(f"端口 {port}：启动{label}浏览器。")
        if not start_browser(browser_exe, port, user_data_dir, mode=mode):
            return None
        deadline = time.monotonic() + startup_wait
        while time.monotonic() < deadline:
            if browser_is_ready(port):
                break
            time.sleep(1)
        else:
            print(f"端口 {port}：浏览器调试端口启动超时。")
            return None

    page: Any | None = None
    try:
        page = ChromiumPage(port)
        page.get(PDD_HOME_URL)
        return page
    except Exception as exc:
        if page is not None:
            close_store_browser(page)
        print(f"端口 {port}：无法连接店铺浏览器：{exc}")
        return None


def close_store_browser(page: Any | None) -> None:
    """关闭本次打开的完整浏览器，同时保留用户配置目录。"""
    if page is None:
        return
    try:
        page.quit(timeout=5, force=True, del_data=False)
    except Exception as exc:
        print(f"关闭店铺浏览器失败：{exc}")


def cookie_payload_from_page(page: Any) -> dict[str, str]:
    cookies = page.cookies().as_dict()
    cookie_text = page.cookies().as_str()
    if not cookie_text.strip():
        raise CookieExpiredError("浏览器没有返回 Cookie")
    return get_pdd_shop_info(cookies, cookie_text)


def _open_account_login_tab(page: Any) -> bool:
    script = """
        const candidates = [...document.querySelectorAll('button, a, div, span')];
        const tab = candidates.find((element) => {
          const text = (element.innerText || '').trim();
          return /^(账号登录|密码登录)$/.test(text);
        });
        if (tab) { tab.click(); return true; }
        return Boolean(document.querySelector('#usernameId, input[name="username"], input[type="password"]'));
    """
    try:
        return bool(page.run_js(script))
    except Exception:
        return False


def _fill_account_login(page: Any, login_account: str, login_password: str) -> bool:
    account_literal = json.dumps(login_account, ensure_ascii=False)
    password_literal = json.dumps(login_password, ensure_ascii=False)
    script = f"""
        const account = document.querySelector('#usernameId, input[name="username"], input[type="text"]');
        const password = document.querySelector('#passwordId, input[name="password"], input[type="password"]');
        if (!account || !password) return false;
        const setValue = (element, value) => {{
          const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
          setter.call(element, value);
          element.dispatchEvent(new Event('input', {{bubbles: true}}));
          element.dispatchEvent(new Event('change', {{bubbles: true}}));
        }};
        setValue(account, {account_literal});
        setValue(password, {password_literal});
        return true;
    """
    try:
        return bool(page.run_js(script))
    except Exception:
        return False


def _submit_login(page: Any) -> bool:
    script = """
        for (const selector of [
          'button[type="submit"]', 'input[type="submit"]', '[data-testid="login-submit"]'
        ]) {
          const element = document.querySelector(selector);
          if (element && !element.disabled) { element.click(); return true; }
        }
        const candidates = [...document.querySelectorAll('button, a, div[role="button"]')];
        const button = candidates.find((element) => /^(登录|立即登录)$/.test((element.innerText || '').trim()));
        if (button && !button.disabled) { button.click(); return true; }
        return false;
    """
    try:
        return bool(page.run_js(script))
    except Exception:
        return False


def attempt_account_password_login(
    page: Any, wait_seconds: int, credential: ShopLoginCredential | None
) -> bool:
    """用匹配的人工账号登录；验证码、短信与扫码保留给可见窗口处理。"""
    if credential is None:
        print("Cookie 无效：未匹配到该店铺的人工账号，无法自动登录。")
        return False
    print(f"Cookie 无效，正在使用店铺 {credential.shop_name} 的人工账号自动登录。")
    try:
        page.get(PDD_LOGIN_URL)
    except Exception as exc:
        print(f"无法打开拼多多登录页：{exc}")
        return False

    time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
    submitted = False
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        try:
            cookie_payload_from_page(page)
            return True
        except (CookieExpiredError, requests.RequestException, ValueError):
            pass

        if not submitted:
            if _open_account_login_tab(page):
                time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
            if _fill_account_login(page, credential.login_account, credential.login_password):
                submitted = _submit_login(page)
                if submitted:
                    print("已提交自动登录，等待会话生效。")
                    time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
        time.sleep(AUTO_LOGIN_STEP_WAIT_SECONDS)
    print("自动登录未获得有效 Cookie（可能需要扫码、短信或验证码）。")
    return False


def _read_cookie_without_login(
    port: int,
    user_data_dir: Path,
    *,
    browser_exe: Path,
    browser_wait: int,
) -> tuple[Any | None, dict[str, str] | None, bool]:
    """读取 Cookie，返回 ``(page, payload, 是否需显示登录窗口)``。"""
    page = open_store_browser(
        port,
        user_data_dir,
        browser_exe=browser_exe,
        startup_wait=browser_wait,
        mode="routine",
    )
    if page is None:
        return None, None, False
    try:
        return page, cookie_payload_from_page(page), False
    except CookieExpiredError:
        close_store_browser(page)
        return None, None, True
    except (requests.RequestException, ValueError) as exc:
        close_store_browser(page)
        print(f"端口 {port}：日常 Cookie 获取失败：{exc}")
        return None, None, False


def process_store(
    group_name: str,
    port: int,
    user_data_dir: Path,
    *,
    base_url: str,
    browser_exe: Path,
    browser_wait: int,
    login_wait: int,
    login_info_file: Path,
    login_credentials: Iterable[ShopLoginCredential],
) -> bool:
    """处理一个店铺，并在结束时关闭本次启动的浏览器。"""
    page: Any | None = None
    try:
        page, shop_info, needs_login = _read_cookie_without_login(
            port,
            user_data_dir,
            browser_exe=browser_exe,
            browser_wait=browser_wait,
        )
        if needs_login:
            # 此处是唯一会显示普通浏览器窗口的分支。
            print(f"端口 {port}：Cookie 已失效，打开可见窗口自动登录。")
            page = open_store_browser(
                port,
                user_data_dir,
                browser_exe=browser_exe,
                startup_wait=browser_wait,
                mode="login",
            )
            if page is None:
                report_auto_login_failure(base_url, port, group_name, login_info_file=login_info_file)
                return False
            credential = match_shop_login_credential(
                group_name, port, login_info_file, login_credentials
            )
            if not attempt_account_password_login(page, login_wait, credential):
                report_auto_login_failure(base_url, port, group_name, login_info_file=login_info_file)
                return False
            try:
                shop_info = cookie_payload_from_page(page)
            except (CookieExpiredError, requests.RequestException, ValueError) as exc:
                print(f"端口 {port}：自动登录后 Cookie 仍不可用：{exc}")
                report_auto_login_failure(base_url, port, group_name, login_info_file=login_info_file)
                return False

        if shop_info is None:
            report_auto_login_failure(base_url, port, group_name, login_info_file=login_info_file)
            return False
        try:
            result = upsert_cookie(base_url, shop_info)
        except (requests.RequestException, ValueError) as exc:
            print(f"{group_name} 端口 {port}：Cookie 上传失败：{exc}")
            return False
        action = "新增" if result.get("created") else "更新"
        print(f"{group_name} 端口 {port}：{action} {shop_info['shop_name']} Cookie 成功。")
        return True
    finally:
        close_store_browser(page)


def process_group(
    group_name: str,
    *,
    profile_root: Path,
    base_url: str,
    browser_exe: Path,
    browser_wait: int,
    login_wait: int,
    thread: int,
    login_info_file: Path,
    login_credentials: Iterable[ShopLoginCredential],
) -> tuple[int, int]:
    stores = discover_shop_profiles(group_name, profile_root)
    print(f"{group_name}：发现 {len(stores)} 个店铺。")
    if not stores:
        return 0, 0
    print(f"{group_name}：同时处理最多 {thread} 个店铺。")
    success = 0
    with ThreadPoolExecutor(max_workers=thread, thread_name_prefix="pdd-store") as executor:
        futures = {
            executor.submit(
                process_store,
                group_name,
                port,
                user_data_dir,
                base_url=base_url,
                browser_exe=browser_exe,
                browser_wait=browser_wait,
                login_wait=login_wait,
                login_info_file=login_info_file,
                login_credentials=login_credentials,
            ): port
            for port, user_data_dir in stores
        }
        for future in as_completed(futures):
            port = futures[future]
            try:
                success += int(future.result())
            except Exception as exc:
                print(f"{group_name} 端口 {port}：处理失败：{exc}")
    print(f"{group_name}：本次完成，成功 {success}/{len(stores)}。")
    return success, len(stores)


def cli(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="独立轮询拼多多分组并更新 Cookie")
    parser.add_argument("--profile-root", type=Path, default=DEFAULT_PROFILE_ROOT)
    parser.add_argument("--api-config", type=Path, default=DEFAULT_API_CONFIG_FILE)
    parser.add_argument("--api-base-url", help="临时覆盖 ipyuan.json 的中控地址")
    parser.add_argument("--login-info", type=Path, default=DEFAULT_LOGIN_INFO_FILE)
    parser.add_argument(
        "--edge", "--browser", dest="edge", type=Path,
        help="Microsoft Edge 路径（--browser 为兼容别名）",
    )
    parser.add_argument("--interval", type=int, help="相邻分组之间的等待秒数")
    parser.add_argument("--browser-wait", type=int, default=DEFAULT_BROWSER_WAIT_SECONDS)
    parser.add_argument("--login-wait", type=int, default=DEFAULT_LOGIN_WAIT_SECONDS)
    parser.add_argument("--once", action="store_true", help="只执行全部分组一轮后退出")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if min(args.browser_wait, args.login_wait) <= 0:
        parser.error("--browser-wait 和 --login-wait 必须是正整数")

    selected_group = prompt_group_selection()
    if selected_group == "":
        return 1

    try:
        config = load_server_config(args.api_config)
    except ConfigError as exc:
        print(f"启动失败：{exc}")
        return 1
    interval = args.interval if args.interval is not None else config.interval
    if interval <= 0:
        parser.error("--interval 必须是正整数")
    browser_exe = args.edge or find_edge_executable()
    if browser_exe is None or not browser_exe.is_file():
        print("启动失败：未找到 Microsoft Edge，请通过 --edge 指定路径。")
        return 1
    base_url = args.api_base_url or config.base_url

    try:
        login_credentials = fetch_shop_login_credentials(base_url)
        print(f"已读取中控人工账号：{len(login_credentials)} 个店铺。")
    except (requests.RequestException, ValueError) as exc:
        login_credentials = []
        print(f"读取中控人工账号失败：{exc}；需要登录的店铺将按失败上报。")

    try:
        groups = discover_groups(args.profile_root)
    except ConfigError as exc:
        print(f"启动失败：{exc}")
        return 1
    if not groups:
        print(f"未在 {args.profile_root} 找到有店铺的 groupN 分组。")
        return 1
    if selected_group is not None:
        groups = [group for group in groups if group.lower() == selected_group]
        if not groups:
            print(f"未在 {args.profile_root} 找到有店铺的 {selected_group} 分组。")
            return 1
        print(f"已选择 {groups[0]}，仅处理该分组。")

    try:
        while True:
            for index, group_name in enumerate(groups):
                process_group(
                    group_name,
                    profile_root=args.profile_root,
                    base_url=base_url,
                    browser_exe=browser_exe,
                    browser_wait=args.browser_wait,
                    login_wait=args.login_wait,
                    thread=config.thread,
                    login_info_file=args.login_info,
                    login_credentials=login_credentials,
                )
                if args.once:
                    continue
                if index < len(groups) - 1:
                    print(f"等待 {interval} 秒后处理下一分组。")
                    time.sleep(interval)
            if args.once:
                return 0
            print(f"本轮完成，等待 {interval} 秒后开始下一轮。")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("已停止独立 Cookie 更新器。")
        return 0


if __name__ == "__main__":
    raise SystemExit(cli())
