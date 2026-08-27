import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")

from main import default_config, parse_duration  # noqa: E402


class BotHelpersTest(unittest.TestCase):
    def test_parse_duration(self) -> None:
        self.assertEqual(parse_duration("10m"), 600)
        self.assertEqual(parse_duration("2h"), 7200)
        self.assertIsNone(parse_duration("forever"))
        self.assertIsNone(parse_duration("29d"))

    def test_default_config(self) -> None:
        config = default_config()
        self.assertFalse(config["automod_enabled"])
        self.assertEqual(config["blocked_words"], [])
        self.assertEqual(config["custom_commands"], {})


if __name__ == "__main__":
    unittest.main()
