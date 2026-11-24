"""蘑菇头中控平台配置。

生产环境通过环境变量配置 MySQL；仅在本地验收时设置 USE_SQLITE=1。
"""
from pathlib import Path
import os
import secrets
import sys

BASE_DIR = Path(__file__).resolve().parent.parent


def load_server_env():
    """Load a simple KEY=VALUE file next to the packaged executable.

    System environment variables have priority, so a deployment platform can
    still inject secrets without placing them in a file.
    """
    config_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else BASE_DIR
    config_file = config_dir / "server.env"
    if not config_file.is_file():
        return
    for raw_line in config_file.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            os.environ.setdefault(key, value.strip())


load_server_env()


def get_secret_key():
    configured_key = os.getenv("DJANGO_SECRET_KEY")
    if configured_key:
        return configured_key
    if getattr(sys, "frozen", False):
        key_file = Path(sys.executable).resolve().parent / "server.secret"
        if key_file.is_file():
            return key_file.read_text(encoding="utf-8").strip()
        generated_key = secrets.token_urlsafe(50)
        try:
            key_file.write_text(generated_key, encoding="utf-8")
            return generated_key
        except OSError:
            # The server can still start when its installation folder is
            # read-only, though a configured DJANGO_SECRET_KEY is preferable.
            return "change-this-in-production-lianzun"
    return "change-this-in-production-lianzun"


SECRET_KEY = get_secret_key()
# 默认关闭调试页，避免向用户展示 Django 的 “Page not found”。本地排错时可设为 1。
DEBUG = os.getenv("DJANGO_DEBUG", "0") == "1"
ALLOWED_HOSTS = [item.strip() for item in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if item.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.CoreConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "lianzun.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "lianzun.wsgi.application"
ASGI_APPLICATION = "lianzun.asgi.application"

if os.getenv("USE_SQLITE", "0") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
else:
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "lianzun"),
        "USER": os.getenv("MYSQL_USER", "root"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "123456"),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "core.User"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "login"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
