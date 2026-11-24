// 读取标准输入中的 {"frame":"base64..."}，使用 ws_accept.js 解码并输出 JSON。
// ws_accept.js 来自原项目的协议解码器；本文件不包含 Cookie，也不发送任何消息。
const fs = require("fs");
const path = require("path");

const decoderPath = path.join(__dirname, "ws_accept.js");
const decoderCode = fs.readFileSync(decoderPath, "utf8");
// ws_accept.js 定义了 receiveRaw(hex)。在当前模块作用域执行可保留它对 require 的访问。
eval(decoderCode);

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  try {
    const { frame } = JSON.parse(input);
    if (typeof frame !== "string") {
      throw new TypeError("frame 必须是 base64 字符串");
    }
    const hex = Buffer.from(frame, "base64").toString("hex");
    process.stdout.write(JSON.stringify(receiveRaw(hex)));
  } catch (error) {
    process.stderr.write(`${error.stack || error.message}\n`);
    process.exitCode = 1;
  }
});
