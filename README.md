# Dragon Army Bot

Dragon Army Bot is a **Python-only, slash-command Discord bot** inspired by Carl-bot and Dyno. It includes server moderation, automod, onboarding, logging, and a persistent Dragon Army economy game.

## Pella setup

Upload this project or import the GitHub repository into Pella. Set the runtime to **Python 3.10 or newer**.

| Pella setting | Value |
| --- | --- |
| Main file | `main.py` |
| Install command | `pip install -r requirements.txt` |
| Startup command | `python main.py` |
| Required environment variable | `DISCORD_TOKEN=your_new_bot_token` |
| Pella-required global mode | `DISCORD_GUILD_ID=global` |
| Optional environment variable | `DATA_FILE=data/config.json` |

Only `DISCORD_TOKEN` is needed to start the bot. If Pella requires a Guild ID value but you want commands everywhere, set `DISCORD_GUILD_ID` to `global`. The bot treats `global`, `none`, `all`, and `0` as global registration mode. A real numeric server ID registers commands instantly in only that test server. Keep the `data` directory persistent so both `config.json` and `economy.json` survive restarts.

Do not put a real token in GitHub or the ZIP file. The token previously pasted into chat should be revoked and replaced before use. The public Pella pages advertise Python/Node.js Discord hosting and GitHub integration [1] [2], but do not document automatic two-way commits from Pella’s dashboard back to GitHub. Treat GitHub as the source repository and Pella as the deployment target.

## Moderation and server tools

| Area | Slash commands |
| --- | --- |
| Moderation | `/warn`, `/timeout`, `/kick`, `/ban`, `/unban`, `/purge`, `/nickname` |
| Channel control | `/slowmode`, `/lock`, `/unlock` |
| Server configuration | `/config view`, `/config log-channel`, `/config welcome`, `/config reset` |
| Automod | `/automod`, `/blockword add`, `/blockword remove`, `/blockword list` |
| Onboarding and logs | Welcome messages with `{user}` and `{server}`, plus moderation/automod/member logging |
| Custom responses | `/custom-command set`, `/custom-command remove`, `/custom-command list`, and `/custom name` |
| Utilities | `/help`, `/ping`, `/server`, and `/userinfo` |

Moderation commands use Discord permission gates and role-hierarchy checks. The bot does not bypass Discord permissions, and the bot role must be below roles it should not moderate.

## Dragon Army economy game

Every player starts with 100 coins. The economy is stored persistently in `data/economy.json`, with separate wallet and bank balances, XP, levels, cooldowns, inventory, quests, and a global rich list.

| Feature | Commands and gameplay |
| --- | --- |
| Account | `/economy balance`, `/economy bank-balance`, `/economy deposit`, `/economy withdraw`, `/economy inventory` |
| Earning | `/economy daily`, `/economy work`, `/economy fish`, `/economy mine`, `/economy hunt` |
| Games | `/economy slots` and `/economy coinflip` with cooldowns and wager limits |
| Risk and defense | `/economy rob` attacks a wallet and `/economy hack` attacks a bank; Firewalls, VPNs, Security Cameras, Dragon Armor, Decoy Wallets, and Insurance defend players |
| Shop | `/economy shop`, `/economy buy`, and `/economy use` for 23 items with active and passive effects, including bank cards |
| Social | `/economy pay` lets players transfer wallet coins to each other |
| Progression | `/economy quest` tracks work, game, and fishing goals; XP unlocks levels |
| Competition | `/economy leaderboard` is global; `/economy server-leaderboard` ranks only members of the current server |

The earning activities use cooldowns, randomized rewards, rare drops, item bonuses, and XP progression. Gambling commands have bounded wager ranges and do not use real money. The economy intentionally uses virtual coins only. Every player starts with a **20,000-coin bank limit**. `/economy bank-balance` shows current usage and remaining capacity, while `/economy deposit` and `/economy withdraw` move coins between wallet and bank.

## Twenty-item shop

Use `/economy shop` to browse the catalog and `/economy buy item:<key>` to purchase an item. Consumables are activated with `/economy use item:<key>`. Defensive items activate automatically when another player attacks you.

| Item | Use |
| --- | --- |
| `coffee` | Consumable reward boost |
| `energy_drink` | Resets your work cooldown |
| `lucky_charm` | Improves slot-machine odds |
| `sapphire_dice` | Improves coinflip payouts |
| `fishing_rod` | Improves fishing rewards |
| `pickaxe` | Improves mining rewards |
| `hunter_charm` | Improves hunting rewards |
| `golden_ticket` | Consumable coin bonus |
| `backpack` | Progression collectible |
| `lockpick` | Improves one `/economy rob` attempt |
| `hacker_kit` | Improves one `/economy hack` attempt |
| `firewall` | Blocks one incoming hack |
| `vpn` | Blocks one incoming hack |
| `security_camera` | Blocks one incoming robbery |
| `decoy_wallet` | Reduces one robbery loss |
| `dragon_armor` | Blocks one robbery or hack |
| `insurance` | Reduces one robbery or hack loss |
| `medkit` | Consumable emergency coin recovery |
| `guild_banner` | Progression collectible |
| `crown` | Prestige collectible |
| `bank_card` | Use to add 10,000 bank capacity |
| `gold_bank_card` | Use to add 25,000 bank capacity |
| `platinum_bank_card` | Use to add 100,000 bank capacity |

Players can use `/economy rob user:@member` to attempt a capped wallet robbery or `/economy hack user:@member` to attempt a capped bank extraction. Both commands have cooldowns, bounded rewards, and item-based defenses. No real money or external payment system is involved.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Create a Discord application and bot user, then enable the **Server Members Intent** and **Message Content Intent** in the Developer Portal. Invite the bot with View Channels, Send Messages, Embed Links, Read Message History, Manage Messages, Moderate Members, Kick Members, Ban Members, and Manage Channels as needed.

## Project files

The main runtime is `main.py`. Economy logic and persistence are in `economy.py`. Python dependencies are listed in `requirements.txt`. The standard-library tests are in `test_main.py`.

Run checks with:

```bash
python3 -m py_compile main.py economy.py test_main.py
python3 -m unittest -v
```

This remains an MVP rather than a clone of every Carl-bot or Dyno feature. Ticketing, reaction roles, giveaways, reminders, and a web dashboard can be added later.

## References

[1]: https://www.pella.app/discord-bot-hosting "Pella Discord Bot Hosting"

[2]: https://www.pella.app/free-discord-bot-hosting "Pella Free Discord Bot Hosting"
