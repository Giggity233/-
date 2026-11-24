# 抖店自动回复中控

## 启动

```powershell
pip install -r requirements.txt
python main.py
```

Coze Token 会自动从 `data/COZE_TOKEN.txt` 读取；文件中只放 Token 本身即可。若该文件不存在，才会回退读取环境变量 `COZE_TOKEN`。

启动后先在黑框输入工作流序号；选项来自 `data/workflowid.json` 的键名。随后会打开 tkinter 中控：选择人工 `account_name`，点击“列出店铺”，再逐店启动或关闭机器人。

每次打开中控都会从以下接口读取最新抖音店铺、Cookie 与人工账号：

`http://117.72.204.36:8000/api/v1/cookies/?platform=douyin`

没有 `human_accounts[0].account_id`、没有 Cookie 或 Cookie 状态非 `valid` 的店铺不能启动。

勾选“协同回复”后，中控会改读独立的机器人 Cookie 接口：

`http://117.72.204.36:8000/api/v1/robot-cookies/?platform=douyin`

协同回复需先选择客户；中控会以该客户 ID 读取店铺的机器人 Cookie。此模式不需要人工账号，也不会查询或调用转人工。Coze 返回内容含“转人工”时，机器人保持静默，不发送消息。

## 回复规则

- 同一会话从第一句开始固定拼接 8 秒；窗口内的新消息只追加，不重置计时。每个拼接完成的批次都会创建并释放一个独立处理线程。
- Coze 返回必须是 `{"output": "..."}`。
- `output` 含“转人工”、没有 `@@@@`、`@@@@` 后为空，或 Coze 调用/解析失败时，使用首个人工账号 ID 调用转人工。
- 含 `@@@@` 时，仅发送第一个 `@@@@` 后面的文字。
- 发送失败只记录日志，不转人工。
- 协同回复下，Coze 调用/解析异常、返回“转人工”、缺少 `@@@@` 或 `@@@@` 后为空时，均不发送消息也不转人工。

## 日志

收到的拼接对话、Coze 返回、发送结果与转人工结果都会以绿色打印在黑框，并写入：

`log/<店铺名>/自动回复对话.log`

tkinter 窗口不显示运行日志。
