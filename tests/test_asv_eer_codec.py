"""Unit checks for explicit codec conditions in independent-session EER."""

import unittest

from scripts.run_asv_eer_eval import configure_telephony_codec


class AsvEerCodecTests(unittest.TestCase):
    def test_none_disables_codec_without_mutating_input(self):
        source = {"codec": {"enabled": True, "name": "opus", "bitrate": "8k"}}
        configured = configure_telephony_codec(source, "none", "16k")
        self.assertFalse(configured["codec"]["enabled"])
        self.assertTrue(source["codec"]["enabled"])

    def test_opus_sets_bitrate(self):
        configured = configure_telephony_codec({}, "opus", "16k")
        self.assertEqual(
            configured["codec"],
            {"enabled": True, "name": "opus", "bitrate": "16k"},
        )

    def test_g711_enables_named_codec(self):
        configured = configure_telephony_codec({}, "g711", "ignored")
        self.assertEqual(configured["codec"], {"enabled": True, "name": "g711"})


if __name__ == "__main__":
    unittest.main()
