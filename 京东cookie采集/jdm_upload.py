"""扫描京麦工作台各账号的 Cookies，查询店名/类目后上传到蘑菇头中控平台。

把本文件放到 C:\\Users\\Admin\\AppData\\Local\\JDM\\JMWorkStation 下运行（右键运行即可），
脚本会自动遍历每个账号目录下的 .cefcache\\Network\\Cookies。
"""

import base64
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from ctypes import wintypes

import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

BASE_URL = "http://117.72.204.36:8000"          # 蘑菇头中控平台地址
PLATFORM = "jingdong"
SHOP_ID_FORMAT = "{venderId}"                # 店铺 ID 只用 venderId，不加平台前缀
INTERVAL_MINUTES = 30                        # 每轮上传的间隔（分钟）

# 京东“店铺星级”接口（取 shopName / scndCategoryName）
JD_API_URL = "https://sff.jd.com/api"
JD_PARAMS = {
    "v": "1.0",
    "appId": "P9Q5MDPM2DHRJOCY4UDL",        # 固定
    "api": "dsm.shop.vane.view.core.export.ohs.stars.service.VaneStarsFacade",
}
JD_DATA = {"vaneStarsParam": {}, "callerParam": {}}
JD_HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "dsm-language": "zh_CN",
    "dsm-platform": "pc",
    "origin": "https://shop.jd.com",
    "referer": "https://shop.jd.com/jdm/home",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
    ),
    "x-referer-page": "https://shop.jd.com/jdm/home",
    "x-requested-with": "XMLHttpRequest",
    "x-rp-client": "h5_2.4.0",
}


# --------------------------------------------------------------------------- #
# cookie 读取（CEF/Chrome v10 解密）
# --------------------------------------------------------------------------- #
class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes) -> bytes:
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    dst = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)
    ):
        raise OSError("DPAPI 解密失败")
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(dst.pbData)


def _keys(cookie_dir: str) -> list[bytes]:
    """密钥：CEF 在 LocalPrefs.json，Chrome/Edge 在 Local State。"""
    paths = []
    cur = os.path.abspath(cookie_dir)
    while True:
        paths += [os.path.join(cur, "LocalPrefs.json"), os.path.join(cur, "Local State")]
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    keys = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as f:
                enc = base64.b64decode(json.load(f)["os_crypt"]["encrypted_key"])
            key = _dpapi(enc[5:])  # 去掉 "DPAPI" 前缀
        except Exception:
            continue
        if len(key) in (16, 32) and key not in keys:
            keys.append(key)
    return keys


def _decrypt(encrypted: bytes, keys: list[bytes], host: str) -> str | None:
    body = encrypted[3:]  # 去掉 v10/v11 前缀
    for key in keys:
        try:  # 新版 AES-GCM：12 字节 nonce + 密文 + 16 字节 tag
            plain = AESGCM(key).decrypt(body[:12], body[12:], None)
        except Exception:
            try:  # 旧版 AES-CBC：16 字节 IV + 密文
                dec = Cipher(algorithms.AES(key), modes.CBC(body[:16])).decryptor()
                plain = dec.update(body[16:]) + dec.finalize()
                plain = plain[:-plain[-1]] if 1 <= plain[-1] <= 16 else plain
            except Exception:
                continue
        if plain[:32] == hashlib.sha256(host.encode()).digest():
            plain = plain[32:]  # 新版在明文前加了 host 哈希
        return plain.decode("utf-8", "ignore")
    return None


def read_cookie(db_path: str) -> str:
    """读取 Cookies 库，返回 "name=value; ..." 字符串。"""
    tmpdir = tempfile.mkdtemp()
    tmp = os.path.join(tmpdir, "Cookies")
    try:
        shutil.copy2(db_path, tmp)  # 应用占用时先复制
    except OSError:
        tmp = db_path
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute(
            "SELECT host_key, name, value, encrypted_value FROM cookies"
        ).fetchall()
        con.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    keys = _keys(os.path.dirname(db_path))
    cookies: dict[str, str] = {}
    for host, name, value, encrypted in rows:
        if not value and encrypted:
            value = _decrypt(encrypted, keys, host) or ""
        if name and value:
            cookies[name] = value
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


