import asyncio
import json
import random
import time
from pathlib import Path
from typing import Any


SHOP: dict[str, dict[str, Any]] = {
    "coffee": {"name": "Coffee", "price": 80, "description": "A small boost for your next work shift."},
    "lucky_charm": {"name": "Lucky Charm", "price": 450, "description": "A shiny collectible for your profile."},
    "fishing_rod": {"name": "Fishing Rod", "price": 900, "description": "A better chance at rare fish."},
    "pickaxe": {"name": "Pickaxe", "price": 900, "description": "A better chance at rare ore."},
    "crown": {"name": "Crown", "price": 5000, "description": "The ultimate status symbol."},
}


class EconomyStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"users": {}}
        self.lock = asyncio.Lock()

    async def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            await self.save()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON in {self.path}: {exc}") from exc

    def get(self, user_id: int) -> dict[str, Any]:
        key = str(user_id)
        users = self.data.setdefault("users", {})
        if key not in users:
            users[key] = {
                "wallet": 100,
                "bank": 0,
                "xp": 0,
                "level": 1,
                "inventory": {},
                "last_claims": {},
                "quest_progress": {"work": 0, "games": 0, "fish": 0},
            }
        user = users[key]
        user.setdefault("wallet", 100)
        user.setdefault("bank", 0)
        user.setdefault("xp", 0)
        user.setdefault("level", 1)
        user.setdefault("inventory", {})
        user.setdefault("last_claims", {})
        user.setdefault("quest_progress", {"work": 0, "games": 0, "fish": 0})
        return user

    async def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)

    @staticmethod
    def level_for_xp(xp: int) -> int:
        return max(1, int((xp / 100) ** 0.5) + 1)

    async def award(self, user_id: int, coins: int = 0, xp: int = 0) -> tuple[dict[str, Any], bool]:
        async with self.lock:
            user = self.get(user_id)
            old_level = user["level"]
            user["wallet"] += coins
            user["xp"] += xp
            user["level"] = self.level_for_xp(user["xp"])
            await self.save()
            return user, user["level"] > old_level

    async def cooldown(self, user_id: int, action: str, seconds: int) -> int:
        now = int(time.time())
        async with self.lock:
            user = self.get(user_id)
            last = int(user["last_claims"].get(action, 0))
            remaining = max(0, seconds - (now - last))
            if remaining == 0:
                user["last_claims"][action] = now
                await self.save()
            return remaining

    async def spend(self, user_id: int, amount: int) -> bool:
        async with self.lock:
            user = self.get(user_id)
            if amount < 0 or user["wallet"] < amount:
                return False
            user["wallet"] -= amount
            await self.save()
            return True

    async def transfer(self, sender_id: int, recipient_id: int, amount: int) -> bool:
        async with self.lock:
            if amount <= 0:
                return False
            sender = self.get(sender_id)
            if sender["wallet"] < amount:
                return False
            recipient = self.get(recipient_id)
            sender["wallet"] -= amount
            recipient["wallet"] += amount
            await self.save()
            return True

    async def deposit(self, user_id: int, amount: int) -> bool:
        async with self.lock:
            user = self.get(user_id)
            if amount <= 0 or user["wallet"] < amount:
                return False
            user["wallet"] -= amount
            user["bank"] += amount
            await self.save()
            return True

    async def withdraw(self, user_id: int, amount: int) -> bool:
        async with self.lock:
            user = self.get(user_id)
            if amount <= 0 or user["bank"] < amount:
                return False
            user["bank"] -= amount
            user["wallet"] += amount
            await self.save()
            return True

    async def add_item(self, user_id: int, item: str) -> None:
        async with self.lock:
            user = self.get(user_id)
            inventory = user["inventory"]
            inventory[item] = inventory.get(item, 0) + 1
            await self.save()

    async def progress(self, user_id: int, quest: str) -> None:
        async with self.lock:
            user = self.get(user_id)
            progress = user["quest_progress"]
            progress[quest] = progress.get(quest, 0) + 1
            await self.save()

    def leaderboard(self, limit: int = 10) -> list[tuple[str, dict[str, Any]]]:
        users = self.data.get("users", {})
        return sorted(users.items(), key=lambda pair: pair[1].get("wallet", 0) + pair[1].get("bank", 0), reverse=True)[:limit]

    @staticmethod
    def roll_game(game: str, has_lucky_charm: bool = False) -> tuple[str, int]:
        if game == "coinflip":
            return random.choice(("heads", "tails")), 2
        if game == "slots":
            symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
            result = [random.choice(symbols) for _ in range(3)]
            if result[0] == result[1] == result[2]:
                multiplier = 15 if result[0] == "7️⃣" else 8
            elif len(set(result)) == 2:
                multiplier = 2
            else:
                multiplier = 0
            return " ".join(result), multiplier
        return "", 0
