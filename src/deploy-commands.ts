import { REST, Routes } from 'discord.js';
import { commands } from './commands/index.js';
import { env } from './config.js';

const rest = new REST({ version: '10' }).setToken(env.DISCORD_TOKEN);
const body = commands.map((command) => command.data.toJSON());

if (env.DISCORD_GUILD_ID) {
  await rest.put(Routes.applicationGuildCommands(env.DISCORD_CLIENT_ID, env.DISCORD_GUILD_ID), { body });
  console.log(`Registered ${body.length} commands in guild ${env.DISCORD_GUILD_ID}.`);
} else {
  await rest.put(Routes.applicationCommands(env.DISCORD_CLIENT_ID), { body });
  console.log(`Registered ${body.length} global commands.`);
}
