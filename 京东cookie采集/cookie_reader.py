"""读取 cookie 文件，返回 "name=value; name2=value2" 形式的字符串。

直接右键运行本文件即可，改下面的 COOKIE_PATH 就行。
"""

import base64
import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from ctypes import wintypes

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

COOKIE_PATH = r"C:\Users\Admin\AppData\Local\JDM\JMWorkStation\5ZC05ZC05ZC0X+Wwj+Wcow==\.cefcache"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes) -> bytes:
    """用当前 Windows 用户的 DPAPI 解密。"""
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
    """取出解密密钥：Chrome/Edge 在 Local State，CEF 应用（如京麦）在 LocalPrefs.json。"""
    local = os.environ.get("LOCALAPPDATA", "")
    paths = []
    cur = os.path.abspath(cookie_dir)
    while True:  # Cookies 一般在 ...\User Data\Default\Network\ 或 ...\.cefcache\Network\ 下
        paths += [
            os.path.join(cur, "Local State"),
            os.path.join(cur, "LocalPrefs.json"),
        ]
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    paths += [
        os.path.join(local, r"Google\Chrome\User Data\Local State"),
        os.path.join(local, r"Microsoft\Edge\User Data\Local State"),
    ]
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
        # 新版 Chrome 在明文前加了 32 字节 host 哈希
        if plain[:32] == hashlib.sha256(host.encode()).digest():
            plain = plain[32:]
        return plain.decode("utf-8", "ignore")
    return None


def _read_db(path: str, keys: list[bytes]) -> list[tuple[str, str, str]]:
    tmpdir = tempfile.mkdtemp()
    tmp = os.path.join(tmpdir, "Cookies")
    try:
        shutil.copy2(path, tmp)  # 复制一份，避免浏览器占用
    except OSError:
        tmp = path
    try:
        con = sqlite3.connect(tmp)
        rows = con.execute("SELECT host_key, name, value, encrypted_value FROM cookies").fetchall()
        con.close()
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    result = []
    for host, name, value, encrypted in rows:
        if not value and encrypted:
            value = _decrypt(encrypted, keys, host) or ""
        if name and value:
            result.append((host, name, value))
    return result


def _read_text(path: str) -> list[tuple[str, str, str]]:
    """兼容 cookies.txt / JSON / "a=1; b=2" 纯文本。"""
    with open(path, encoding="utf-8-sig", errors="ignore") as f:
        text = f.read()
    if text.lstrip().startswith(("[", "{")):
        data = json.loads(text)
        if isinstance(data, dict):
            return [("", str(k), str(v)) for k, v in data.items()]
        return [(d.get("domain", ""), d["name"], str(d.get("value", ""))) for d in data if d.get("name")]
    pairs = []
    for line in text.splitlines():
        if "\t" in line:  # Netscape 格式：domain flag path secure expire name value
            parts = line.split("\t")
            if len(parts) >= 7 and not line.startswith("#"):
                pairs.append((parts[0], parts[5], parts[6]))
        elif "=" in line and not line.startswith("#"):
            name, _, value = line.partition("=")
            pairs.append(("", name.strip(), value.strip()))
    return pairs


def get_cookie(path: str, domain: str | None = None) -> str:
    """读取 path（文件或目录）里的 cookie 文件，返回 cookie 字符串。

    domain: 只保留指定域名（如 "jd.com"），None 表示全部
    """
    files = [path] if os.path.isfile(path) else [
        os.path.join(root, name)
        for root, _dirs, names in os.walk(path)
        for name in names
        if name.lower() in ("cookies", "cookies.sqlite", "cookies.db")
        or ("cookie" in name.lower() and os.path.splitext(name.lower())[1] in (".txt", ".json", ".cookie"))
    ]

    cookies: dict[str, str] = {}
    for file in files:
        try:
            with open(file, "rb") as f:
                is_db = f.read(16) == b"SQLite format 3\x00"
        except OSError:
            continue
        try:
            items = _read_db(file, _keys(os.path.dirname(file))) if is_db else _read_text(file)
        except Exception as exc:
            print(f"跳过 {file}: {exc}")
            continue
        for host, name, value in items:
            if domain and domain.lower() not in host.lower():
                continue
            cookies[name] = value  # 同名覆盖
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


if __name__ == "__main__":
    print(
        get_cookie(COOKIE_PATH)
        or "没有读到 cookie：该 Cookies 库的密文无法用本机密钥解开，"
        "通常是文件来自其它电脑 / 其它 Windows 用户（DPAPI 密钥不随文件走）"
    )
