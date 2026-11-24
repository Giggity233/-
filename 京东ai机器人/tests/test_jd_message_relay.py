import asyncio
import json
import unittest

from jd_message_listener import ReceivedMessage
from jd_message_relay import JdMessageRelay
from jd_message_sender import JdMessageSender


def make_message(identifier: str, content: str) -> ReceivedMessage:
    return ReceivedMessage(
        session_id="buyer:im.customer:shop",
        buyer_id="buyer",
        vender_id="shop",
        content=content,
        message_type="text",
        packet={
            "id": identifier,
            "mid": 1,
            "datetime": 1,
            "from": {"app": "im.customer", "pin": "buyer"},
            "body": {"mid": 1},
        },
    )


class JdMessageRelayTests(unittest.IsolatedAsyncioTestCase):
    async def test_does_not_pass_jd_emoticon_codes_to_reply_handler(self) -> None:
        received_payloads: list[dict] = []
        handled = asyncio.Event()

        async def write_packet(_payload: str) -> None:
            return None

        async def reply_handler(payload: dict) -> str:
            received_payloads.append(payload)
            handled.set()
            return ""

        relay = JdMessageRelay(
            JdMessageSender(write_packet, waiter_pin="waiter", aid="aid", art="art"),
            reply_handler,
            wait_seconds=0.01,
        )
        await relay.receive(make_message("message-1", "hello#E-s49"))
        await asyncio.wait_for(handled.wait(), timeout=1)

        self.assertEqual(received_payloads[0]["input"], "hello[微笑]")
        await relay.close()

    async def test_combines_messages_received_in_the_fixed_window(self) -> None:
        sent_packets: list[dict] = []
        received_payloads: list[dict] = []
        handled = asyncio.Event()

        async def write_packet(payload: str) -> None:
            sent_packets.append(json.loads(payload))

        async def reply_handler(payload: dict) -> str:
            received_payloads.append(payload)
            handled.set()
            return "received"

        async def chat_history_provider(_message: ReceivedMessage) -> str:
            return "【买家】：earlier question"

        sender = JdMessageSender(write_packet, waiter_pin="waiter", aid="aid", art="art")
        relay = JdMessageRelay(
            sender,
            reply_handler,
            wait_seconds=0.03,
            cookie_provider=lambda: "pt_key=test;pt_pin=buyer;",
            reply_context_provider=lambda: {
                "waiter_pin": "waiter",
                "username": "waiter",
                "aid": "aid",
            },
            chat_history_provider=chat_history_provider,
        )

        await relay.receive(make_message("message-1", "first"))
        await asyncio.sleep(0.01)
        await relay.receive(make_message("message-2", "second"))
        await asyncio.wait_for(handled.wait(), timeout=1)

        replies = [
            packet for packet in sent_packets if packet["type"] == "chat_message"
        ]
        self.assertEqual(len(received_payloads), 1)
        payload = received_payloads[0]
        self.assertEqual(payload["input"], "first\nsecond")
        self.assertEqual(payload["chathistory"], "【买家】：earlier question")
        self.assertEqual(payload["cookie"], "pt_key=test;pt_pin=buyer;")
        self.assertEqual(payload["username"], "waiter")
        self.assertEqual(payload["buyer_name"], "buyer")
        self.assertEqual(payload["shopid"], "shop")
        self.assertEqual(payload["waiter_pin"], "waiter")
        self.assertEqual(payload["aid"], "aid")
        self.assertEqual(
            set(payload),
            {
                "aid",
                "buyer_name",
                "chathistory",
                "cookie",
                "input",
                "shopid",
                "username",
                "waiter_pin",
            },
        )
        self.assertEqual(len(replies), 1)
        self.assertEqual(replies[0]["body"]["content"], "received")
        await relay.close()
