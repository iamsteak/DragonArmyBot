# Dragon Army Bot

Dragon Army Bot is a **Python-only, slash-command Discord bot** inspired by Carl-bot and Dyno. It is designed to run directly on Pella or any standard Python bot host.

## Main file

The main file is:

```text
main.py
```

The bot uses only slash commands. There is no TypeScript, JavaScript, `src/` entry point, or prefix-command handler in this version.

## Included commands

| Area | Commands and behavior |
| --- | --- |
| Moderation | `/warn`, `/timeout`, `/kick`, `/ban`, and `/purge` with permission and role checks |
| Server configuration | `/config view`, `/config log-channel`, `/config welcome`, and `/config reset` |
| Automod | `/automod`, `/blockword add`, `/blockword remove`, and `/blockword list` |
| Onboarding | Welcome messages with `{user}` and `{server}` placeholders |
| Logging | Configurable channel for warnings, automod deletions, bans, and member departures |
| Custom responses | `/custom-command set`, `/custom-command remove`, `/custom-command list`, and `/custom name` |
| Utilities | `/help`, `/ping`, `/server`, and `/userinfo` |

## Pella setup

Upload this project or import the GitHub repository into Pella. Set the server language/runtime to **Python 3.10 or newer**.

| Pella setting | Value |
| --- | --- |
| Main file | `main.py` |
| Install command | `pip install -r requirements.txt` |
| Startup command | `python main.py` |
| Environment variable | `DISCORD_TOKEN=your_new_bot_token` |
| Optional environment variable | `DISCORD_GUILD_ID=your_test_server_id` |
| Optional environment variable | `DATA_FILE=data/config.json` |

The bot only needs `DISCORD_TOKEN` to start. Set `DISCORD_GUILD_ID` if you want slash commands registered quickly in one test server. If it is empty, the bot registers commands globally, which can take longer to appear.

Add the token through Pella’s environment-variable settings. Do not put a real token in `.env`, GitHub, or the ZIP file. The token previously pasted into chat should be revoked and replaced before use. Keep `data/config.json` persistent if you want server settings to survive restarts.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## Discord setup

Create a Discord application and bot user, then enable the **Server Members Intent** and **Message Content Intent** in the Developer Portal. Invite the bot with the permissions required for your server: View Channels, Send Messages, Embed Links, Read Message History, Manage Messages, Moderate Members, Kick Members, and Ban Members. Keep the bot role below roles it should not moderate.

## Notes

This is an MVP rather than a clone of every Carl-bot or Dyno feature. The JSON store and command groups are structured so ticketing, reaction roles, giveaways, reminders, and a dashboard can be added later.

Pella advertises Node.js and Python Discord bot hosting and GitHub integration [1] [2]. Its public pages confirm repository import/integration but do not document automatic two-way commits from Pella’s dashboard back to GitHub. Treat GitHub as the source repository and Pella as the deployment target unless your authenticated Pella dashboard explicitly provides a commit or push action.

## References

[1]: https://www.pella.app/discord-bot-hosting "Pella Discord Bot Hosting"

[2]: https://www.pella.app/free-discord-bot-hosting "Pella Free Discord Bot Hosting"
