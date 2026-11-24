"""京东图片、视频回复指令解析及受限元数据探测。"""

from __future__ import annotations

import ipaddress
import os
import socket
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlsplit

import requests


IMAGE_DIRECTIVE_PREFIX = "[图片]::::"
VIDEO_DIRECTIVE_PREFIX = "[视频]::::"
VIDEO_DIRECTIVE_SEPARATOR = "@@@"
MAX_REDIRECTS = 5
DOWNLOAD_CHUNK_SIZE = 64 * 1024
MEDIA_HEADERS = {
    "Accept": "*/*",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
}


class MediaProbeError(RuntimeError):
    """媒体指令或媒体资源不符合发送要求。"""


@dataclass(frozen=True)
class ImageDirective:
    image_url: str


@dataclass(frozen=True)
class VideoDirective:
    video_url: str
    thumbnail_url: str


@dataclass(frozen=True)
class ImageMetadata:
    width: int
    height: int


@dataclass(frozen=True)
class VideoMetadata:
    size: int
    duration: int
    thumb_width: int
    thumb_height: int


def parse_image_directive(reply: str) -> Optional[ImageDirective]:
    normalized = reply.strip()
    if not normalized.startswith(IMAGE_DIRECTIVE_PREFIX):
        return None
    image_url = normalized[len(IMAGE_DIRECTIVE_PREFIX) :].strip()
    _validate_url(image_url, "图片")
    return ImageDirective(image_url=image_url)


def parse_video_directive(reply: str) -> Optional[VideoDirective]:
    normalized = reply.strip()
    if not normalized.startswith(VIDEO_DIRECTIVE_PREFIX):
        return None
    content = normalized[len(VIDEO_DIRECTIVE_PREFIX) :]
    if content.count(VIDEO_DIRECTIVE_SEPARATOR) != 1:
        raise MediaProbeError("视频指令必须包含一个 @@@ 分隔符")
    video_url, thumbnail_url = (
        item.strip() for item in content.split(VIDEO_DIRECTIVE_SEPARATOR, 1)
    )
    _validate_url(video_url, "视频")
    _validate_url(thumbnail_url, "视频封面")
    return VideoDirective(video_url=video_url, thumbnail_url=thumbnail_url)


def probe_image_metadata(
    directive: ImageDirective,
    *,
    timeout_seconds: float = 30.0,
    max_bytes: int = 10 * 1024 * 1024,
) -> ImageMetadata:
    image_bytes = _download_bytes(
        directive.image_url,
        timeout_seconds=timeout_seconds,
        max_bytes=max_bytes,
    )
    width, height = _image_dimensions(image_bytes, "图片")
    return ImageMetadata(width=width, height=height)


def probe_video_metadata(
    directive: VideoDirective,
    *,
    timeout_seconds: float = 30.0,
    video_max_bytes: int = 100 * 1024 * 1024,
    thumbnail_max_bytes: int = 10 * 1024 * 1024,
) -> VideoMetadata:
    video_path: Path | None = None
    try:
        video_path, size = _download_file(
            directive.video_url,
            timeout_seconds=timeout_seconds,
            max_bytes=video_max_bytes,
        )
        duration = _video_duration(video_path)
        thumbnail = _download_bytes(
            directive.thumbnail_url,
            timeout_seconds=timeout_seconds,
            max_bytes=thumbnail_max_bytes,
        )
        thumb_width, thumb_height = _image_dimensions(thumbnail, "视频封面")
        return VideoMetadata(
            size=size,
            duration=duration,
            thumb_width=thumb_width,
            thumb_height=thumb_height,
        )
    finally:
        if video_path is not None:
            try:
                os.unlink(video_path)
            except FileNotFoundError:
                pass


def _download_bytes(url: str, *, timeout_seconds: float, max_bytes: int) -> bytes:
    with requests.Session() as session:
        session.headers.update(MEDIA_HEADERS)
        response = _public_response(session, url, timeout_seconds)
        try:
            return _read_limited(response, max_bytes)
        finally:
            response.close()


