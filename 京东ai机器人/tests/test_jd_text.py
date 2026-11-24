import unittest

from jd_text import normalize_jd_emoticons


class JdTextTests(unittest.TestCase):
    def test_replaces_every_jd_emoticon_code_with_smile(self) -> None:
        self.assertEqual(
            normalize_jd_emoticons("你好#E-s49，收到#E-s100"),
            "你好[微笑]，收到[微笑]",
        )

    def test_keeps_non_emoticon_text_unchanged(self) -> None:
        self.assertEqual(normalize_jd_emoticons("#E-sx #E-s"), "#E-sx #E-s")
