"""读取当前 Windows 用户的抖店工作台 Cookie。

Cookie 数据保存在 Chromium/Electron 的 Network/Cookies SQLite 数据库中，
值使用当前 Windows 用户的 DPAPI 密钥或 AES-GCM 加密。因此必须在登录抖店
工作台的同一个 Windows 用户下运行本脚本。

依赖：python -m pip install cryptography
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from ctypes import wintypes
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


APP_DIR_NAME = "抖店工作台"
ALT_APP_DIR_NAMES = ("抖店工作台", "飞鸽客服工作台")
PORTABLE_DIR_NAME = "抖店"
DEFAULT_APP_DIR = Path(os.environ.get("APPDATA", "")) / APP_DIR_NAME
FXG_HOST = "fxg.jinritemai.com"
COOKIE_COLUMNS = (
    "host_key, name, path, encrypted_value, value, "
    "expires_utc, is_secure, is_httponly"
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = (
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    )


def dpapi_decrypt(ciphertext: bytes) -> bytes:
    """Use the current Windows logon user's DPAPI key to decrypt bytes."""
    if not ciphertext:
        return b""

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptUnprotectData.argtypes = (
        ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB),
    )
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    input_buffer = ctypes.create_string_buffer(ciphertext)
    input_blob = DATA_BLOB(
        len(ciphertext),
        ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_char)),
    )
    output_blob = DATA_BLOB()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        error = ctypes.get_last_error()
        raise OSError(error, "CryptUnprotectData failed")

    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(output_blob.pbData)


def _load_master_key_from_local_state(local_state: Path) -> bytes:
    data = json.loads(local_state.read_text(encoding="utf-8"))
    encoded_key = data.get("os_crypt", {}).get("encrypted_key")
    if not encoded_key:
        raise RuntimeError(f"未在 {local_state} 找到 os_crypt.encrypted_key")

    protected_key = base64.b64decode(encoded_key)
    if not protected_key.startswith(b"DPAPI"):
        raise RuntimeError("该版本使用了应用绑定加密，无法用当前脚本导出")

    return dpapi_decrypt(protected_key[5:])


def load_master_keys(app_dir: Path) -> list[bytes]:
    local_states = find_local_state_paths(app_dir)
    if not local_states:
        raise FileNotFoundError("未找到 Local State，请确认程序同级目录或 C 盘默认目录包含该文件")

    keys: list[bytes] = []
    last_exc: Exception | None = None
    for local_state in local_states:
        try:
            keys.append(_load_master_key_from_local_state(local_state))
        except Exception as exc:
            last_exc = exc

    if keys:
        return keys
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("未找到可用 Local State 解密密钥")


def load_master_key(app_dir: Path) -> bytes:
    return load_master_keys(app_dir)[0]


def decrypt_cookie(
    encrypted_value: bytes,
    plaintext_value: str,
    host: str,
    master_key: bytes,
) -> str:
    """Decrypt old DPAPI cookies and Chromium v10/v11/v20 AES-GCM cookies."""
    if plaintext_value:
        return plaintext_value
    if not encrypted_value:
        return ""

    if encrypted_value[:3] in (b"v10", b"v11", b"v20"):
        try:
            value = AESGCM(master_key).decrypt(
                encrypted_value[3:15],
                encrypted_value[15:],
                None,
            )
        except Exception as exc:
            raise RuntimeError(f"AES-GCM 解密失败：{exc}") from exc

        host_digest = hashlib.sha256(host.encode("utf-8")).digest()
        if value.startswith(host_digest):
            value = value[len(host_digest) :]
        return value.decode("utf-8", errors="replace")

    return dpapi_decrypt(encrypted_value).decode("utf-8", errors="replace")


def decrypt_cookie_with_master_keys(
    encrypted_value: bytes,
    plaintext_value: str,
    host: str,
    master_keys: list[bytes],
) -> str:
    if plaintext_value:
        return plaintext_value
    if not encrypted_value:
        return ""

    if encrypted_value[:3] not in (b"v10", b"v11", b"v20"):
        return decrypt_cookie(encrypted_value, plaintext_value, host, b"")

    last_exc: Exception | None = None
    for master_key in master_keys:
        try:
            return decrypt_cookie(encrypted_value, plaintext_value, host, master_key)
        except Exception as exc:
            last_exc = exc

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("未找到可用 Local State 解密密钥")


