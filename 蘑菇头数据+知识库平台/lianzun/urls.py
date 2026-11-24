from django.contrib import admin
from django.contrib.staticfiles.views import serve as serve_static
from django.urls import include, path, re_path

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("", include("core.urls")),
    # 本机 runserver 在 DEBUG=False 时也能加载项目中的 CSS、图片等静态资源。
    re_path(r"^static/(?P<path>.*)$", serve_static, {"insecure": True}),
]

handler404 = "core.views.page_not_found"
