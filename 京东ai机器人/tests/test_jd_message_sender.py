import json
import unittest

from jd_message_listener import ReceivedMessage
from jd_message_sender import JdMessageSender


def make_message() -> ReceivedMessage:
    return ReceivedMessage(
        session_id="buyer:im.customer:shop",
        buyer_id="buyer",
        vender_id="shop",
        content="",
        message_type="text",
        packet={},
    )


class JdMessageSenderTests(unittest.IsolatedAsyncioTestCase):
    async def test_sends_image_packet(self) -> None:
        packets: list[dict] = []

        async def write_packet(payload: str) -> None:
            packets.append(json.loads(payload))

        sender = JdMessageSender(write_packet, waiter_pin="waiter", aid="aid")
        await sender.send_image(
            make_message(),
            url="https://example.com/image.jpg",
            width=640,
            height=480,
        )

        body = packets[0]["body"]
        self.assertEqual(packets[0]["type"], "chat_message")
        self.assertEqual(body["type"], "image")
        self.assertEqual(body["url"], "https://example.com/image.jpg")
        self.assertEqual(body["width"], 640)
        self.assertEqual(body["height"], 480)
        self.assertEqual(body["param"], {"cusVenderId": "shop"})

    async def test_sends_video_packet(self) -> None:
        packets: list[dict] = []

        async def write_packet(payload: str) -> None:
            packets.append(json.loads(payload))

        sender = JdMessageSender(write_packet, waiter_pin="waiter", aid="aid")
        await sender.send_video(
            make_message(),
            url="https://example.com/video.mp4",
            size=1234,
            duration=8,
            thumbnail="https://example.com/cover.jpg",
            thumb_width=320,
            thumb_height=180,
        )

        body = packets[0]["body"]
        self.assertEqual(body["type"], "video")
        self.assertEqual(body["url"], "https://example.com/video.mp4")
        self.assertEqual(body["thumbnail"], "https://example.com/cover.jpg")
        self.assertEqual(body["size"], 1234)
        self.assertEqual(body["duration"], 8)
        self.assertEqual(body["thumbWidth"], 320)
        self.assertEqual(body["thumbHeight"], 180)
