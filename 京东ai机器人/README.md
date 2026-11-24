# 京东机器人

## 批量控制店铺

1. 中控平台按接口文档保存京东机器人 Cookie，平台参数使用 `jingdong`。
2. 如缺少依赖，在 PyCharm Terminal 执行：`pip install -r requirements.txt`。
3. 首次运行前，将与 `D:\pythonProject\抖音机器人9527` 相同的 Coze Token 写入 `data/COZE_TOKEN.txt`（或设置环境变量 `COZE_TOKEN`）。`data/COZE_TOKEN.example.txt` 仅作说明，不要把真实 Token 提交到代码库。
4. 右键运行 `main.py`；先在控制台选择 `data/workflowid.json` 中的 Coze 工作流，再打开操作页。页面只列出有京东机器人 Cookie 店铺的客户。
5. 点击“加载店铺”，程序会读取 `GET /api/v1/robot-cookies/?platform=jingdong&customer_id=...`。
6. 每家店铺右侧都有“启动/停止”按钮；也可勾选多家后批量启动或停止。

`main.py` 顶部可修改中控接口地址和平台值。页面首次读取店铺时，会从中控 `/cookies/` 接口取得每家店铺 `human_accounts` 的第一条账号；该数据按店铺缓存，单独启动、停止或转人工都不会再次读取。连接成功后，命令行会显示当前店铺可转接的人工账号名称和 ID。每家店铺使用其独立机器人 Cookie 建立一个 WebSocket，Cookie 不显示在界面或日志中；Cookie 无效时该店铺会自动停止并显示原因。每家店铺会在 `logs/<店铺ID_店铺名>/` 下建立 `chat.log`、`runtime.log` 与 `error.log`；连接、重连、收发消息、聊天记录和转人工都使用 Loguru 记录，完整聊天记录仅写入文件、不输出命令行。

## 回复函数参数与媒体回复

`jd_reply_handler.py` 向 Coze 只传这八个参数：`aid`、`buyer_name`（对方买家）、`chathistory`、`cookie`、`input`（8 秒拼接文本）、`shopid`、`username`（当前登录客服）和 `waiter_pin`（当前回复账号）。本地机器人不会请求订单、商品详情或商品浏览足迹接口。不要打印或上传 `cookie`。

返回普通文本会发送文本；返回 `[图片]::::图片公网URL` 会发送图片；返回 `[视频]::::视频公网URL@@@封面公网URL` 会发送视频。图片和视频发送前会校验公网地址并探测所需元数据。

这是独立的京东消息监听与回复模块。它需要接入一个已经完成京东鉴权的 WebSocket 对象。

## 行为

- 只接收发给当前客服账号的买家文本、图片、视频和语音消息。
- 每条有效买家消息会立即打印，并发送 `msg_receive_ack`。
- 同一会话从第一句话到达时开始固定等待 8 秒，期间消息以换行拼接。
- 八秒到期后调用 Coze 工作流；只会发送 JSON `output` 中第一个 `@@@@` 后的文字。
- `@@@@` 后出现“人工”、没有 `@@@@`、内容为空或 Coze 异常时，机器人不再回复文字，而是使用当前店铺 `human_accounts` 中第一个人工账号的 ID 执行转人工；失败按 5、10、20 秒重试。
- 每个会话独立聚合；上一批回复耗时不会延后下一批的计时。

## 接入

```python
from jd_robot import JdCustomerRobot

robot = JdCustomerRobot(
    websocket,
    waiter_pin="当前客服账号",
    aid="京东 aid",
    art="京东 art",
    fallback_vender_id="店铺 ID",
)
await robot.run()
```

如需改写回复逻辑，请保持 `jd_reply_handler.py` 的异步处理约定，并返回 `ReplyAction(text="...")` 或 `ReplyAction.transfer("原因")`。
