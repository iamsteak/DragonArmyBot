# Dragon Army Bot

Dragon Army Bot is a modular Discord moderation and utility bot built with **TypeScript** and **discord.js**. It provides a focused, self-hostable foundation inspired by the day-to-day server administration workflow of Carl-bot and Dyno.

## Included capabilities

| Area | Commands and behavior |
| --- | --- |
| Moderation | `/warn`, `/timeout`, `/kick`, `/ban`, and `/purge` with permission gates and role-hierarchy checks |
| Server configuration | `/config view`, `/config log-channel`, `/config welcome`, and `/config reset` |
| Automod | `/automod`, `/blockword add`, `/blockword remove`, and `/blockword list`; matching messages are deleted and optionally logged |
| Onboarding | Configurable member welcome messages with `{user}` and `{server}` placeholders |
| Logging | Configurable channel for warnings, automod deletions, bans, and member departures |
| Custom responses | `/custom-command set`, `/custom-command remove`, `/custom-command list`, and `/custom name` |
| Utilities | `/help`, `/ping`, `/server`, and `/userinfo` |

This is an MVP rather than a clone of every Carl-bot or Dyno feature. The architecture is intentionally modular so ticketing, reaction roles, giveaways, scheduled reminders, and a web dashboard can be added without rewriting the command runtime.

## Requirements

You need Node.js 20 or later, a Discord application with a bot user, and a server where you have permission to install applications. The bot requires the `Guilds`, `Guild Members`, `Guild Messages`, and `Message Content` privileged gateway intents. Enable the privileged intents in the Discord Developer Portal before starting the bot.

## Installation

```bash
pnpm install
cp .env.example .env
```

Fill in `DISCORD_TOKEN` and `DISCORD_CLIENT_ID`. Set `DISCORD_GUILD_ID` during development to register commands in one server immediately. Leave it blank for global registration; Discord may take time to propagate global commands.

Register commands and start the bot:

```bash
pnpm register
pnpm dev
```

For production:

```bash
pnpm build
pnpm start
```

The bot stores per-server settings in `data/config.json`. This file is intentionally ignored by Git because it contains server configuration and is runtime state.

## Recommended Discord permissions

Install the bot with the minimum permissions needed by your server. For the full included feature set, the bot generally needs View Channels, Send Messages, Embed Links, Read Message History, Manage Messages, Moderate Members, Kick Members, Ban Members, and Manage Channels only if future modules are enabled. Keep the bot’s role below roles that it should not be able to moderate.

## Command examples

```text
/config log-channel channel:#mod-logs
/config welcome channel:#welcome message:Welcome {user} to {server}!
/automod enabled:true
/blockword add word:scam
/custom-command set name:rules response:Read the rules in #rules before chatting.
/custom name:rules
/timeout user:@member duration:30m reason:Repeated spam
/purge amount:25
```

## Hosting choices

The bot must run continuously to receive Discord gateway events. A local computer is the simplest free option if it can remain online. A managed always-on Node.js service is more reliable for production and avoids requiring your own computer to stay online. A conventional cloud VM is appropriate when you need Docker, root access, a fixed IP, or other operating-system-level control. Keep the token in the host’s secret manager or environment variables; never commit it to the repository.

## Development notes

The command definitions live in `src/commands/index.ts`, event handling lives in `src/index.ts`, and the JSON persistence layer lives in `src/lib/store.ts`. The project uses strict TypeScript checks and includes tests for the persistence layer and duration parsing.

```bash
./node_modules/.bin/tsc -p tsconfig.json --noEmit
./node_modules/.bin/vitest run
```

## Safety and limitations

Moderation actions are protected by Discord permissions and role hierarchy checks. The bot does not attempt to bypass Discord’s permission model. Automod currently uses simple case-insensitive substring matching, so server staff should review blocked phrases carefully. Before public deployment, add rate limits, a database backend, structured audit records, and a dashboard if the bot will serve many servers.
