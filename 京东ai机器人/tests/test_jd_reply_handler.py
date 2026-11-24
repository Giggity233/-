import unittest

from jd_reply_handler import ReplyAction, reply_for_message


class _Client:
    def __init__(self, response: str | Exception) -> None:
        self.response = response
        self.calls: list[tuple[dict, str]] = []

    def chat(self, payload: dict, workflow_id: str) -> str:
        self.calls.append((dict(payload), workflow_id))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class ReplyHandlerTests(unittest.IsolatedAsyncioTestCase):
    def payload(self) -> dict:
        return {
            "aid": "aid",
            "buyer_name": "buyer",
            "chathistory": "history",
            "cookie": "pt_key=private",
            "input": "question",
            "shopid": "shop",
            "username": "robot",
            "waiter_pin": "robot",
        }

    async def test_sends_only_text_after_marker(self) -> None:
        client = _Client("售后ai回复@@@@您好，很高兴为您服务")

        action = await reply_for_message(self.payload(), workflow_id="workflow", client=client)

        self.assertIsInstance(action, ReplyAction)
        self.assertFalse(action.needs_transfer)
        self.assertEqual(action.text, "您好，很高兴为您服务")

    async def test_human_word_after_marker_transfers(self) -> None:
        client = _Client("售后ai回复@@@@请转人工")

        action = await reply_for_message(self.payload(), workflow_id="workflow", client=client)

        self.assertTrue(action.needs_transfer)
        self.assertIn("人工", action.transfer_reason)

    async def test_invalid_coze_result_transfers(self) -> None:
        client = _Client("售后ai回复没有分隔符")

        action = await reply_for_message(self.payload(), workflow_id="workflow", client=client)

        self.assertTrue(action.needs_transfer)
        self.assertIn("@@@@", action.transfer_reason)

    async def test_json_wrapped_result_transfers(self) -> None:
        client = _Client('{"output": "售后ai回复@@@@不应发送"}')

        action = await reply_for_message(self.payload(), workflow_id="workflow", client=client)

        self.assertTrue(action.needs_transfer)
        self.assertIn("格式", action.transfer_reason)