def snapshot_rows(cookie_db: Path) -> list[tuple]:
    """Read a consistent temporary SQLite backup without changing the live DB."""
    uri = f"file:{cookie_db.as_posix()}?mode=ro"
    source = sqlite3.connect(uri, uri=True)
    try:
        with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tmp:
            snapshot_name = tmp.name

        try:
            destination = sqlite3.connect(snapshot_name)
            try:
                source.backup(destination)
            finally:
                destination.close()

            snapshot = sqlite3.connect(snapshot_name)
            try:
                return snapshot.execute(f"SELECT {COOKIE_COLUMNS} FROM cookies").fetchall()
            finally:
                snapshot.close()
        finally:
            Path(snapshot_name).unlink(missing_ok=True)
    finally:
        source.close()


def is_cookie_for(host: str, target_host: str) -> bool:
    cookie_domain = host.lstrip(".").lower()
    target_host = target_host.lower()
    return target_host == cookie_domain or target_host.endswith("." + cookie_domain)


def discover_cookie_dbs(app_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for base in _cookie_candidate_dirs(app_dir):
        if not _has_cookie_dbs(base):
            continue
        try:
            paths.extend(
                path
                for path in base.rglob("Cookies")
                if path.is_file() and path.parent.name == "Network"
            )
        except OSError:
            continue
    return sorted(_dedupe_paths(paths))


def cookie_db_partition(cookie_db: Path, app_dir: Path | None = None) -> str:
    for base in _cookie_candidate_dirs(app_dir):
        try:
            return str(cookie_db.parent.parent.relative_to(base))
        except ValueError:
            continue
    return str(cookie_db.parent.parent)


def cookie_db_data_dir(cookie_db: Path, app_dir: Path | None = None) -> Path:
    """Return the data directory that contains a Cookie database."""
    for base in _cookie_candidate_dirs(app_dir):
        try:
            cookie_db.parent.parent.relative_to(base)
            return base
        except ValueError:
            continue
    return cookie_db.parent.parent


def _has_cookie_dbs(path: Path) -> bool:
    if (path / "Network" / "Cookies").is_file():
        return True
    try:
        return any(path.glob("Partitions/*/Network/Cookies"))
    except OSError:
        return False


def _is_data_dir(path: Path) -> bool:
    """A usable data/cache dir has cookies, Local State, or saved shop metadata."""
    return path.is_dir() and (
        (path / "Local State").is_file()
        or _has_cookie_dbs(path)
        or (path / "config.json").is_file()
        or (path / "cache.json").is_file()
    )


def _cookie_db_mtime(app_dir: Path) -> float:
    """Newest modification time of the directory's cookie databases."""
    candidates = [app_dir / "Network" / "Cookies"]
    candidates.extend(app_dir.glob("Partitions/*/Network/Cookies"))
    mtimes = [path.stat().st_mtime for path in candidates if path.is_file()]
    return max(mtimes, default=0.0)


def _known_roaming_app_dirs() -> list[Path]:
    """Known APPDATA product dirs that may hold config.json or live cookies."""
    candidates: list[Path] = []

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        roaming = Path(appdata)
        candidates.extend(roaming / name for name in ALT_APP_DIR_NAMES)

    users_root = Path(os.environ.get("SystemDrive", "C:") + "\\Users")
    try:
        profiles = [path for path in users_root.iterdir() if path.is_dir()] if users_root.is_dir() else []
    except OSError:
        profiles = []

    for profile in profiles:
        roaming = profile / "AppData" / "Roaming"
        candidates.extend(roaming / name for name in ALT_APP_DIR_NAMES)

    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            key = str(candidate.expanduser().resolve()).lower()
        except OSError:
            key = str(candidate).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)

    return result


