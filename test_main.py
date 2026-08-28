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

    def test_default_bank_limit(self) -> None:
        from economy import EconomyStore
        store = EconomyStore(__import__("pathlib").Path("/tmp/dragon-army-test-economy.json"))
        self.assertEqual(store.get(12345)["bank_limit"], 20_000)

    def test_economy_progression(self) -> None:
        self.assertEqual(EconomyStore.level_for_xp(0), 1)
        self.assertEqual(EconomyStore.level_for_xp(100), 2)
        result, multiplier = EconomyStore.roll_game("coinflip")
        self.assertIn(result, {"heads", "tails"})
        self.assertEqual(multiplier, 2)

    def test_server_leaderboard_scope(self) -> None:
        store = EconomyStore(__import__("pathlib").Path("/tmp/dragon-army-test-leaderboard.json"))
        store.data = {"users": {"1": {"wallet": 900, "bank": 0}, "2": {"wallet": 100, "bank": 0}}}
        rows = store.server_leaderboard({2})
        self.assertEqual([user_id for user_id, _ in rows], ["2"])

    def test_shop_catalog(self) -> None:
        self.assertEqual(len(SHOP), 23)
        for item in ("bank_card", "gold_bank_card", "platinum_bank_card"):
            self.assertIn(item, SHOP)
        for item in ("lockpick", "hacker_kit", "firewall", "vpn", "security_camera", "dragon_armor"):
            self.assertIn(item, SHOP)


if __name__ == "__main__":
    unittest.main()
