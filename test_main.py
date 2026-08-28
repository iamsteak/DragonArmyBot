import os
import unittest

os.environ.setdefault("DISCORD_TOKEN", "test-token")

from economy import EconomyStore, SHOP  # noqa: E402
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

    def test_economy_progression(self) -> None:
        self.assertEqual(EconomyStore.level_for_xp(0), 1)
        self.assertEqual(EconomyStore.level_for_xp(100), 2)
        result, multiplier = EconomyStore.roll_game("coinflip")
        self.assertIn(result, {"heads", "tails"})
        self.assertEqual(multiplier, 2)

    def test_shop_catalog(self) -> None:
        self.assertEqual(len(SHOP), 20)
        for item in ("lockpick", "hacker_kit", "firewall", "vpn", "security_camera", "dragon_armor"):
            self.assertIn(item, SHOP)


if __name__ == "__main__":
    unittest.main()
