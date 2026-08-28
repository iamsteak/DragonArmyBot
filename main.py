import asyncio
import json
import logging
import os
import random
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from economy import EconomyStore, SHOP
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("dragon-army-bot")

TOKEN = os.getenv("DISCORD_TOKEN") or os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Missing DISCORD_TOKEN (or BOT_TOKEN) environment variable.")

GUILD_ID = os.getenv("DISCORD_GUILD_ID")
DATA_FILE = Path(os.getenv("DATA_FILE", "data/config.json"))


def default_config() -> dict[str, Any]:
    return {
        "log_channel_id": None,
        "welcome_channel_id": None,
        "welcome_message": None,
        "automod_enabled": False,
        "blocked_words": [],
        "custom_commands": {},
    }


class GuildStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"guilds": {}}
        self.lock = asyncio.Lock()

    async def load(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            await self.save()
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON in {self.path}: {exc}") from exc

    def get(self, guild_id: int) -> dict[str, Any]:
        key = str(guild_id)
        if key not in self.data.setdefault("guilds", {}):
            self.data["guilds"][key] = default_config()
        return self.data["guilds"][key]

    async def update(self, guild_id: int, **changes: Any) -> dict[str, Any]:
        async with self.lock:
            config = self.get(guild_id)
            config.update(changes)
            await self.save()
            return config

    async def reset(self, guild_id: int) -> None:
        async with self.lock:
            self.data.setdefault("guilds", {}).pop(str(guild_id), None)
            await self.save()

    async def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.path)


store = GuildStore(DATA_FILE)
economy = EconomyStore(DATA_FILE.with_name("economy.json"))
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
config_group = app_commands.Group(name="config", description="Configure this server")
automod_group = app_commands.Group(name="blockword", description="Manage blocked words")
custom_group = app_commands.Group(name="custom-command", description="Manage custom server responses")
economy_group = app_commands.Group(name="economy", description="Play the Dragon Army economy game")
_sync_complete = False


def guild_only(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None


async def log_to_channel(guild: discord.Guild, text: str) -> None:
    channel_id = store.get(guild.id).get("log_channel_id")
    if not channel_id:
        return
    channel = guild.get_channel(int(channel_id))
    if isinstance(channel, discord.TextChannel):
        await channel.send(text)


def can_moderate(actor: discord.Member, target: discord.Member) -> bool:
    return (
        actor.id != target.id
        and target.id != actor.guild.owner_id
        and actor.top_role > target.top_role
    )


def parse_duration(value: str) -> int | None:
    match = re.fullmatch(r"(\d+)(s|m|h|d|w)", value.strip().lower())
    if not match:
        return None
    amount = int(match.group(1))
    multiplier = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[match.group(2)]
    seconds = amount * multiplier
    return seconds if 0 < seconds <= 28 * 86400 else None


@bot.event
async def on_ready() -> None:
    global _sync_complete
    if _sync_complete:
        return
    if GUILD_ID:
        guild = discord.Object(id=int(GUILD_ID))
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        log.info("Registered %s slash commands in guild %s", len(synced), GUILD_ID)
    else:
        synced = await bot.tree.sync()
        log.info("Registered %s global slash commands", len(synced))
    _sync_complete = True
    log.info("Logged in as %s", bot.user)


@bot.event
async def on_member_join(member: discord.Member) -> None:
    config = store.get(member.guild.id)
    channel_id = config.get("welcome_channel_id")
    template = config.get("welcome_message")
    if not channel_id or not template:
        return
    channel = member.guild.get_channel(int(channel_id))
    if not isinstance(channel, discord.TextChannel):
        return
    text = template.replace("{user}", member.mention).replace("{server}", member.guild.name)
    await channel.send(text)


@bot.event
async def on_member_remove(member: discord.Member) -> None:
    await log_to_channel(member.guild, f"Member left: {member.user.tag}")


@bot.event
async def on_member_ban(guild: discord.Guild, user: discord.User) -> None:
    await log_to_channel(guild, f"Ban: {user.tag}")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.guild is None or message.author.bot:
        return
    config = store.get(message.guild.id)
    if not config.get("automod_enabled"):
        return
    if isinstance(message.author, discord.Member) and message.author.guild_permissions.manage_messages:
        return
    content = message.content.casefold()
    if not any(word.casefold() in content for word in config.get("blocked_words", [])):
        return
    try:
        await message.delete()
        warning = await message.channel.send(f"{message.author.mention}, that message was removed by automod.")
        await asyncio.sleep(5)
        await warning.delete()
        await log_to_channel(message.guild, f"Automod removed a message from {message.author} in {message.channel.mention}")
    except discord.HTTPException:
        log.exception("Automod action failed")


@bot.tree.command(name="help", description="Show the bot command guide")
async def help_command(interaction: discord.Interaction) -> None:
    embed = discord.Embed(
        title="Dragon Army Bot",
        description="Slash-command moderation, automod, onboarding, logging, and utilities.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="Moderation", value="`/warn`, `/timeout`, `/kick`, `/ban`, `/purge`", inline=False)
    embed.add_field(name="Setup", value="`/config`, `/automod`, `/blockword`, `/custom-command`", inline=False)
    embed.add_field(name="Utilities", value="`/ping`, `/server`, `/userinfo`, `/custom`", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="ping", description="Check the bot latency")
async def ping(interaction: discord.Interaction) -> None:
    await interaction.response.send_message(f"Pong. Gateway latency: {bot.latency * 1000:.0f}ms.")


@bot.tree.command(name="server", description="Show server information")
@app_commands.guild_only()
async def server(interaction: discord.Interaction) -> None:
    guild = interaction.guild
    assert guild is not None
    embed = discord.Embed(title=guild.name, color=discord.Color.dark_gray())
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
    embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "D"), inline=True)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show information about a member")