# --------------------------------------------------------------------------- #
# 京东接口：查店名 / 类目
# --------------------------------------------------------------------------- #
def jd_shop_info(cookie: str) -> dict | None:
    """成功返回 {"venderId","shopName","scndCategoryName"}，失败返回 None。"""
    jar = {}
    for pair in cookie.split(";"):
        name, _, value = pair.strip().partition("=")
        if name:
            jar[name] = value
    try:
        resp = requests.post(
            JD_API_URL, headers=JD_HEADERS, cookies=jar, params=JD_PARAMS,
            json=JD_DATA, timeout=20,
        )
        body = resp.json()
        print(body)
    except Exception as exc:
        print(f"    京东接口请求失败: {exc}")
        return None
    if body.get("code") != 200:
        print(f"    京东接口返回异常: code={body.get('code')} msg={body.get('msg')}")
        return None
    data = body.get("data") or {}
    if not data.get("shopName"):
        print("    京东接口未返回店名，跳过")
        return None
    return {
        "venderId": data.get("venderId", ""),
        "shopName": data["shopName"],
        "scndCategoryName": data.get("scndCategoryName", ""),
    }


def upload(shop_id: str, shop_name: str, category: str, cookie: str) -> bool:
    payload = {
        "platform": PLATFORM,
        "shop_id": shop_id,
        "shop_name": shop_name,
        "cookie": cookie,
        "main_category": category or "notfind",
    }
    try:
        resp = requests.post(
            f"{BASE_URL}/api/v1/cookies/upsert/", json=payload, timeout=15
        )
        body = resp.json()
    except Exception as exc:
        print(f"    上传失败: {exc}")
        return False
    if body.get("ok"):
        print("    上传成功")
        return True
    print(f"    上传失败: {body.get('message')}")
    return False


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def find_cookie_db(account_dir: str) -> str | None:
    for root, _dirs, files in os.walk(account_dir):
        if os.path.basename(root).lower() == "network" and "Cookies" in files:
            return os.path.join(root, "Cookies")
    return None


def _base_dir() -> str:
    """打包成 exe 后取 exe 所在目录，源码运行取脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    base_dir = _base_dir()

    accounts = []
    with os.scandir(base_dir) as it:
        for entry in it:
            # 只查文件夹，不是文件夹的（.py/.txt/.exe 等）一律不查
            if not entry.is_dir():
                continue
            # 排除脚本自身产生的缓存目录和隐藏目录
            if entry.name == "__pycache__" or entry.name.startswith("."):
                continue
            accounts.append(entry.name)
    accounts.sort()

    if not accounts:
        print(f"{base_dir} 下没有账号目录，请把脚本放到 JMWorkStation 目录里运行")
        return

    ok = failed = 0
    for account in accounts:
        print(f"[{account}]")
        db = find_cookie_db(os.path.join(base_dir, account))
        if not db:
            print("    没找到 .cefcache\\Network\\Cookies，跳过")
            failed += 1
            continue
        try:
            cookie = read_cookie(db)
        except Exception as exc:
            print(f"    读取 cookie 失败: {exc}")
            failed += 1
            continue
        if not cookie:
            print("    cookie 为空（可能未登录），跳过")
            failed += 1
            continue

        info = jd_shop_info(cookie)
        if not info:  # 接口没成功就不上传
            failed += 1
            continue

        shop_id = SHOP_ID_FORMAT.format(platform=PLATFORM, venderId=info["venderId"])
        print(f"    {info['shopName']}（{info['scndCategoryName']}）-> {shop_id}")
        if upload(shop_id, info["shopName"], info["scndCategoryName"], cookie):
            ok += 1
        else:
            failed += 1

    print(f"\n完成：成功 {ok} 个，失败 {failed} 个")


if __name__ == "__main__":
    try:
        while True:
            print(f"\n===== {time.strftime('%Y-%m-%d %H:%M:%S')} 开始上传 =====")
            try:
                main()
            except Exception as exc:  # 单轮出错不影响下一轮
                print(f"本轮出错: {exc}")
            print(f"===== 本轮结束，{INTERVAL_MINUTES} 分钟后再次上传（Ctrl+C 退出） =====")
            time.sleep(INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        print("\n已退出")