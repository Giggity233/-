import unittest

from jd_message_listener import parse_customer_message


class JdMessageListenerTests(unittest.TestCase):
    def test_replaces_jd_emoticon_code_when_parsing_customer_message(self) -> None:
        packet = {
            "type": "chat_message",
            "from": {"app": "im.customer", "pin": "buyer"},
            "to": {"pin": "waiter"},
            "body": {
                "type": "text",
                "content": "hello#E-s49",
                "param": {"venderId": "shop"},
            },
        }

        message = parse_customer_message(packet, waiter_pin="waiter")

        self.assertIsNotNone(message)
        self.assertEqual(message.content, "hello[微笑]")