@app_commands.guild_only()
@app_commands.describe(user="Member to inspect")
async def userinfo(interaction: discord.Interaction, user: discord.Member | None = None) -> None:
    member = user or interaction.user
    if not isinstance(member, discord.Member):
        await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
        return
    roles = [role.mention for role in member.roles if role != interaction.guild.default_role]
    embed = discord.Embed(title=str(member), color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "Unknown")
    embed.add_field(name="Roles", value=", ".join(roles) or "None", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="warn", description="Warn a member")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(user="Member to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str) -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    await interaction.response.send_message(f"Warned {user.mention} for: {reason}")
    await log_to_channel(interaction.guild, f"Warning: {user} was warned by {interaction.user}. Reason: {reason}")


@bot.tree.command(name="timeout", description="Temporarily timeout a member")
@app_commands.guild_only()
@app_commands.default_permissions(moderate_members=True)
@app_commands.describe(user="Member to timeout", duration="For example 10m, 2h, or 1d", reason="Reason")
async def timeout(interaction: discord.Interaction, user: discord.Member, duration: str, reason: str = "No reason provided") -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    seconds = parse_duration(duration)
    if seconds is None or not can_moderate(interaction.user, user):
        await interaction.response.send_message("Use a duration like `10m` or `2h` (maximum 28 days), and make sure the target is below your role.", ephemeral=True)
        return
    await user.timeout(discord.utils.utcnow() + timedelta(seconds=seconds), reason=reason)
    await interaction.response.send_message(f"Timed out {user.mention} for `{duration}`. Reason: {reason}")


@bot.tree.command(name="kick", description="Kick a member")
@app_commands.guild_only()
@app_commands.default_permissions(kick_members=True)
@app_commands.describe(user="Member to kick", reason="Reason")
async def kick(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided") -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    if not can_moderate(interaction.user, user):
        await interaction.response.send_message("That member has an equal or higher role than you.", ephemeral=True)
        return
    await user.kick(reason=reason)
    await interaction.response.send_message(f"Kicked **{user}**. Reason: {reason}")


@bot.tree.command(name="ban", description="Ban a member")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
@app_commands.describe(user="Member to ban", reason="Reason")
async def ban(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided") -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    if not can_moderate(interaction.user, user):
        await interaction.response.send_message("That member has an equal or higher role than you.", ephemeral=True)
        return
    await user.ban(reason=reason)
    await interaction.response.send_message(f"Banned **{user}**. Reason: {reason}")


@bot.tree.command(name="purge", description="Delete recent messages from this channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_messages=True)
@app_commands.describe(amount="Number of messages, from 1 to 100")
async def purge(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100]) -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This command only works in a standard text channel.", ephemeral=True)
        return
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.response.send_message(f"Deleted {len(deleted)} message(s).", ephemeral=True)


@config_group.command(name="view", description="View the current server configuration")
@app_commands.guild_only()
async def config_view(interaction: discord.Interaction) -> None:
    config = store.get(interaction.guild.id)
    text = "Command mode: slash commands only\n"
    text += f"Log channel: <#{config['log_channel_id']}>\n" if config.get("log_channel_id") else "Log channel: not set\n"
    text += f"Welcome channel: <#{config['welcome_channel_id']}>\n" if config.get("welcome_channel_id") else "Welcome channel: not set\n"
    text += f"Automod: {'enabled' if config.get('automod_enabled') else 'disabled'}\nBlocked words: {len(config.get('blocked_words', []))}"
    await interaction.response.send_message(text, ephemeral=True)


@config_group.command(name="log-channel", description="Set the moderation log channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def config_log_channel(interaction: discord.Interaction, channel: discord.TextChannel) -> None:
    await store.update(interaction.guild.id, log_channel_id=channel.id)
    await interaction.response.send_message(f"Moderation logs will be sent to {channel.mention}.")


@config_group.command(name="welcome", description="Set the welcome channel and message")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
@app_commands.describe(channel="Welcome channel", message="Use {user} and {server} placeholders")
async def config_welcome(interaction: discord.Interaction, channel: discord.TextChannel, message: str) -> None:
    await store.update(interaction.guild.id, welcome_channel_id=channel.id, welcome_message=message)
    await interaction.response.send_message(f"Welcome messages will be sent to {channel.mention}.")


@config_group.command(name="reset", description="Reset this server configuration")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def config_reset(interaction: discord.Interaction) -> None:
    await store.reset(interaction.guild.id)
    await interaction.response.send_message("Server configuration reset.")


@automod_group.command(name="add", description="Add a blocked word or phrase")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def blockword_add(interaction: discord.Interaction, word: str) -> None:
    config = store.get(interaction.guild.id)
    words = set(config.get("blocked_words", []))
    words.add(word.strip().casefold())
    await store.update(interaction.guild.id, blocked_words=sorted(words))
    await interaction.response.send_message(f"Blocked word list updated. Current count: {len(words)}.")


@automod_group.command(name="remove", description="Remove a blocked word or phrase")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def blockword_remove(interaction: discord.Interaction, word: str) -> None:
    config = store.get(interaction.guild.id)
    words = set(config.get("blocked_words", []))
    words.discard(word.strip().casefold())
    await store.update(interaction.guild.id, blocked_words=sorted(words))
    await interaction.response.send_message(f"Blocked word list updated. Current count: {len(words)}.")


@automod_group.command(name="list", description="List blocked words")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def blockword_list(interaction: discord.Interaction) -> None:
    words = store.get(interaction.guild.id).get("blocked_words", [])
    await interaction.response.send_message("\n".join(f"- {word}" for word in words) or "No blocked words configured.", ephemeral=True)


@bot.tree.command(name="automod", description="Enable or disable blocked-word automod")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def automod(interaction: discord.Interaction, enabled: bool) -> None:
    await store.update(interaction.guild.id, automod_enabled=enabled)
    await interaction.response.send_message(f"Blocked-word automod is now **{'enabled' if enabled else 'disabled'}**.")


@custom_group.command(name="set", description="Set a custom server response")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def custom_set(interaction: discord.Interaction, name: str, response: str) -> None:
    safe_name = re.sub(r"[^a-z0-9-]", "-", name.casefold())[:32]
    config = store.get(interaction.guild.id)
    custom_commands = dict(config.get("custom_commands", {}))
    custom_commands[safe_name] = response[:2000]
    await store.update(interaction.guild.id, custom_commands=custom_commands)
    await interaction.response.send_message(f"Custom response `{safe_name}` saved.")


@custom_group.command(name="remove", description="Remove a custom server response")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def custom_remove(interaction: discord.Interaction, name: str) -> None:
    config = store.get(interaction.guild.id)
    custom_commands = dict(config.get("custom_commands", {}))
    custom_commands.pop(name.casefold(), None)
    await store.update(interaction.guild.id, custom_commands=custom_commands)
    await interaction.response.send_message(f"Custom response `{name.casefold()}` removed.")


@custom_group.command(name="list", description="List custom server responses")
@app_commands.guild_only()
@app_commands.default_permissions(manage_guild=True)
async def custom_list(interaction: discord.Interaction) -> None:
    names = list(store.get(interaction.guild.id).get("custom_commands", {}).keys())
    await interaction.response.send_message("\n".join(f"- `{name}`" for name in names) or "No custom responses configured.", ephemeral=True)


@bot.tree.command(name="custom", description="Run a configured custom server response")
@app_commands.guild_only()
async def custom(interaction: discord.Interaction, name: str) -> None:
    response = store.get(interaction.guild.id).get("custom_commands", {}).get(name.casefold())
    if not response:
        await interaction.response.send_message(f"No custom response named `{name.casefold()}` exists.", ephemeral=True)
        return
    response = response.replace("{user}", interaction.user.mention).replace("{server}", interaction.guild.name)
    await interaction.response.send_message(response)


@economy_group.command(name="balance", description="View a wallet and bank balance")
async def economy_balance(interaction: discord.Interaction, user: discord.User | None = None) -> None:
    target = user or interaction.user
    profile = economy.get(target.id)
    total = profile["wallet"] + profile["bank"]
    await interaction.response.send_message(
        f"**{target.display_name}'s account**\\nWallet: **{profile['wallet']:,}** coins\\nBank: **{profile['bank']:,} / {profile['bank_limit']:,}** coins\\nNet worth: **{total:,}** coins\\nLevel: **{profile['level']}** ({profile['xp']:,} XP)",
    )


@economy_group.command(name="daily", description="Claim your daily coins")
async def economy_daily(interaction: discord.Interaction) -> None:
    remaining = await economy.cooldown(interaction.user.id, "daily", 86_400)
    if remaining:
        await interaction.response.send_message(f"Your daily reward is ready in **{remaining // 3600}h {(remaining % 3600) // 60}m**.", ephemeral=True)
        return
    streak_bonus = random.randint(25, 100)
    profile, level_up = await economy.award(interaction.user.id, coins=500 + streak_bonus, xp=30)
    await interaction.response.send_message(f"Daily claimed: **{500 + streak_bonus:,}** coins. Wallet: **{profile['wallet']:,}**." + (f" Level up! You reached level **{profile['level']}**." if level_up else ""))


async def earn_command(interaction: discord.Interaction, action: str, cooldown: int, low: int, high: int, xp: int, messages: list[str]) -> None:
    remaining = await economy.cooldown(interaction.user.id, action, cooldown)
    if remaining:
        await interaction.response.send_message(f"Try again in **{remaining}s**.", ephemeral=True)
        return
    amount = random.randint(low, high)
    profile, level_up = await economy.award(interaction.user.id, coins=amount, xp=xp)
    text = f"{random.choice(messages)} You earned **{amount:,}** coins."
    if level_up:
        text += f" You leveled up to **{profile['level']}**!"
    await interaction.response.send_message(text)


@economy_group.command(name="work", description="Work a random job for coins")
async def economy_work(interaction: discord.Interaction) -> None:
    await earn_command(interaction, "work", 45, 80, 240, 20, ["You completed a delivery.", "You repaired a mech.", "You performed at the tavern.", "You solved a guild contract."])
    await economy.progress(interaction.user.id, "work")


@economy_group.command(name="fish", description="Go fishing for coins and rare loot")
async def economy_fish(interaction: discord.Interaction) -> None:
    remaining = await economy.cooldown(interaction.user.id, "fish", 30)
    if remaining:
        await interaction.response.send_message(f"Your fishing rod needs **{remaining}s** before the next cast.", ephemeral=True)
        return
    profile = economy.get(interaction.user.id)
    catches = [("small fish", 90), ("salmon", 180), ("golden koi", 650), ("ancient pearl", 1500)]
    name, value = random.choices(catches, weights=[55, 30, 12, 3])[0]
    if profile["inventory"].get("fishing_rod"):
        value = int(value * 1.35)
    updated, level_up = await economy.award(interaction.user.id, coins=value, xp=25)
    await economy.progress(interaction.user.id, "fish")
    await interaction.response.send_message(f"You caught a **{name}** worth **{value:,}** coins. Wallet: **{updated['wallet']:,}**." + (f" Level up to **{updated['level']}**!" if level_up else ""))


@economy_group.command(name="mine", description="Mine ore for coins")
async def economy_mine(interaction: discord.Interaction) -> None:
    remaining = await economy.cooldown(interaction.user.id, "mine", 35)
    if remaining:
        await interaction.response.send_message(f"Your arms are tired. Try again in **{remaining}s**.", ephemeral=True)
        return
    profile = economy.get(interaction.user.id)
    ores = [("coal", 70), ("iron", 160), ("ruby", 500), ("dragon crystal", 1800)]
    name, value = random.choices(ores, weights=[52, 30, 14, 4])[0]
    if profile["inventory"].get("pickaxe"):
        value = int(value * 1.35)
    updated, level_up = await economy.award(interaction.user.id, coins=value, xp=28)
    await interaction.response.send_message(f"You mined **{name}** worth **{value:,}** coins. Wallet: **{updated['wallet']:,}**." + (f" Level up to **{updated['level']}**!" if level_up else ""))


@economy_group.command(name="hunt", description="Hunt a creature for a risky reward")
async def economy_hunt(interaction: discord.Interaction) -> None:
    remaining = await economy.cooldown(interaction.user.id, "hunt", 40)
    if remaining:
        await interaction.response.send_message(f"The forest is quiet. Try again in **{remaining}s**.", ephemeral=True)
        return
    result = random.choices([("rabbit", 100), ("boar", 280), ("griffin feather", 1000), ("dragon scale", 2500)], weights=[50, 30, 16, 4])[0]
    if economy.get(interaction.user.id).get("inventory", {}).get("hunter_charm", 0) > 0:
        result = (result[0], int(result[1] * 1.30))
    profile, level_up = await economy.award(interaction.user.id, coins=result[1], xp=35)
    await interaction.response.send_message(f"Your hunt found a **{result[0]}** worth **{result[1]:,}** coins. Wallet: **{profile['wallet']:,}**." + (f" Level up to **{profile['level']}**!" if level_up else ""))


@economy_group.command(name="slots", description="Play the slot machine")
@app_commands.describe(bet="Coins to wager")
async def economy_slots(interaction: discord.Interaction, bet: app_commands.Range[int, 1, 1000]) -> None:
    remaining = await economy.cooldown(interaction.user.id, "slots", 5)
    if remaining:
        await interaction.response.send_message("The slot machine is cooling down. Try again in a few seconds.", ephemeral=True)
        return
    if not await economy.spend(interaction.user.id, bet):
        await interaction.response.send_message("You do not have enough wallet coins for that bet.", ephemeral=True)
        return
    result, multiplier = EconomyStore.roll_game("slots", has_lucky_charm=bool(economy.get(interaction.user.id).get("inventory", {}).get("lucky_charm", 0)))
    winnings = bet * multiplier
    profile, level_up = await economy.award(interaction.user.id, coins=winnings, xp=10)
    await economy.progress(interaction.user.id, "games")
    message = f"**{result}**\\n"
    message += f"Jackpot! You won **{winnings:,}** coins!" if multiplier else f"You lost **{bet:,}** coins."
    message += f" Wallet: **{profile['wallet']:,}**."
    await interaction.response.send_message(message)


@economy_group.command(name="coinflip", description="Bet on heads or tails")
@app_commands.describe(choice="heads or tails", bet="Coins to wager")
@app_commands.choices(choice=[app_commands.Choice(name="Heads", value="heads"), app_commands.Choice(name="Tails", value="tails")])
async def economy_coinflip(interaction: discord.Interaction, choice: app_commands.Choice[str], bet: app_commands.Range[int, 1, 1000]) -> None:
    if not await economy.spend(interaction.user.id, bet):
        await interaction.response.send_message("You do not have enough wallet coins for that bet.", ephemeral=True)
        return
    result = random.choice(["heads", "tails"])
    won = result == choice.value
    has_dice = economy.get(interaction.user.id).get("inventory", {}).get("sapphire_dice", 0) > 0
    winnings = bet * (3 if has_dice else 2) if won else 0
    profile, _ = await economy.award(interaction.user.id, coins=winnings, xp=8)
    await economy.progress(interaction.user.id, "games")
    await interaction.response.send_message(f"The coin landed on **{result}**. " + (f"You won **{winnings:,}** coins!" if won else f"You lost **{bet:,}** coins.") + f" Wallet: **{profile['wallet']:,}**.")


@economy_group.command(name="shop", description="View the coin shop")
async def economy_shop(interaction: discord.Interaction) -> None:
    lines = [f"**{key}** — {item['price']:,} coins — {item['description']}" for key, item in SHOP.items()]
    await interaction.response.send_message("**Dragon Army Shop**\\n" + "\\n".join(lines), ephemeral=True)


@economy_group.command(name="buy", description="Buy an item from the coin shop")
@app_commands.describe(item="Shop item key")
async def economy_buy(interaction: discord.Interaction, item: str) -> None:
    key = item.casefold()
    if key not in SHOP:
        await interaction.response.send_message(f"That item is not in the shop. Use `/economy shop`.", ephemeral=True)
        return
    product = SHOP[key]
    if not await economy.spend(interaction.user.id, product["price"]):
        await interaction.response.send_message("You do not have enough wallet coins.", ephemeral=True)
        return
    await economy.add_item(interaction.user.id, key)
    await interaction.response.send_message(f"You bought **{product['name']}** for **{product['price']:,}** coins.")


@economy_group.command(name="inventory", description="View your inventory")
async def economy_inventory(interaction: discord.Interaction) -> None:
    inventory = economy.get(interaction.user.id).get("inventory", {})
    text = "\\n".join(f"- **{SHOP.get(key, {'name': key})['name']}** x{amount}" for key, amount in inventory.items())
    await interaction.response.send_message(text or "Your inventory is empty. Visit `/economy shop`.", ephemeral=True)


@economy_group.command(name="pay", description="Pay another member from your wallet")
@app_commands.describe(user="Member to pay", amount="Coins to transfer")
async def economy_pay(interaction: discord.Interaction, user: discord.User, amount: app_commands.Range[int, 1, 1000000]) -> None:
    if user.id == interaction.user.id or user.bot:
        await interaction.response.send_message("Choose another human member.", ephemeral=True)
        return
    if not await economy.transfer(interaction.user.id, user.id, amount):
        await interaction.response.send_message("Payment failed. Check your wallet balance and amount.", ephemeral=True)
        return
    await interaction.response.send_message(f"Paid **{amount:,}** coins to {user.mention}.")


@economy_group.command(name="deposit", description="Move wallet coins into your bank")
async def economy_deposit(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 1000000]) -> None:
    profile = economy.get(interaction.user.id)
    if profile["bank"] + amount > profile["bank_limit"]:
        await interaction.response.send_message(f"That deposit exceeds your bank limit of **{profile['bank_limit']:,}** coins. Buy and use a bank card to increase it.", ephemeral=True)
        return
    if not await economy.deposit(interaction.user.id, amount):
        await interaction.response.send_message("You do not have enough wallet coins.", ephemeral=True)
        return
    await interaction.response.send_message(f"Deposited **{amount:,}** coins into your bank.")


@economy_group.command(name="bank-balance", description="View your bank balance and limit")
async def economy_bank_balance(interaction: discord.Interaction) -> None:
    profile = economy.get(interaction.user.id)
    available = profile["bank_limit"] - profile["bank"]
    await interaction.response.send_message(f"Bank balance: **{profile['bank']:,} / {profile['bank_limit']:,}** coins. Available space: **{available:,}** coins.")


@economy_group.command(name="withdraw", description="Move bank coins into your wallet")
async def economy_withdraw(interaction: discord.Interaction, amount: app_commands.Range[int, 1, 1000000]) -> None:
    if not await economy.withdraw(interaction.user.id, amount):
        await interaction.response.send_message("You do not have enough banked coins.", ephemeral=True)
        return
    await interaction.response.send_message(f"Withdrew **{amount:,}** coins from your bank.")


@economy_group.command(name="leaderboard", description="View the richest players")
async def economy_leaderboard(interaction: discord.Interaction) -> None:
    rows = economy.leaderboard()
    if not rows:
        await interaction.response.send_message("No players yet. Start with `/economy daily`!")
        return
    lines = [f"**{index}.** <@{user_id}> — {profile.get('wallet', 0) + profile.get('bank', 0):,} coins" for index, (user_id, profile) in enumerate(rows, start=1)]
    await interaction.response.send_message("**Dragon Army Rich List**\\n" + "\\n".join(lines))


@economy_group.command(name="server-leaderboard", description="View the richest players in this server")
@app_commands.guild_only()
async def economy_server_leaderboard(interaction: discord.Interaction) -> None:
    member_ids = {member.id for member in interaction.guild.members if not member.bot}
    rows = economy.server_leaderboard(member_ids)
    if not rows:
        await interaction.response.send_message("No server players have an economy profile yet. Start with `/economy daily`!")
        return
    lines = [f"**{index}.** <@{user_id}> — {economy.wealth(profile):,} coins" for index, (user_id, profile) in enumerate(rows, start=1)]
    await interaction.response.send_message(f"**{interaction.guild.name} Server Rich List**\\n" + "\\n".join(lines))


@economy_group.command(name="quest", description="View your rotating economy quests")
async def economy_quest(interaction: discord.Interaction) -> None:
    profile = economy.get(interaction.user.id)
    progress = profile.get("quest_progress", {})
    lines = [f"Work **{min(progress.get('work', 0), 5)}/5** — reward 500 coins", f"Play games **{min(progress.get('games', 0), 3)}/3** — reward 350 coins", f"Fish **{min(progress.get('fish', 0), 3)}/3** — reward 450 coins"]
    await interaction.response.send_message("**Daily Guild Quests**\\n" + "\\n".join(lines) + "\\nComplete them during your adventures to track progress.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Set the current channel slowmode")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def slowmode(interaction: discord.Interaction, seconds: app_commands.Range[int, 0, 21600]) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This only works in a text channel.", ephemeral=True)
        return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"Slowmode set to **{seconds} seconds**.")


@bot.tree.command(name="lock", description="Lock the current channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def lock(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This only works in a text channel.", ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Locked by {interaction.user}")
    await interaction.response.send_message("Channel locked. Members can no longer send messages.")


@bot.tree.command(name="unlock", description="Unlock the current channel")
@app_commands.guild_only()
@app_commands.default_permissions(manage_channels=True)
async def unlock(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("This only works in a text channel.", ephemeral=True)
        return
    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = None
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite, reason=f"Unlocked by {interaction.user}")
    await interaction.response.send_message("Channel unlocked.")


@bot.tree.command(name="nickname", description="Set or clear a member nickname")
@app_commands.guild_only()
@app_commands.default_permissions(manage_nicknames=True)
async def nickname(interaction: discord.Interaction, user: discord.Member, name: str | None = None) -> None:
    if not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.manage_nicknames:
        await interaction.response.send_message("You do not have permission to manage nicknames.", ephemeral=True)
        return
    if not can_moderate(interaction.user, user):
        await interaction.response.send_message("That member has an equal or higher role than you.", ephemeral=True)
        return
    await user.edit(nick=name, reason=f"Nickname changed by {interaction.user}")
    await interaction.response.send_message(f"Nickname {'cleared' if not name else 'set to ' + name} for {user.mention}.")


@bot.tree.command(name="unban", description="Unban a user by ID")
@app_commands.guild_only()
@app_commands.default_permissions(ban_members=True)
async def unban(interaction: discord.Interaction, user_id: str) -> None:
    if not user_id.isdigit():
        await interaction.response.send_message("Enter a numeric Discord user ID.", ephemeral=True)
        return
    user = await bot.fetch_user(int(user_id))
    await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}")
    await interaction.response.send_message(f"Unbanned **{user}**.")


@economy_group.command(name="use", description="Use a consumable economy item")
@app_commands.describe(item="Item key, such as bank_card, coffee, firewall, or medkit")
async def economy_use(interaction: discord.Interaction, item: str) -> None:
    key = item.casefold()
    consumables = {"coffee", "energy_drink", "golden_ticket", "medkit"}
    bank_cards = {"bank_card": 10_000, "gold_bank_card": 25_000, "platinum_bank_card": 100_000}
    if key in bank_cards:
        if not await economy.consume_item(interaction.user.id, key):
            await interaction.response.send_message("You do not own that bank card.", ephemeral=True)
            return
        profile = economy.get(interaction.user.id)
        profile["bank_limit"] += bank_cards[key]
        await economy.save()
        await interaction.response.send_message(f"{SHOP[key]['name']} activated. Your bank limit is now **{profile['bank_limit']:,}** coins.")
        return
    if key not in consumables:
        await interaction.response.send_message("That item is passive or activates automatically. Check `/economy shop`.", ephemeral=True)
        return
    if not await economy.consume_item(interaction.user.id, key):
        await interaction.response.send_message("You do not own that item.", ephemeral=True)
        return
    if key == "coffee":
        profile, _ = await economy.award(interaction.user.id, coins=150, xp=8)
        text = f"You drank Coffee and earned a quick **150** coins. Wallet: **{profile['wallet']:,}**."
    elif key == "energy_drink":
        await economy.reset_cooldown(interaction.user.id, "work")
        text = "Energy Drink activated. Your `/economy work` cooldown is ready again."
    elif key == "golden_ticket":
        profile, _ = await economy.award(interaction.user.id, coins=350, xp=15)
        text = f"Golden Ticket redeemed for **350** coins. Wallet: **{profile['wallet']:,}**."
    else:
        profile, _ = await economy.award(interaction.user.id, coins=250, xp=5)
        text = f"Medkit sold for **250** emergency coins. Wallet: **{profile['wallet']:,}**."
    await interaction.response.send_message(text)


@economy_group.command(name="rob", description="Attempt to rob another player’s wallet")
@app_commands.guild_only()
@app_commands.describe(user="Player to rob")
async def economy_rob(interaction: discord.Interaction, user: discord.Member) -> None:
    if user.bot or user.id == interaction.user.id:
        await interaction.response.send_message("Choose another human player.", ephemeral=True)
        return
    remaining = await economy.cooldown(interaction.user.id, "rob", 90)
    if remaining:
        await interaction.response.send_message(f"Your next robbery is ready in **{remaining}s**.", ephemeral=True)
        return
    target_profile = economy.get(user.id)
    target_inventory = target_profile.get("inventory", {})
    for defense in ("dragon_armor", "security_camera"):
        if target_inventory.get(defense, 0) > 0:
            await economy.consume_item(user.id, defense)
            await interaction.response.send_message(f"Robbery blocked! {user.mention} used **{SHOP[defense]['name']}**.")
            return
    attacker_profile = economy.get(interaction.user.id)
    chance = 0.38
    if attacker_profile.get("inventory", {}).get("lockpick", 0) > 0:
        await economy.consume_item(interaction.user.id, "lockpick")
        chance += 0.18
    if random.random() > chance:
        await interaction.response.send_message("The robbery failed and the guards are now alert.")
        return
    available = target_profile["wallet"]
    if available < 20:
        await interaction.response.send_message("That player’s wallet is too empty to rob.", ephemeral=True)
        return
    amount = min(max(20, int(available * random.uniform(0.10, 0.25))), 1200)
    reduction = 1.0
    if target_inventory.get("decoy_wallet", 0) > 0:
        await economy.consume_item(user.id, "decoy_wallet")
        reduction *= 0.5
    if target_inventory.get("insurance", 0) > 0:
        await economy.consume_item(user.id, "insurance")
        reduction *= 0.65
    amount = max(1, int(amount * reduction))
    await economy.steal(interaction.user.id, user.id, amount, source="wallet")
    await interaction.response.send_message(f"Robbery successful! You stole **{amount:,}** coins from {user.mention}.")


@economy_group.command(name="hack", description="Attempt to hack another player’s bank")
@app_commands.guild_only()
@app_commands.describe(user="Player to hack")
async def economy_hack(interaction: discord.Interaction, user: discord.Member) -> None:
    if user.bot or user.id == interaction.user.id:
        await interaction.response.send_message("Choose another human player.", ephemeral=True)
        return
    remaining = await economy.cooldown(interaction.user.id, "hack", 120)
    if remaining:
        await interaction.response.send_message(f"Your next hack is ready in **{remaining}s**.", ephemeral=True)
        return
    target_profile = economy.get(user.id)
    target_inventory = target_profile.get("inventory", {})
    for defense in ("dragon_armor", "firewall", "vpn"):
        if target_inventory.get(defense, 0) > 0:
            await economy.consume_item(user.id, defense)
            await interaction.response.send_message(f"Hack blocked! {user.mention} used **{SHOP[defense]['name']}**.")
            return
    attacker_profile = economy.get(interaction.user.id)
    chance = 0.28
    if attacker_profile.get("inventory", {}).get("hacker_kit", 0) > 0:
        await economy.consume_item(interaction.user.id, "hacker_kit")
        chance += 0.22
    if random.random() > chance:
        await interaction.response.send_message("Hack failed. The target’s bank security held.")
        return
    available = target_profile["bank"]
    if available < 50:
        await interaction.response.send_message("That player’s bank has too little balance to hack.", ephemeral=True)
        return
    amount = min(max(50, int(available * random.uniform(0.08, 0.20))), 1500)
    if target_inventory.get("insurance", 0) > 0:
        await economy.consume_item(user.id, "insurance")
        amount = max(1, int(amount * 0.55))
    await economy.steal(interaction.user.id, user.id, amount, source="bank")
    await interaction.response.send_message(f"Hack successful! You extracted **{amount:,}** coins from {user.mention}’s bank.")


bot.tree.add_command(config_group)
bot.tree.add_command(automod_group)
bot.tree.add_command(custom_group)
bot.tree.add_command(economy_group)


async def main() -> None:
    await store.load()
    await economy.load()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
