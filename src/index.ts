import {
  Client,
  Events,
  GatewayIntentBits,
  Partials,
  TextChannel,
} from 'discord.js';
import { commands } from './commands/index.js';
import { env } from './config.js';
import { GuildStore } from './lib/store.js';

const store = new GuildStore(env.DATA_FILE);
await store.load();

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Channel, Partials.Message],
});

const commandMap = new Map(commands.map((item) => [item.data.name, item]));

client.once(Events.ClientReady, (readyClient) => {
  console.log(`Logged in as ${readyClient.user.tag} in ${readyClient.guilds.cache.size} server(s).`);
});

client.on(Events.InteractionCreate, async (interaction) => {
  if (!interaction.isChatInputCommand()) return;
  const command = commandMap.get(interaction.commandName);
  if (!command) return;
  try {
    await command.execute(interaction, store);
  } catch (error) {
    console.error(`Command ${interaction.commandName} failed`, error);
    const payload = { content: 'Something went wrong while running that command.', ephemeral: true };
    if (interaction.replied || interaction.deferred) await interaction.followUp(payload);
    else await interaction.reply(payload);
  }
});

client.on(Events.GuildMemberAdd, async (member) => {
  const config = store.get(member.guild.id);
  if (!config.welcomeChannelId || !config.welcomeMessage) return;
  const channel = await member.guild.channels.fetch(config.welcomeChannelId).catch(() => null);
  if (!channel?.isTextBased()) return;
  const message = config.welcomeMessage
    .replaceAll('{user}', member.toString())
    .replaceAll('{server}', member.guild.name);
  await (channel as TextChannel).send(message).catch((error) => console.error('Welcome message failed', error));
});

client.on(Events.MessageCreate, async (message) => {
  if (!message.guild || message.author.bot) return;
  const config = store.get(message.guild.id);
  const normalized = message.content.toLowerCase();
  if (config.autoModEnabled && config.blockedWords.some((word) => normalized.includes(word.toLowerCase()))) {
    const member = message.member;
    if (member?.permissions.has('ManageMessages')) return;
    await message.delete().catch(() => undefined);
    const warning = await message.channel.send(`${message.author}, that message was removed by automod.`).catch(() => null);
    if (warning) setTimeout(() => warning.delete().catch(() => undefined), 5_000);
    if (config.logChannelId) {
      const channel = await message.guild.channels.fetch(config.logChannelId).catch(() => null);
      if (channel?.isTextBased()) await channel.send(`🛡️ Automod removed a message from ${message.author.tag} in ${message.channel}.`).catch(() => undefined);
    }
    return;
  }
});

client.on(Events.GuildBanAdd, async (ban) => {
  const config = store.get(ban.guild.id);
  if (!config.logChannelId) return;
  const channel = await ban.guild.channels.fetch(config.logChannelId).catch(() => null);
  if (channel?.isTextBased()) await channel.send(`🔨 **Ban** — ${ban.user.tag} was banned.`).catch(() => undefined);
});

client.on(Events.GuildMemberRemove, async (member) => {
  const config = store.get(member.guild.id);
  if (!config.logChannelId) return;
  const channel = await member.guild.channels.fetch(config.logChannelId).catch(() => null);
  if (channel?.isTextBased()) await channel.send(`🚪 **Member left** — ${member.user.tag}`).catch(() => undefined);
});

process.on('unhandledRejection', (error) => console.error('Unhandled rejection', error));
process.on('uncaughtException', (error) => console.error('Uncaught exception', error));

await client.login(env.DISCORD_TOKEN);
