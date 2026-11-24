import asyncio
import unittest
from typing import Any, Mapping

from jd_chat_history import JdChatHistory, format_chat_history
from jd_message_listener import ReceivedMessage


def make_message() -> ReceivedMessage:
    return ReceivedMessage(
        session_id="buyer:im.customer:shop",
        buyer_id="buyer",
        vender_id="shop",
        content="current message",
        message_type="text",
        packet={
            "id": "current-id",
            "mid": 30,
            "type": "chat_message",
            "timestamp": 30,
            "from": {"app": "im.customer", "pin": "buyer"},
            "body": {"type": "text", "content": "current message"},
        },
    )


class JdChatHistoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_pull_result_is_correlated_and_formatted(self) -> None:
        sent_packets: list[Mapping[str, Any]] = []

        async def send_packet(packet: Mapping[str, Any]) -> None:
            sent_packets.append(packet)

        history = JdChatHistory(send_packet, waiter_pin="waiter", aid="aid")
        message = make_message()
        task = asyncio.create_task(history.get_history(message))
        for _ in range(10):
            if sent_packets:
                break
            await asyncio.sleep(0)
        self.assertEqual(len(sent_packets), 1)
        request = sent_packets[0]
        self.assertEqual(request["type"], "pull")
        self.assertEqual(request["body"], {
            "sessionGroup": 1,
            "showRP": True,
            "count": 20,
            "sessionId": "buyer:im.customer:shop",
            "startMid": 30,
        })

        handled = history.handle_packet({
            "id": request["id"],
            "type": "pull_result",
            "body": {
                "sessionId": "buyer:im.customer:shop",
                "msgs": [
                    {
                        "id": "customer-1",
                        "mid": 1,
                        "timestamp": 1,
                        "type": "chat_message",
                        "from": {"app": "im.customer", "pin": "buyer"},
                        "body": {"type": "text", "content": "hello"},
                    },
                    {
                        "id": "waiter-2",
                        "mid": 2,
                        "timestamp": 2,
                        "type": "chat_message",
                        "from": {"app": "im.waiter", "pin": "waiter"},
                        "body": {"type": "image", "url": "https://example.test/image.jpg"},
                    },
                    message.packet,
                ],
            },
        })

        self.assertTrue(handled)
        self.assertEqual(
            await task,
            "【买家】：hello\n【客服】：[图片]https://example.test/image.jpg",
        )

    def test_history_formatter_ignores_duplicate_and_current_messages(self) -> None:
        message = make_message()
        result = format_chat_history(
            [
                {
                    "id": "one",
                    "mid": 1,
                    "type": "chat_message",
                    "from": {"app": "im.customer", "pin": "buyer"},
                    "body": {"type": "text", "content": "first"},
                },
                {
                    "id": "one",
                    "mid": 1,
                    "type": "chat_message",
                    "from": {"app": "im.customer", "pin": "buyer"},
                    "body": {"type": "text", "content": "duplicate"},
                },
                message.packet,
            ],
            message,
            "waiter",
        )
        self.assertEqual(result, "【买家】：duplicate")
