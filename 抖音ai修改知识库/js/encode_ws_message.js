// 读取发送所需 JSON，用 ws_send.js 编码为 WebSocket 二进制帧并以 base64 JSON 输出。
// 本文件不保存 Cookie，也不建立网络连接。
const fs = require("fs");
const path = require("path");

const encoderPath = path.join(__dirname, "ws_send.js");
const encoderCode = fs.readFileSync(encoderPath, "utf8");
// ws_send.js 定义了 sendByWs(...)，需要在当前模块作用域执行以使用 require。
eval(encoderCode);

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  try {
    const { request, token, pigeon_sign, pigeon_cid, app_id } = JSON.parse(input);
    const frame = sendByWs(request, token, pigeon_sign, pigeon_cid, String(app_id));
    process.stdout.write(JSON.stringify({ frame: Buffer.from(frame).toString("base64") }));
  } catch (error) {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  }
});
