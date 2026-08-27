import asyncio
import json
import logging
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
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
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)
config_group = app_commands.Group(name="config", description="Configure this server")
automod_group = app_commands.Group(name="blockword", description="Manage blocked words")
custom_group = app_commands.Group(name="custom-command", description="Manage custom server responses")
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


bot.tree.add_command(config_group)
bot.tree.add_command(automod_group)
bot.tree.add_command(custom_group)


async def main() -> None:
    await store.load()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
