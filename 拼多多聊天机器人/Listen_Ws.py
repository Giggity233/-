# -*- coding: utf-8 -*-
"""
Listen_Ws.py —— WebSocket 监听模块（与原版一致，未做改动）
----------------------------------------------------------
作用：通过 CDP（Chrome DevTools Protocol）挂到已经打开的拼多多商家聊天页上，
     监听页面自身的 WebSocket 帧，把原始帧丢进队列供上层解码。

要点：
    1. 不主动请求任何业务接口，只被动接收页面 WS 推送；
    2. Network.enable 后注册两个回调：
         - Network.webSocketFrameReceived（收到帧）
         - Network.webSocketClosed（连接断开）
    3. 三层保活：30 秒心跳 × 3 无消息 / 收到 Closed / 主动 stop，都会触发重连；
    4. 重连方式：刷新页面 -> 等 10 秒 -> 重建 Driver -> 40 秒内收到消息即视为成功。
"""
import asyncio
import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from DrissionPage._base.driver import Driver


class AsyncListenWs:
    _SENTINEL = object()
    _RECONNECT_SENTINEL = object()

    def __init__(self, page):
        self.page = page
        self.driver = None
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="WSListen")
        self.raw_q = queue.Queue(maxsize=5000)
        self._listening = False
        self._lock = threading.Lock()
        self._reconnecting = False
        self._last_message_time = time.time()
        self._heartbeat_interval = 30
        self._max_reconnect_delay = 60

    @property
    def listening(self):
        with self._lock:
            return self._listening

    def _set_listening(self, v: bool):
        with self._lock:
            self._listening = v

    def _set_reconnecting(self, v: bool):
        with self._lock:
            self._reconnecting = v

    @property
    def reconnecting(self):
        with self._lock:
            return self._reconnecting

    async def _init_driver(self):
        loop = asyncio.get_running_loop()
        if self.driver:
            try:
                await loop.run_in_executor(self.executor, self.driver.stop)
            except Exception:
                pass
            self.driver = None

        # DrissionPage 4.1.x 的 Driver 签名是 (tab_id, tab_type, address)。
        # address 应为浏览器调试地址，tab_type 固定传 page。
        tab_id = self.page.tab_id
        address = self.page.browser.address
        self.driver = await loop.run_in_executor(
            self.executor,
            lambda: Driver(tab_id, 'page', address)
        )
        await loop.run_in_executor(self.executor, lambda: self.driver.run("Network.enable"))
        await loop.run_in_executor(self.executor, self._register_callbacks)

    async def start(self):
        if self.listening:
            return
        await self._init_driver()
        self._last_message_time = time.time()
        self._set_listening(True)

    async def stop(self):
        self._set_listening(False)
        self._set_reconnecting(False)
        try:
            self.raw_q.put_nowait(self._SENTINEL)
        except Exception:
            pass
        loop = asyncio.get_running_loop()
        if self.driver:
            try:
                await loop.run_in_executor(self.executor, self.driver.stop)
            except Exception:
                pass
            self.driver = None

    async def close(self):
        try:
            await self.stop()
        finally:
            try:
                self.executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def _register_callbacks(self):
        self.driver.set_callback("Network.webSocketFrameReceived", self._on_ws_frame)
        self.driver.set_callback("Network.webSocketClosed", self._on_ws_closed)

    def _on_ws_frame(self, **kwargs):
        self._last_message_time = time.time()
        try:
            self.raw_q.put(kwargs["response"])
        except Exception:
            pass

    def _on_ws_closed(self, **kwargs):
        with self._lock:
            if self._listening and not self._reconnecting:
                self._reconnecting = True
                try:
                    self.raw_q.put_nowait(self._RECONNECT_SENTINEL)
                except Exception:
                    pass

    async def _heartbeat_check(self):
        while self.listening:
            await asyncio.sleep(self._heartbeat_interval)
            with self._lock:
                if self._listening and (time.time() - self._last_message_time > self._heartbeat_interval * 3):
                    if not self._reconnecting:
                        self._reconnecting = True
                        try:
                            self.raw_q.put_nowait(self._RECONNECT_SENTINEL)
                        except Exception:
                            pass

    async def _reconnect(self):
        delay = 10
        max_delay = self._max_reconnect_delay
        print(f"WebSocket开始重连")

        while self.reconnecting:
            self._last_message_time = 0
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(self.executor, self.page.refresh)
                print(f"页面刷新完成，等待WebSocket连接建立...")
                await asyncio.sleep(10)
                await self._init_driver()
                print(f"驱动重新初始化完成，等待消息...")

                timeout = 40
                elapsed = 0
                while elapsed < timeout:
                    if self._last_message_time > 0 and time.time() - self._last_message_time < 10:
                        print(f"WebSocket重连成功！")
                        self._set_reconnecting(False)
                        self._last_message_time = time.time()
                        return True
                    await asyncio.sleep(1)
                    elapsed += 1

                raise Exception(f"等待{timeout}秒后仍未收到消息")

            except Exception as e:
                print(f"WebSocket重连失败: {e}")
                print(f"等待{delay}秒后重试...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, max_delay)

        return False

    async def receive_messages(self):
        heartbeat_task = asyncio.create_task(self._heartbeat_check())

        while True:
            item = await asyncio.to_thread(self.raw_q.get)

            if item is self._SENTINEL:
                heartbeat_task.cancel()
                break

            if item is self._RECONNECT_SENTINEL:
                await self._reconnect()
                continue

            yield item
