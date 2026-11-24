import unittest

from jd_coze_api import COZE_PARAMETER_FIELDS, build_workflow_parameters


class CozeParameterTests(unittest.TestCase):
    def test_builds_only_the_eight_jd_workflow_parameters(self) -> None:
        parameters = build_workflow_parameters({
            "aid": "aid",
            "buyer_name": "buyer",
            "chathistory": "history",
            "cookie": "cookie",
            "input": "question",
            "shopid": "shop",
            "username": "robot",
            "waiter_pin": "reply-waiter",
            "internal_field": "must not be sent",
        })

        self.assertEqual(tuple(parameters), COZE_PARAMETER_FIELDS)
        self.assertEqual(parameters["username"], "robot")
        self.assertEqual(parameters["buyer_name"], "buyer")
        self.assertEqual(parameters["waiter_pin"], "reply-waiter")