def _download_file(url: str, *, timeout_seconds: float, max_bytes: int) -> tuple[Path, int]:
    with requests.Session() as session:
        session.headers.update(MEDIA_HEADERS)
        response = _public_response(session, url, timeout_seconds)
        temporary = tempfile.NamedTemporaryFile(prefix="jd-video-", suffix=".tmp", delete=False)
        path = Path(temporary.name)
        total = 0
        try:
            expected_size = _content_length(response)
            if expected_size is not None and expected_size > max_bytes:
                raise MediaProbeError("视频文件超过大小限制")
            with temporary:
                for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        raise MediaProbeError("视频文件超过大小限制")
                    temporary.write(chunk)
            if not total:
                raise MediaProbeError("视频文件为空")
            return path, total
        except Exception:
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
            raise
        finally:
            response.close()


def _public_response(
    session: requests.Session,
    url: str,
    timeout_seconds: float,
) -> requests.Response:
    current_url = url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_public_url(current_url)
        response = session.get(
            current_url,
            allow_redirects=False,
            stream=True,
            timeout=(timeout_seconds, timeout_seconds),
        )
        if response.is_redirect or response.is_permanent_redirect:
            location = response.headers.get("Location")
            response.close()
            if not location:
                raise MediaProbeError("媒体重定向缺少地址")
            current_url = urljoin(current_url, location)
            continue
        response.raise_for_status()
        return response
    raise MediaProbeError("媒体重定向次数过多")


def _read_limited(response: requests.Response, max_bytes: int) -> bytes:
    expected_size = _content_length(response)
    if expected_size is not None and expected_size > max_bytes:
        raise MediaProbeError("媒体文件超过大小限制")
    data = bytearray()
    for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
        if not chunk:
            continue
        data.extend(chunk)
        if len(data) > max_bytes:
            raise MediaProbeError("媒体文件超过大小限制")
    if not data:
        raise MediaProbeError("媒体文件为空")
    return bytes(data)


def _content_length(response: requests.Response) -> int | None:
    value = response.headers.get("Content-Length")
    if not value:
        return None
    try:
        result = int(value)
    except ValueError:
        return None
    return result if result >= 0 else None


def _image_dimensions(data: bytes, resource_name: str) -> tuple[int, int]:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as error:
        raise MediaProbeError("缺少 Pillow，无法发送{}".format(resource_name)) from error
    try:
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
    except (UnidentifiedImageError, OSError) as error:
        raise MediaProbeError("{}不是有效图片".format(resource_name)) from error
    if width <= 0 or height <= 0:
        raise MediaProbeError("{}尺寸无效".format(resource_name))
    return int(width), int(height)


def _video_duration(path: Path) -> int:
    try:
        import cv2
    except ImportError as error:
        raise MediaProbeError("缺少 opencv-python-headless，无法读取视频时长") from error
    capture = cv2.VideoCapture(str(path))
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    finally:
        capture.release()
    if fps <= 0 or frames < 0:
        raise MediaProbeError("无法读取视频时长")
    return max(0, int(round(frames / fps)))


def _validate_url(url: str, resource_name: str) -> None:
    if not url or any(character.isspace() for character in url):
        raise MediaProbeError("{} URL 不能为空或包含空白字符".format(resource_name))
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError as error:
        raise MediaProbeError("{} URL 格式错误".format(resource_name)) from error
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise MediaProbeError("{} URL 必须是 HTTP(S) 地址".format(resource_name))
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise MediaProbeError("{} URL 不合法".format(resource_name))
    if port is not None and not 1 <= port <= 65535:
        raise MediaProbeError("{} URL 端口无效".format(resource_name))


def _validate_public_url(url: str) -> None:
    _validate_url(url, "媒体")
    parsed = urlsplit(url)
    hostname = parsed.hostname
    if hostname is None or hostname.lower() == "localhost" or hostname.lower().endswith(".localhost"):
        raise MediaProbeError("媒体 URL 不允许访问本机")
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addresses = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as error:
        raise MediaProbeError("媒体 URL 域名解析失败") from error
    if not addresses:
        raise MediaProbeError("媒体 URL 未解析到地址")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise MediaProbeError("媒体 URL 不允许访问非公网地址")
