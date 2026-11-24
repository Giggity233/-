# 拼多多 Cookie 更新器（恢复源码）

运行环境：Python 3.10+、Microsoft Edge、`D:\aibot\ipyuan.json` 与店铺用户目录。

```powershell
py -3.10 -m pip install -r requirements.txt
py -3.10 pdd_group_cookie_runner.py --once
```

程序启动时会提示输入分组编号：输入 `0` 按原逻辑轮询全部非空分组；输入正整数（例如 `3`）则只处理 `group3`。

浏览器策略：平常 Cookie 同步使用普通 Edge，并请求最小化；若 Edge 忽略最小化请求，则以右上角 440×340 小窗口运行。Cookie 失效且需要自动登录时打开普通可见窗口。
