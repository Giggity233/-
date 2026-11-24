import unittest

from jd_transfer_accounts import TransferAccountCache, TransferAccountService


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "code": 0,
            "Data": [
                {"AccountId": "human-id", "AccountType": 1, "Status": 1},
                {"AccountId": "offline-id", "AccountType": 1, "Status": 0},
                {"AccountName": "not-an-id", "AccountType": 1, "Status": 1},
            ],
        }


class _Session:
    def post(self, _url: str, **kwargs: object) -> _Response:
        self.kwargs = kwargs
        return _Response()


class TransferAccountServiceTests(unittest.TestCase):
    def test_returns_only_available_human_account_ids(self) -> None:
        session = _Session()
        service = TransferAccountService(session=session, url="http://example.test/accounts")

        account_ids = service.list_human_account_ids("robot-account")

        self.assertEqual(account_ids, ["human-id"])
        self.assertEqual(session.kwargs["json"], {"AccName": "robot-account", "ShopName": ""})

    def test_cache_reads_each_robot_account_once(self) -> None:
        calls: list[str] = []

        def provider(account_name: str) -> list[str]:
            calls.append(account_name)
            return ["human-{}".format(account_name)]

        cache = TransferAccountCache(provider)

        self.assertEqual(cache.get("robot-a"), ["human-robot-a"])
        self.assertEqual(cache.get("robot-a"), ["human-robot-a"])
        self.assertEqual(cache.get("robot-b"), ["human-robot-b"])
        self.assertEqual(calls, ["robot-a", "robot-b"])
