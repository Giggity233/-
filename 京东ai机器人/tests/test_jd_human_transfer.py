import asyncio
import unittest

from jd_human_transfer import JdHumanTransfer
from jd_message_listener import ReceivedMessage


def make_message() -> ReceivedMessage:
    return ReceivedMessage(
        session_id="buyer:im.customer:shop",
        buyer_id="buyer",
        vender_id="shop",
        content="人工",
        message_type="text",
        packet={},
    )


class HumanTransferTests(unittest.IsolatedAsyncioTestCase):
    async def test_transfers_to_the_first_configured_human_id_without_online_lookup(self) -> None:
        packets: list[dict] = []
        transfer = None

        async def send_packet(packet: dict) -> None:
            packets.append(packet)

        service = JdHumanTransfer(
            send_packet,
            waiter_pin="robot-account",
            aid="aid",
            human_account_id="human-first",
            human_account_name="人工一号",
        )
        task = asyncio.create_task(service.transfer_to_human(make_message(), "Coze 回复包含人工"))
        while not packets:
            await asyncio.sleep(0)
        transfer = packets[0]
        self.assertEqual(transfer["type"], "chat_transfer_partern")
        self.assertEqual(transfer["body"]["waiter"], "human-first")
        self.assertEqual(transfer["body"]["customer"], "buyer")
        self.assertEqual(transfer["body"]["reason"], "")
        self.assertNotIn("pid", transfer["body"])
        self.assertNotIn("ext", transfer["body"])
        service.handle_packet({
            "id": transfer["id"],
            "type": "chat_transfer_result",
            "body": {"code": 1, "bizCode": {"code": 1}},
        })
        self.assertTrue(await task)
        service.close()
