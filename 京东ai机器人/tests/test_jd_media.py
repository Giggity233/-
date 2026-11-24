import unittest

from jd_media import parse_image_directive, parse_video_directive


class JdMediaTests(unittest.TestCase):
    def test_parses_image_directive(self) -> None:
        directive = parse_image_directive("[图片]::::https://example.com/image.jpg")

        self.assertIsNotNone(directive)
        self.assertEqual(directive.image_url, "https://example.com/image.jpg")

    def test_parses_video_directive(self) -> None:
        directive = parse_video_directive(
            "[视频]::::https://example.com/video.mp4@@@https://example.com/cover.jpg"
        )

        self.assertIsNotNone(directive)
        self.assertEqual(directive.video_url, "https://example.com/video.mp4")
        self.assertEqual(directive.thumbnail_url, "https://example.com/cover.jpg")
