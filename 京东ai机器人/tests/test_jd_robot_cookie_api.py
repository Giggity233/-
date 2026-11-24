import unittest

from jd_robot_cookie_api import RobotCookieApi, parse_cookie_string


class _Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class _Session:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.call = None
        self.calls = []

    def get(self, url: str, **kwargs: object) -> _Response:
        self.call = (url, kwargs)
        self.calls.append(self.call)
        return _Response(self.payload)


class RobotCookieApiTests(unittest.TestCase):
    def test_lists_enabled_customers(self) -> None:
        session = _Session(
            {
                "ok": True,
                "data": [{"id": 1, "name": "Demo Customer"}],
            }
        )
        api = RobotCookieApi(base_url="http://example.test/api/v1", session=session)

        customers = api.list_customers()

        self.assertEqual(customers[0].id, "1")
        self.assertEqual(customers[0].name, "Demo Customer")
        self.assertEqual(session.call[0], "http://example.test/api/v1/customers/")

    def test_lists_jingdong_robot_cookie_shops(self) -> None:
        session = _Session(
            {
                "ok": True,
                "data": [
                    {
                        "id": 7,
                        "shop_id": "jd-1",
                        "shop_name": "Demo Shop",
                        "customer_name": "Demo Customer",
                        "cookie": "thor=value; pin=waiter",
                        "cookie_status": "valid",
                    }
                ],
            }
        )
        api = RobotCookieApi(base_url="http://example.test/api/v1", session=session)

        shops = api.list_shops(platform="jingdong", customer_id="1")

        self.assertEqual(shops[0].key, "7")
        self.assertEqual(shops[0].shop_id, "jd-1")
        self.assertTrue(shops[0].can_start)
        self.assertEqual(session.calls[0][0], "http://example.test/api/v1/robot-cookies/")
        self.assertEqual(
            session.calls[0][1]["params"],
            {"platform": "jingdong", "customer_id": "1"},
        )
        self.assertEqual(session.calls[1][0], "http://example.test/api/v1/cookies/")

    def test_uses_first_human_account_id_of_the_same_shop(self) -> None:
        class _SequenceSession:
            def __init__(self) -> None:
                self.payloads = [
                    {"ok": True, "data": [{
                        "id": 7,
                        "shop_id": "jd-1",
                        "shop_name": "Demo Shop",
                        "customer_name": "Demo Customer",
                        "cookie": "thor=value; pin=waiter",
                        "cookie_status": "valid",
                    }]},
                    {"ok": True, "data": [{
                        "shop_id": "jd-1",
                        "human_accounts": [
                            {"account_id": "human-first", "account_name": "人工一号"},
                            {"account_id": "human-second", "account_name": "人工二号"},
                        ],
                    }]},
                ]
                self.calls = []

            def get(self, url: str, **kwargs: object) -> _Response:
                self.calls.append((url, kwargs))
                return _Response(self.payloads.pop(0))

        session = _SequenceSession()
        api = RobotCookieApi(base_url="http://example.test/api/v1", session=session)

        shops = api.list_shops(platform="jingdong", customer_id="1")

        self.assertEqual(shops[0].human_account_id, "human-first")
        self.assertEqual(shops[0].human_account_name, "人工一号")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(api.list_shops(platform="jingdong", customer_id="1")[0].human_account_id, "human-first")
        self.assertEqual(len(session.calls), 2)

    def test_lists_only_customers_that_have_robot_shops(self) -> None:
        class _SequenceSession:
            def __init__(self) -> None:
                self.payloads = [
                    {"ok": True, "data": [
                        {"id": 1, "name": "Has JD Shop"},
                        {"id": 2, "name": "No JD Shop"},
                    ]},
                    {"ok": True, "data": [{
                        "id": 3,
                        "shop_id": "jd-1",
                        "shop_name": "Demo Shop",
                        "customer_name": "Has JD Shop",
                        "cookie": "thor=value",
                        "cookie_status": "valid",
                    }]},
                    {"ok": True, "data": [{
                        "shop_id": "jd-1",
                        "human_accounts": [{"account_id": "human-first", "account_name": "人工一号"}],
                    }]},
                ]

            def get(self, _url: str, **_kwargs: object) -> _Response:
                return _Response(self.payloads.pop(0))

        api = RobotCookieApi(
            base_url="http://example.test/api/v1",
            session=_SequenceSession(),
        )

        customers = api.list_customers_with_robot_shops(platform="jingdong")

        self.assertEqual([(customer.id, customer.name) for customer in customers], [("1", "Has JD Shop")])

    def test_parses_cookie_string(self) -> None:
        self.assertEqual(
            parse_cookie_string("Cookie: thor=value; pin=waiter"),
            {"thor": "value", "pin": "waiter"},
        )