def _dedupe_paths(candidates) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            path = Path(candidate).expanduser()
            key = str(path.resolve()).lower()
        except OSError:
            path = Path(candidate)
            key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def is_plausible_shop_id(value: object) -> bool:
    """Return whether a value looks like a real Douyin shop ID.

    Cached Electron state also contains short random/session strings.  Those
    values must never be sent to the shop API as ``shop_id``.
    """
    text = str(value or "").strip()
    return bool(text) and text.isdigit() and text != "0"


def _metadata_candidate_dirs(app_dir: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    # Account metadata normally lives in the Windows roaming profile.  Put
    # those locations first, while still merging portable/same-level copies.
    candidates.extend(_known_roaming_app_dirs())
    candidates.append(DEFAULT_APP_DIR)
    try:
        candidates.extend(_own_dirs())
    except Exception:
        pass
    if app_dir is not None:
        candidates.append(app_dir)
    return _dedupe_paths(candidates)


def _cookie_candidate_dirs(app_dir: Path | None = None) -> list[Path]:
    candidates: list[Path] = []
    try:
        candidates.extend(_own_dirs())
    except Exception:
        pass
    if app_dir is not None:
        candidates.append(app_dir)
    try:
        candidates.extend(_running_data_dirs())
    except Exception:
        pass
    candidates.extend(_known_roaming_app_dirs())
    candidates.append(DEFAULT_APP_DIR)
    return _dedupe_paths(candidates)


def _running_data_dirs() -> list[Path]:
    """Infer user-data dirs from running doudian.exe / 抖店工作台.exe."""
    TH32CS_SNAPPROCESS = 2
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    DRIVE_FIXED = 3

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = (
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", ctypes.c_long),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateToolhelp32Snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(PROCESSENTRY32W),
    )
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = (
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    )
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.GetLogicalDrives.restype = wintypes.DWORD
    kernel32.GetDriveTypeW.argtypes = (wintypes.LPCWSTR,)
    kernel32.GetDriveTypeW.restype = wintypes.UINT

    exe_paths: list[str] = []
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        try:
            ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
            while ok:
                if entry.szExeFile.lower() in {
                    "doudian.exe",
                    f"{APP_DIR_NAME}.exe",
                    "飞鸽客服工作台.exe",
                }:
                    handle = kernel32.OpenProcess(
                        PROCESS_QUERY_LIMITED_INFORMATION,
                        False,
                        entry.th32ProcessID,
                    )
                    if handle:
                        buffer = ctypes.create_unicode_buffer(32768)
                        size = wintypes.DWORD(32768)
                        if kernel32.QueryFullProcessImageNameW(
                            handle,
                            0,
                            buffer,
                            ctypes.byref(size),
                        ):
                            exe_paths.append(buffer.value)
                        kernel32.CloseHandle(handle)
                ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        finally:
            kernel32.CloseHandle(snapshot)

    data_dirs: list[Path] = []
    for exe_path in exe_paths:
        path = Path(exe_path)
        if path.name.lower() == "doudian.exe" and len(path.parents) >= 3:
            data_dirs.append(path.parents[2])
            continue
        data_dirs.append(path.parent)

    bitmask = kernel32.GetLogicalDrives()
    for index in range(26):
        if not ((bitmask >> index) & 1):
            continue
        root = Path(f"{chr(ord('A') + index)}:\\")
        if kernel32.GetDriveTypeW(str(root)) != DRIVE_FIXED:
            continue
        portable_dir = root / PORTABLE_DIR_NAME
        if portable_dir.is_dir():
            data_dirs.append(portable_dir)

    return data_dirs


def _own_dirs() -> list[Path]:
    """Directory of the running exe/script and a few parents above it.

    The program is commonly copied directly into the portable data folder
    (e.g. D:\\抖店\\doudian_cookie_sync.exe); its own directory then *is* the
    user-data directory.
    """
    if getattr(sys, "frozen", False):
        start = Path(sys.executable)
    else:
        start = Path(__file__).resolve()

    dirs: list[Path] = []
    current = start.parent
    for _ in range(4):
        dirs.append(current)
        parent = current.parent
        if parent == current:
            return dirs
        current = parent
    return dirs


def resolve_app_dir(explicit: Path | str | None) -> Path:
    """Locate the live user-data directory.

    1.1.9 keeps cookies together with config.json under
    %APPDATA%\\抖店工作台. The 1.1.11 portable install writes Local State and
    Cookies under <drive>\\抖店 (e.g. D:\\抖店) while config.json stays in
    APPDATA. When no directory is given explicitly, prefer the valid
    candidate whose cookie databases were modified most recently, so stale
    leftover directories are never picked by mistake.
    """
    if explicit is not None:
        return Path(explicit).expanduser().resolve()

    candidates: list[Path] = []
    try:
        candidates.extend(_own_dirs())
    except Exception:
        pass

    try:
        candidates.extend(_running_data_dirs())
    except Exception:
        pass

    candidates.extend(_known_roaming_app_dirs())
    candidates.append(DEFAULT_APP_DIR)

    valid: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve()
        except OSError:
            continue

        key = str(resolved).lower()
        if key in seen or not _is_data_dir(resolved):
            continue
        seen.add(key)
        valid.append(resolved)

    if not valid:
        return DEFAULT_APP_DIR.expanduser().resolve()
    cookie_valid = [path for path in valid if _has_cookie_dbs(path)]
    if cookie_valid:
        return max(cookie_valid, key=_cookie_db_mtime)
    return max(valid, key=_cookie_db_mtime)


def find_local_state_paths(app_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for directory in _metadata_candidate_dirs(app_dir):
        candidate = directory / "Local State"
        try:
            if candidate.is_file():
                paths.append(candidate)
        except OSError:
            continue
    return _dedupe_paths(paths)


def find_local_state_path(app_dir: Path) -> Path | None:
    paths = find_local_state_paths(app_dir)
    return paths[0] if paths else None


def find_config_paths(app_dir: Path) -> list[Path]:
    """Find every config.json in the default and portable locations."""
    paths: list[Path] = []
    for directory in _metadata_candidate_dirs(app_dir):
        candidate = directory / "config.json"
        try:
            if candidate.is_file():
                paths.append(candidate)
        except OSError:
            continue
    return _dedupe_paths(paths)


def find_config_path(app_dir: Path) -> Path | None:
    """Find config.json in the data dir, falling back to the APPDATA copy.

    1.1.11 stores the account list in APPDATA even though the cookie
    databases may live in a portable data directory. Some installs use
    飞鸽客服工作台 instead of 抖店工作台.
    """
    paths = find_config_paths(app_dir)
    return paths[0] if paths else None


def find_cache_paths(app_dir: Path) -> list[Path]:
    """Find every cache.json in the default and portable locations."""
    paths: list[Path] = []
    for directory in _metadata_candidate_dirs(app_dir):
        candidate = directory / "cache.json"
        try:
            if candidate.is_file():
                paths.append(candidate)
        except OSError:
            continue
    return _dedupe_paths(paths)


def find_cache_path(app_dir: Path) -> Path | None:
    paths = find_cache_paths(app_dir)
    return paths[0] if paths else None


def _shop_records_from_cache(cache: dict) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    def walk(node, account_id: str = "", depth: int = 0) -> None:
        if depth > 10:
            return
        if isinstance(node, dict):
            # Do not treat sec_shop_id or arbitrary cache keys as a shop ID:
            # Electron cache entries can contain random values such as
            # ``muthcYBe`` which are not accepted by the backend.
            shop_id = node.get("shopId") or node.get("shop_id")
            name = (
                node.get("shopName")
                or node.get("shop_name")
                or node.get("main_shop_name")
                or node.get("name")
            )
            if is_plausible_shop_id(shop_id):
                records.append(
                    {
                        "account_id": account_id,
                        "shop_id": str(shop_id).strip(),
                        "name": str(name or ""),
                    }
                )
            for key, value in node.items():
                next_account_id = account_id
                if isinstance(key, str) and key.startswith("persist:"):
                    next_account_id = key.split(":", 1)[1]
                walk(value, next_account_id, depth + 1)
        elif isinstance(node, list):
            for item in node:
                walk(item, account_id, depth + 1)

    walk(cache)

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        key = (record["shop_id"], record["account_id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def load_shop_info(app_dir: Path) -> dict[str, dict[str, str]]:
    """Read saved shop names and account partition IDs from config.json."""
    records: list[dict[str, str]] = []

    for config_path in find_config_paths(app_dir):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            records.extend(_account_records(config))
        except (OSError, json.JSONDecodeError):
            continue

    for cache_path in find_cache_paths(app_dir):
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            records.extend(_shop_records_from_cache(cache))
        except (OSError, json.JSONDecodeError):
            continue

    result: dict[str, dict[str, str]] = {}
    for record in records:
        shop_id = str(record.get("shop_id") or "").strip()
        if not is_plausible_shop_id(shop_id):
            continue
        current = result.setdefault(
            shop_id,
            {"name": "", "account_id": ""},
        )
        if not current["name"] and record.get("name"):
            current["name"] = str(record["name"])
        if not current["account_id"] and record.get("account_id"):
            current["account_id"] = str(record["account_id"])
    return result


def load_accounts(app_dir: Path) -> list[dict[str, str]]:
    """Return every saved login account as one record.

    Several staff accounts can be logged into the same shop, so the result is
    a list keyed by account/partition rather than a dict keyed by shop ID.
    Each record: {"account_id", "shop_id", "name"}.
    """
    records: list[dict[str, str]] = []
    for config_path in find_config_paths(app_dir):
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
            records.extend(_account_records(config))
        except (OSError, json.JSONDecodeError):
            continue

    for cache_path in find_cache_paths(app_dir):
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            records.extend(_shop_records_from_cache(cache))
        except (OSError, json.JSONDecodeError):
            continue

    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        shop_id = str(record.get("shop_id") or "").strip()
        account_id = str(record.get("account_id") or "").strip()
        if not is_plausible_shop_id(shop_id):
            continue
        key = (shop_id, account_id)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "account_id": account_id,
                "shop_id": shop_id,
                "name": str(record.get("name") or ""),
            }
        )
    return result


def _account_records(config: dict) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    accounts = config.get("model__AccountModel", {}).get("accountList", [])
    for account in accounts:
        meta = account.get("meta") or {}
        shop_id = meta.get("shopId")
        records.append(
            {
                "account_id": str(account.get("id") or ""),
                "shop_id": "" if shop_id is None else str(shop_id),
                "name": str(meta.get("shopName") or meta.get("name") or ""),
            }
        )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="打印抖店工作台指定店铺的 fxg.jinritemai.com Cookie"
    )
    parser.add_argument(
        "--app-dir",
        type=Path,
        default=None,
        help=(
            "抖店工作台数据目录；不指定时自动探测正在使用的目录"
            "（1.1.11 便携版一般在安装盘根目录，如 D:\\抖店）"
        ),
    )
    parser.add_argument("--shop-id", help="只输出指定店铺 ID 的 Cookie，例如 29411390")
    parser.add_argument("--shop-name", help="按 config.json 中保存的店铺名称筛选")
    parser.add_argument(
        "--list-shops",
        action="store_true",
        help="列出本机保存的店铺 ID、名称和分区",
    )
    parser.add_argument(
        "--all-domains",
        action="store_true",
        help="输出匹配分区内所有域名的 Cookie，而不只输出抖店域名 Cookie",
    )
    parser.add_argument(
        "--names-only",
        action="store_true",
        help="只打印 Cookie 名称，不打印敏感值",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_dir = resolve_app_dir(args.app_dir)
    if not app_dir.is_dir():
        print(f"未找到抖店工作台数据目录：{app_dir}", file=sys.stderr)
        return 1

    print(f"使用数据目录：{app_dir}")
    config_path = find_config_path(app_dir)
    if config_path is not None and config_path.parent != app_dir:
        print(f"使用账号配置：{config_path}")

    accounts = load_accounts(app_dir)
    if args.list_shops:
        if not accounts:
            print("config.json 中没有找到账号列表。", file=sys.stderr)
            return 1

        print(f"本机保存的登录账号（共 {len(accounts)} 个）：")
        for record in accounts:
            account_id = record.get("account_id") or "未知分区"
            name = record.get("name") or "未命名店铺"
            shop_id = record.get("shop_id") or "未知店铺ID"
            print(f"  {shop_id}\t{name}\t分区: Partitions\\{account_id}")

        distinct = len({r["shop_id"] for r in accounts if r["shop_id"]})
        if distinct != len(accounts):
            print(f"（其中 {distinct} 个不同店铺，存在同店铺多客服账号登录）")
        return 0

    shop_info = load_shop_info(app_dir)
    target_shop_id = str(args.shop_id).strip() if args.shop_id else ""
    if args.shop_name:
        matched = [
            shop_id
            for shop_id, info in shop_info.items()
            if info.get("name") == args.shop_name
        ]
        if not matched:
            print(f"config.json 中没有找到店铺名称：{args.shop_name}", file=sys.stderr)
            return 1
        if target_shop_id and target_shop_id not in matched:
            print("--shop-id 与 --shop-name 指向不同店铺。", file=sys.stderr)
            return 1
        target_shop_id = matched[0]

    try:
        master_keys = load_master_keys(app_dir)
    except Exception as exc:
        print(f"读取 Windows 解密密钥失败：{exc}", file=sys.stderr)
        return 1

    databases = discover_cookie_dbs(app_dir)
    if not databases:
        print("未找到 Network\\Cookies 数据库。", file=sys.stderr)
        return 1

    total = 0
    for cookie_db in databases:
        partition = cookie_db.parent.parent.relative_to(app_dir)
        try:
            rows = snapshot_rows(cookie_db)
        except Exception as exc:
            print(f"\n[{partition}] 读取失败：{exc}", file=sys.stderr)
            continue

        decoded = []
        for (
            host,
            name,
            path,
            encrypted,
            plain,
            expires,
            secure,
            httponly,
        ) in rows:
            if not args.all_domains and not is_cookie_for(host, FXG_HOST):
                continue

            try:
                value = decrypt_cookie_with_master_keys(
                    encrypted or b"",
                    plain or "",
                    host,
                    master_keys,
                )
            except Exception as exc:
                print(f"[{partition}] {host} / {name} 解密失败：{exc}", file=sys.stderr)
                continue

            decoded.append(
                (host, name, path, value, expires, bool(secure), bool(httponly))
            )

        if not decoded:
            continue

        shop_ids = [
            value
            for _host, name, _path, value, *_ in decoded
            if name in {"SHOP_ID", "ecom_gray_shop_id"}
        ]
        if target_shop_id and target_shop_id not in shop_ids:
            continue

        total += 1
        print("\n========================================================================================")
        print(f"数据分区: {partition}")
        print(
            "店铺标识: "
            + (", ".join(shop_ids) if shop_ids else "未找到 SHOP_ID / ecom_gray_shop_id")
        )
        if target_shop_id:
            name = shop_info.get(target_shop_id, {}).get("name") or "未在 config.json 中命名"
            print(f"筛选店铺: {target_shop_id} ({name})")

        print(f"用于 https://{FXG_HOST} 的 Cookie:")
        for host, name, _path, value, _expires, _secure, _httponly in decoded:
            shown_value = "<隐藏>" if args.names_only else value
            print(f"  {host}\t{name} = {shown_value}")

        if args.all_domains or args.names_only:
            continue

        header = "; ".join(f"{name}={value}" for _host, name, _path, value, *_ in decoded)
        print("\nCookie 请求头（可直接复制）：")
        print(header)

    if not total:
        if target_shop_id:
            print(f"没有找到店铺 {target_shop_id} 的可用 Cookie。")
        else:
            print(f"没有找到适用于 {FXG_HOST} 的 Cookie。")
        return 1

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImportError:
        print("缺少依赖，请先执行：python -m pip install cryptography", file=sys.stderr)
        raise
