# Dragon Army Bot

Dragon Army Bot is a **slash-command-only** Discord moderation and utility bot built with TypeScript and discord.js. It provides a focused, self-hostable foundation inspired by the day-to-day server administration workflow of Carl-bot and Dyno.

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

This is an MVP rather than a clone of every Carl-bot or Dyno feature. The architecture is modular so ticketing, reaction roles, giveaways, scheduled reminders, and a web dashboard can be added later.

## Local development

You need Node.js 20 or later and a Discord application with a bot user. Enable the `Guilds`, `Guild Members`, `Guild Messages`, and `Message Content` privileged gateway intents in the Discord Developer Portal.

```bash
pnpm install
cp .env.example .env
```

Edit `.env` with your credentials:

```env
DISCORD_TOKEN=your_replacement_bot_token
DISCORD_CLIENT_ID=your_application_client_id
DISCORD_GUILD_ID=your_test_server_id
```

`DISCORD_GUILD_ID` is optional, but recommended during development because guild commands update quickly. Leave it blank when registering global commands.

Register commands and run locally:

```bash
pnpm register
pnpm dev
```

## Pella deployment

Pella advertises Node.js Discord bot hosting and GitHub integration [1] [2]. Import this repository or upload the ZIP, then configure the server with the following values:

| Pella setting | Value |
| --- | --- |
| Runtime | Node.js 20 or newer |
| Install command | `npm install` or Pella’s automatic package installation |
| Startup command | `npm start` |
| Required environment variable | `DISCORD_TOKEN` or `BOT_TOKEN` |
| Optional environment variable | `DISCORD_CLIENT_ID` or `CLIENT_ID` |
| Optional environment variable | `DISCORD_GUILD_ID` |
| Optional environment variable | `DATA_FILE=./data/config.json` |

The package’s `start` script runs `tsx src/index.ts`, so Pella can start the project directly after installing dependencies. The bot does not need an HTTP port. Add the token through Pella’s environment settings, not to the repository. The token previously pasted into chat should be revoked and replaced before use. Keep the `data` directory persistent if you want server configuration to survive restarts.

Run `npm run register` once from Pella’s console or from a local machine with the same environment variables. If `DISCORD_GUILD_ID` is present, commands are registered in that server immediately. If it is absent, commands are registered globally and may take time to appear.

Pella’s public pages confirm GitHub **import/integration**, but they do not document two-way synchronization or automatic commits from dashboard edits back to GitHub [1] [2]. Treat GitHub as the source repository and Pella as the deployment target unless your logged-in Pella dashboard explicitly provides a commit or push action. Changes made in Pella should not be assumed to update GitHub.

## Other Node.js hosts

The same project also works on Wispbyte and ordinary Node.js hosting. Use Node.js 20 or newer, install dependencies, set `DISCORD_TOKEN`, and start it with `npm start`.

## Recommended Discord permissions

Install the bot with the minimum permissions needed by your server. For the included feature set, it generally needs View Channels, Send Messages, Embed Links, Read Message History, Manage Messages, Moderate Members, Kick Members, and Ban Members. Keep the bot’s role below roles that it should not be able to moderate.

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

## Development checks

```bash
./node_modules/.bin/tsc -p tsconfig.json --noEmit
./node_modules/.bin/vitest run
```

The command definitions live in `src/commands/index.ts`, event handling lives in `src/index.ts`, and JSON persistence lives in `src/lib/store.ts`. The project uses strict TypeScript checks and includes tests for the persistence layer and duration parsing.

## References

[1]: https://www.pella.app/discord-bot-hosting "Pella Discord Bot Hosting"

[2]: https://www.pella.app/free-discord-bot-hosting "Pella Free Discord Bot Hosting"
