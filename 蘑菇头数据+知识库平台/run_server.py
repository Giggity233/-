"""Windows server entry point for the packaged application.

It starts a production WSGI server, applies migrations and creates the initial
administrator when the account does not yet exist.  Command-line options take
priority over values in ``server.env``.
"""
from __future__ import annotations

import argparse
import os


def ensure_initial_admin(reset_password: bool) -> None:
    """Create the requested administrator without overwriting later changes."""
    from core.models import User

    username = os.getenv("INITIAL_ADMIN_USERNAME", "guangon1")
    password = os.getenv("INITIAL_ADMIN_PASSWORD", "heyiwei111")
    responsible_name = os.getenv("INITIAL_ADMIN_RESPONSIBLE_NAME", "平台管理员")
    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "responsible_name": responsible_name,
            "is_active": True,
            "is_staff": True,
            "is_superuser": True,
        },
    )

    changed = False
    for field, value in {
        "responsible_name": user.responsible_name or responsible_name,
        "is_active": True,
        "is_staff": True,
        "is_superuser": True,
    }.items():
        if getattr(user, field) != value:
            setattr(user, field, value)
            changed = True
    if created or reset_password:
        user.set_password(password)
        changed = True
    if changed:
        user.save()

    if created:
        print(f"已创建初始管理员：{username}")
    elif reset_password:
        print(f"已重置管理员密码：{username}")


def main() -> None:
    parser = argparse.ArgumentParser(description="蘑菇头中控平台服务端")
    parser.add_argument("--host", help="监听地址，例如 0.0.0.0")
    parser.add_argument("--port", type=int, help="监听端口，例如 8000")
    parser.add_argument(
        "--reset-admin-password",
        action="store_true",
        help="将初始管理员密码重置为 server.env 中的 INITIAL_ADMIN_PASSWORD",
    )
    parser.add_argument("--no-migrate", action="store_true", help="跳过数据库迁移")
    args = parser.parse_args()

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lianzun.settings")
    import django

    django.setup()

    if not args.no_migrate:
        from django.core.management import call_command

        print("正在检查数据库结构…")
        call_command("migrate", interactive=False, verbosity=1)

    ensure_initial_admin(args.reset_admin_password)

    host = args.host or os.getenv("SERVER_HOST", "0.0.0.0")
    port = args.port or int(os.getenv("SERVER_PORT", "8000"))
    threads = int(os.getenv("SERVER_THREADS", "8"))

    from lianzun.wsgi import application
    from waitress import serve

    print(f"蘑菇头中控平台已启动：http://{host}:{port}")
    print("按 Ctrl+C 可停止服务。")
    serve(application, host=host, port=port, threads=threads)


if __name__ == "__main__":
    main()
